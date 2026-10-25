"""Upload admission gate (Stage A, UCD-131) — deterministic, synchronous, zero model cost.

Runs in the upload handlers BEFORE storage and BEFORE any enqueue. Two defects
it closes (UCD-124 plan §7.1 / §5 layer 1, Rev. 3):

  * double analysis of the same document (cost defect): a SHA-256 index over
    (a) the raw bytes and (b) the extracted Markdown recognises a known
    document — same content in a different file garb, or re-extracted with a
    newer Docling, counts as known. A hit means NO new job, no new analysis;
    the answer points at the existing entry with its provenance.
  * missing content-related admission check (safety defect): curated lists
    catch §86a StGB (text renderings of unconstitutional symbols), §86 StGB
    (organisation names, propaganda formulas) and further maintainable
    categories — deterministically, before acceptance.

The §86a term inventory is NOT a second list: it reuses the platform's
existing curated bilingual file (schemas/stage1_86a_critical_bilingual.json)
through the SAME tested matcher (fast_filter_bilingual_86a) the prompt
pipeline uses. The upload gate adds only the §86 organisation names and the
further categories as its own versioned data files under
my_app/safety_lists/, curated by the operator through ordinary repo review.

Rejections never repeat the found terms in the answer: the client gets the
plain-language reason category, the audit log gets (docHash, rule category,
timestamp) and nothing of the content itself.

Hash index storage: devserver/exports/knowledge_uploads/doc_hash_index.json
(gitignored, rebuildable in the sense that entries can be re-derived only from
the stored originals — the index itself is a cache of hashes, deliberately
NOT committed). Curated lists ARE committed (they are operator curation).
"""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Curated list files (versioned in the repository; operator curation is
# reviewable like code — UCD-124 §7.1).
_SAFETY_LISTS_DIR = Path(__file__).resolve().parents[1] / "safety_lists"
LIST_86_ORGS = "upload_gate_86_orgs.json"
LIST_FURTHER = "upload_gate_further_categories.json"

# Hash-sperrliste (blocklist of forbidden document hashes; starts EMPTY — the
# operator populates it through repo review, same as the term lists).
LIST_BLOCKED_HASHES = "upload_gate_blocked_hashes.json"

def _list_path(name: str) -> Path:
    """Resolve a curated list file at CALL time (tests redirect the dir)."""
    return _SAFETY_LISTS_DIR / name


# Hash index (doc_hash -> entry). Lives under devserver/exports/ (gitignored,
# runtime artefact) next to the other knowledge exports.
def _index_path() -> Path:
    import config

    return Path(config.EXPORTS_DIR) / "knowledge_uploads" / "doc_hash_index.json"


# Page limit for PDF uploads (Bibliothek parity: 100 MB byte limit lives in the
# routes; the page count catches the pathological many-tiny-pages file that a
# byte limit alone misses).
MAX_PDF_PAGES = 1000

# How much text-layer content is scanned per PDF (word budget, not token cap —
# platform rule). A 1000-page PDF's full text can be large; the deterministic
# scan reads at most this many words from the raw strings.
_TEXT_SCAN_WORD_BUDGET = 200_000

# Reason categories (plain language, DE wire as the routes are; never includes
# a found term). These strings go to the operator/UI verbatim.
REASON_NOT_PDF = "kein PDF"
REASON_ENCRYPTED = "verschlüsselt"
REASON_TOO_MANY_PAGES = "seitenlimit"
REASON_EMBEDDED_FILE = "eingebettete datei"
REASON_LAUNCH_ACTION = "startaktion"
REASON_BLOCKED_HASH = "gesperrtes dokument"
REASON_86A = "kennzeichen verfassungswidriger organisationen"
REASON_86 = "organisation oder propaganda verfassungswidriger organisationen"
REASON_FURTHER = "weiterer sperrgrund"

# Internal reason (UCD-140): NOT a content category but the state "the
# deterministic core scan could not run". Handled like every other reason —
# the gates return it, the routes audit it and answer with reject_message() —
# so an outage of the scanner rejects instead of admitting silently.
REASON_SCAN_UNAVAILABLE = "scan_unavailable"


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------

_LISTS_CACHE: Optional[Tuple[float, Dict[str, List[str]]]] = None


def _load_terms(name: str) -> List[str]:
    """Load one curated list file. Empty list when absent (a category without
    a file yet simply matches nothing); malformed file -> RuntimeError
    (fail-closed: a safety list that exists but cannot be read must never
    silently disable itself)."""
    path = _list_path(name)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        terms = data.get("terms", [])
        if not isinstance(terms, list) or not all(isinstance(t, str) for t in terms):
            raise ValueError("'terms' must be a list of strings")
        return [t for t in (s.strip() for s in terms) if t]
    except (OSError, ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Safety list {path.name} unreadable ({e}) — fail-closed") from e


def load_curated_lists() -> Dict[str, List[str]]:
    """All curated upload-gate lists in one dict: 86_orgs, further. Hash
    blocklist is separate (hashes, not terms). Fresh read each call — these
    files change through repo review, not at runtime."""
    return {
        "86_orgs": _load_terms(LIST_86_ORGS),
        "further": _load_terms(LIST_FURTHER),
    }


def load_blocked_hashes() -> List[str]:
    """SHA-256 hex hashes of forbidden documents. Empty when the file is
    absent (initial state) or its terms list is empty; malformed -> RuntimeError
    (fail-closed)."""
    path = _list_path(LIST_BLOCKED_HASHES)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        hashes = data.get("hashes", [])
        if not isinstance(hashes, list) or not all(isinstance(h, str) for h in hashes):
            raise ValueError("'hashes' must be a list of strings")
        out = []
        for h in hashes:
            h = h.strip().lower()
            if h and not re.fullmatch(r"[0-9a-f]{64}", h):
                raise ValueError(f"not a SHA-256 hex hash: {h[:12]}…")
            if h:
                out.append(h)
        return out
    except (OSError, ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Safety list {path.name} unreadable ({e}) — fail-closed"
        ) from e


# ---------------------------------------------------------------------------
# PDF validation (magic bytes, encryption, embedded executables)
# ---------------------------------------------------------------------------

_PDF_MAGIC = b"%PDF-"


def _pypdf():
    """Import pypdf lazily (only PDF uploads pay for it)."""
    from pypdf import PdfReader  # noqa: PLC0415

    return PdfReader


def validate_pdf(data: bytes) -> Optional[str]:
    """Deterministic PDF validation. Returns None when the file is an
    acceptable unencrypted PDF without embedded file streams or launch
    actions, otherwise a REASON_* category. Never opens the file with
    anything but pypdf — exploitable parser surfaces are not touched at all
    (the file is NOT stored on a reject, so there is nothing to exploit)."""
    if not data.startswith(_PDF_MAGIC):
        return REASON_NOT_PDF

    try:
        PdfReader = _pypdf()
        reader = PdfReader(BytesIO(data))  # type: ignore[name-defined]
    except Exception as e:  # noqa: BLE001 — any parse failure is a reject
        logger.info("[UPLOAD-GATE] PDF unparseable: %s", e)
        return REASON_NOT_PDF

    if reader.is_encrypted:
        return REASON_ENCRYPTED

    try:
        n_pages = len(reader.pages)
    except Exception as e:  # noqa: BLE001
        logger.info("[UPLOAD-GATE] page count unreadable: %s", e)
        return REASON_NOT_PDF
    if n_pages > MAX_PDF_PAGES:
        return REASON_TOO_MANY_PAGES

    # --- embedded file streams + launch actions: walk the object graph ------
    # Catalog /EmbeddedFiles (name tree or flat /Names array).
    try:
        root = reader.trailer["/Root"]
        if _catalog_has_embedded_files(root):
            return REASON_EMBEDDED_FILE
    except Exception as e:  # noqa: BLE001
        logger.info("[UPLOAD-GATE] catalog walk failed: %s", e)
        return REASON_NOT_PDF

    # Any /Launch action anywhere in the page tree (a launch action hands the
    # file to the OS; reject before it is ever stored).
    try:
        for page in reader.pages:
            if _page_has_launch_action(page):
                return REASON_LAUNCH_ACTION
    except Exception as e:  # noqa: BLE001
        logger.info("[UPLOAD-GATE] page walk failed: %s", e)
        return REASON_NOT_PDF

    return None


def _catalog_has_embedded_files(root: Any) -> bool:
    """True when the catalog declares embedded file streams (via /EmbeddedFiles
    under /Names or a flat /Names array). Structure-only check — the embedded
    bytes are never extracted."""
    names = root.get("/Names")
    if names is None:
        return False
    names = names.get_object()
    if "/EmbeddedFiles" not in names:
        return False
    embedded = names["/EmbeddedFiles"].get_object()
    if "/Names" in embedded or "/Kids" in embedded:
        return True
    # Flat array form: any value objects present -> embedded files exist.
    return bool(embedded.get("/Names"))


def _page_has_launch_action(page: Any) -> bool:
    """True when the page (or one of its annotations) carries a /Launch
    action under /AA or /A."""
    for holder in [page, *page_annots(page)]:
        for key in ("/AA", "/A"):
            action = holder.get(key)
            if action is None:
                continue
            action = action.get_object()
            if action.get("/S") == "/Launch":
                return True
    return False


def page_annots(page: Any) -> List[Any]:
    """The page's /Annots entries as objects ([]) when absent)."""
    annots = page.get("/Annots")
    if annots is None:
        return []
    arr = annots.get_object()
    out = []
    for ref in arr:
        try:
            out.append(ref.get_object())
        except Exception:  # noqa: BLE001 — unreadable annot: not a launch proof
            continue
    return out


# ---------------------------------------------------------------------------
# Text-layer scan (raw pypdf strings, no Docling)
# ---------------------------------------------------------------------------


def extract_text_layer(data: bytes, word_budget: int = _TEXT_SCAN_WORD_BUDGET) -> str:
    """The PDF's text layer as one lowercase string (raw pypdf extraction —
    the fast path that runs WITHOUT Docling). Truncated to word_budget words
    so a pathological file cannot blow the deterministic scan. Empty string
    for image-only PDFs (the LLM stage B check covers those in the pipeline)."""
    try:
        PdfReader = _pypdf()
        reader = PdfReader(BytesIO(data))  # type: ignore[name-defined]
        chunks: List[str] = []
        budget = word_budget
        for page in reader.pages:
            if budget <= 0:
                break
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001 — one bad page is not a reject
                continue
            chunks.append(text.lower())
            budget -= len(text.split())
        return " ".join(chunks)
    except Exception:  # noqa: BLE001 — unreadable text layer scans as empty
        # Checked under UCD-140 and deliberately kept fail-open: this function
        # produces the scan INPUT, and a missing text layer is a legitimate
        # property of a scanned document (image-only PDFs are the normal case
        # here; the pipeline's stage B model check covers them). The fail-closed
        # rule belongs where the CHECK itself is gone — scan_text_layer below.
        return ""


def scan_text_layer(text: str) -> Optional[str]:
    """Curated-list scan over the extracted text layer. Returns the REASON_*
    category of the first hit or None. §86a reuses the platform's curated
    bilingual list through the SAME tested matcher the prompt pipeline uses
    (schemas.engine.stage_orchestrator.fast_filter_bilingual_86a) — one
    curated inventory, not two. §86 org names and further categories use the
    upload gate's own versioned data files with plain word-boundary matching
    (these are organisation NAMES and formulas; fuzzy matching over phrase
    terms is the §86a lesson from 2026-08-17 and must NOT be repeated for
    multi-word org names).

    Returns REASON_SCAN_UNAVAILABLE when the §86a matcher cannot be imported:
    a None answer from this function always means every check actually ran
    (UCD-140, 2026-09-28)."""
    if not text:
        return None

    # §86a — text renderings of unconstitutional symbols (curated bilingual
    # list, fuzzy matcher, tested by test_86a_word_boundaries.py).
    try:
        from schemas.engine.stage_orchestrator import fast_filter_bilingual_86a
    except ImportError as e:
        # Fail-closed (UCD-140, 2026-09-28). Until this date the missing import
        # only logged a warning and the scan was skipped, so the gate answered
        # "clean" without having looked at the document — while _load_terms two
        # screens up raises on a list file it cannot read. The §86a matcher IS
        # the deterministic core scan of this gate; the one failure mode it must
        # not have is falling out silently. A rejection is recoverable (the
        # operator retries once the deployment is whole again); an admitted
        # unscanned document is not.
        logger.error(
            "[UPLOAD-GATE] §86a matcher unavailable (%s) — scan fail-closed, upload rejected", e
        )
        return REASON_SCAN_UNAVAILABLE

    found, _terms = fast_filter_bilingual_86a(text, "de")
    if found:
        return REASON_86A

    # §86 — organisation names / propaganda formulas (exact, case-insensitive,
    # word-boundary). Own versioned data file.
    lists = load_curated_lists()
    for term in lists["86_orgs"]:
        if _word_boundary_ci(text, term):
            return REASON_86
    for term in lists["further"]:
        if _word_boundary_ci(text, term):
            return REASON_FURTHER
    return None


def _word_boundary_ci(text: str, term: str) -> bool:
    """Case-insensitive whole-word/phrase match at word boundaries (the term
    is quoted so list entries are always literal, never regex)."""
    pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
    return bool(pattern.search(text))


# ---------------------------------------------------------------------------
# Hashes + hash index
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def md_hash(md_text: str) -> str:
    """SHA-256 over the extracted Markdown, whitespace-normalised (the same
    content re-extracted with a different Docling build differs only in
    layout whitespace, not in text)."""
    normalised = re.sub(r"\s+", " ", (md_text or "")).strip()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# Hash-index storage: one JSON file guarded by a process lock (the upload
# routes are the only writers; the FIFO ingest worker is the only updater).
_INDEX_LOCK = threading.Lock()


def _read_index(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("[UPLOAD-GATE] hash index unreadable (%s); treating as empty", e)
        return {}


def lookup_hash_index(raw_hash: str, extracted_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Look up a document in the hash index. Matches on EITHER hash — the
    raw-bytes hash (same file again) or the extracted-MD hash (same content in
    a different file garb / after a new Docling). Returns the stored entry
    (with doc_id + provenance) or None."""
    with _INDEX_LOCK:
        index = _read_index(_index_path())
    for entry in index.values():
        if not isinstance(entry, dict):
            continue
        if entry.get("raw_hash") == raw_hash:
            return entry
        if extracted_hash and entry.get("md_hash") == extracted_hash:
            return entry
    return None


def record_hash_index(doc_id: str, raw_hash: str, md_hash: Optional[str]) -> None:
    """Add or update the index entry for a doc. Keyed by raw_hash (one entry
    per document content). Never raises: an index write failure degrades the
    gate to per-run memory only (the next successful write heals it)."""
    path = _index_path()
    try:
        with _INDEX_LOCK:
            index = _read_index(path)
            entry = {
                "doc_id": doc_id,
                "raw_hash": raw_hash,
                "md_hash": md_hash,
                "recorded_at": _now_iso(),
            }
            index[raw_hash] = entry
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("[UPLOAD-GATE] hash index write failed: %s", e)


def remove_hash_index(doc_id: str) -> None:
    """Drop every entry pointing at a deleted doc_id (delete route parity —
    a deleted dossier must not shadow future uploads of the same file)."""
    path = _index_path()
    try:
        with _INDEX_LOCK:
            index = _read_index(path)
            changed = False
            for key in [k for k, v in index.items()
                        if isinstance(v, dict) and v.get("doc_id") == doc_id]:
                del index[key]
                changed = True
            if changed:
                path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("[UPLOAD-GATE] hash index update failed: %s", e)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Audit log (rejections only; no content stored)
# ---------------------------------------------------------------------------


def audit_rejection(doc_hash: str, reason: str, path_hint: str = "") -> None:
    """Append one rejection line to the audit log: docHash, rule category,
    timestamp. Nothing of the content itself is kept — the file is never
    stored, and the found terms never enter the log."""
    import config

    audit_path = Path(config.EXPORTS_DIR) / "knowledge_uploads" / "upload_gate_audit.log"
    line = json.dumps({
        "ts": _now_iso(),
        "doc_hash": doc_hash,
        "reason": reason,
        "origin": path_hint or None,
    }, ensure_ascii=False)
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as e:
        logger.warning("[UPLOAD-GATE] audit write failed: %s", e)


# ---------------------------------------------------------------------------
# The gate itself
# ---------------------------------------------------------------------------


def gate_pdf_upload(data: bytes) -> Tuple[Optional[str], str]:
    """Full Stage-A gate for a PDF upload: validation + hash blocklist + hash
    index lookup + text-layer scan, in that order (cheapest and most
    decisive first). Returns (reason, raw_hash): reason None means the file
    is admitted; raw_hash is ALWAYS computed (the caller records it in the
    index after a successful enqueue or audits it on a reject)."""
    raw_hash = sha256_hex(data)

    # 1. Hash-Sperrliste (curated, versioned, initially empty).
    if raw_hash in load_blocked_hashes():
        return REASON_BLOCKED_HASH, raw_hash

    # 2. File validation (magic bytes, encryption, page limit, embedded
    #    executables, launch actions).
    reason = validate_pdf(data)
    if reason:
        return reason, raw_hash

    # 3. Hash index (double-analysis protection) — VOR dem Enqueue.
    entry = lookup_hash_index(raw_hash)
    if entry is not None:
        # The caller resolves the dossier and answers with a reference.
        return _DUPLICATE, raw_hash

    # 4. Text-layer pattern scan (§86a, §86, further categories). A scan that
    #    cannot run is a rejection like any other (REASON_SCAN_UNAVAILABLE,
    #    UCD-140) — the same holds in gate_stored_pdf below.
    text = extract_text_layer(data)
    reason = scan_text_layer(text)
    if reason:
        return reason, raw_hash

    return None, raw_hash


# ---------------------------------------------------------------------------
# Plain-language rejection messages (NEVER repeat a found term)
# ---------------------------------------------------------------------------

_REJECT_MESSAGES = {
    REASON_NOT_PDF: "Datei nicht angenommen: kein lesbares PDF.",
    REASON_ENCRYPTED: "Datei nicht angenommen: verschlüsselte Dokumente werden nicht akzeptiert.",
    REASON_TOO_MANY_PAGES: (
        "Datei nicht angenommen: das Dokument überschreitet das Seitenlimit "
        f"von {MAX_PDF_PAGES} Seiten."
    ),
    REASON_EMBEDDED_FILE: (
        "Datei nicht angenommen: das Dokument enthält eingebettete Dateien. "
        "Solche Dokumente werden nicht angenommen."
    ),
    REASON_LAUNCH_ACTION: (
        "Datei nicht angenommen: das Dokument enthält Aktionen, die Programme "
        "starten. Solche Dokumente werden nicht angenommen."
    ),
    REASON_BLOCKED_HASH: "Datei nicht angenommen: dieses Dokument ist gesperrt.",
    REASON_86A: (
        "Dokument nicht angenommen: Kennzeichen verfassungswidriger "
        "Organisationen."
    ),
    REASON_86: (
        "Dokument nicht angenommen: Inhalte verfassungswidriger Organisationen."
    ),
    REASON_FURTHER: "Dokument nicht angenommen: Inhalt entspricht nicht den Aufnahmekriterien.",
    # Never names the module, the import or the matcher: the answer says that
    # the check is unavailable, nothing about how it is built (UCD-140). The
    # platform's own sentence for a check that could not be carried out
    # (stage_orchestrator.SAFETY_CHECK_UNAVAILABLE_MESSAGE) is deliberately NOT
    # reused here: it lives in the module that just failed to import, and it
    # addresses the learner mid-run, where this surface answers the operator.
    REASON_SCAN_UNAVAILABLE: (
        "Dokument nicht angenommen: die Sicherheitsprüfung ist derzeit nicht "
        "verfügbar."
    ),
}


def reject_message(reason: str) -> str:
    """The operator-facing plain-language rejection text for a rule category.
    Never includes a found term — the category is all the answer carries."""
    return _REJECT_MESSAGES.get(reason, "Datei nicht angenommen.")


def gate_stored_pdf(data: bytes) -> Tuple[Optional[str], str]:
    """Stage A for REPROCESS runs (UCD-131): everything except the hash-index
    duplicate check — re-analysing an EXISTING document is the operator's
    explicit way around the index (working basis while the UCD-124 decision
    is open). Blocked hashes, file validation and the curated text-layer
    lists still apply to the stored source (a PDF that predates the gate may
    carry embedded files or launch actions)."""
    raw_hash = sha256_hex(data)
    if raw_hash in load_blocked_hashes():
        return REASON_BLOCKED_HASH, raw_hash
    reason = validate_pdf(data)
    if reason:
        return reason, raw_hash
    text = extract_text_layer(data)
    reason = scan_text_layer(text)
    if reason:
        return reason, raw_hash
    return None, raw_hash


# Sentinel reason for "known document" — internal; the routes translate it
# into a 200-with-reference response, not a rejection.
_DUPLICATE = "__duplicate__"


def is_duplicate(reason: Optional[str]) -> bool:
    return reason == _DUPLICATE


# ---------------------------------------------------------------------------
# Reduced gate for image uploads (UCD-131 scope 6: validation + hash
# blocklist only — a deterministic symbol IMAGE recognition is not reliably
# achievable; the LLM image check is a separate decision, not this ticket)
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_SIGNATURES: Dict[str, bytes] = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
    "webp": b"RIFF",
}


def gate_image_upload(data: bytes, allowed: Optional[set] = None) -> Tuple[Optional[str], str]:
    """Reduced Stage A for image uploads: magic-byte validation + hash
    blocklist. Returns (reason, raw_hash); reason None = admitted."""
    raw_hash = sha256_hex(data)
    if raw_hash in load_blocked_hashes():
        return REASON_BLOCKED_HASH, raw_hash
    if not any(data.startswith(sig) for sig in ALLOWED_IMAGE_SIGNATURES.values()):
        # Generic "wrong file type" category for images (the magic-byte check
        # is the image analogue of the PDF magic-bytes check above).
        return REASON_NOT_PDF, raw_hash
    return None, raw_hash


# BytesIO import kept local to the functions that need it (pypdf callers).


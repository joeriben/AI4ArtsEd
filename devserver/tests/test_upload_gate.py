"""Stage-A upload admission gate (UCD-131) — deterministic unit tests.

Covers the gate's four pillars with NO model, NO Docling, NO network:

  * file validation (magic bytes, encryption, page limit, embedded file
    streams, launch actions),
  * hash formation (raw SHA-256; whitespace-normalised MD hash — same content
    after a new Docling counts as known),
  * curated-list matching (§86a through the platform's existing bilingual
    inventory + tested matcher; §86/further lists with word-boundary logic,
    and the fail-closed answer when that matcher cannot be imported at all —
    UCD-140),
  * hash index (duplicate detection by EITHER hash; delete cleanup) and the
    rejection surface (plain-language category, never a found term; audit
    line without content).

Route-level behaviour (duplicate upload -> 409 with provenance reference,
reject -> 400 with nothing stored) lives in test_upload_gate_routes.py; the
reduced image gate in test_upload_gate_image.py.

Run: python3 -m pytest devserver/tests/test_upload_gate.py -q
"""

import io
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import my_app.services.upload_gate as ug


# ---------------------------------------------------------------------------
# Minimal hand-built PDFs (no Docling, no external fixtures)
# ---------------------------------------------------------------------------

def mk_pdf(text_lines=("Ein Dokument.",), embedded_name=None, launch=False,
           n_pages=1):
    """Build a minimal valid PDF in memory. Optional /EmbeddedFiles entry or
    a /Launch page action — exactly the two attack surfaces the gate rejects."""
    objs = {}
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(n_pages))
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
    for i in range(n_pages):
        page_num = 3 + i * 2
        content_num = page_num + 1
        text = "BT /F1 12 Tf 72 720 Td " + " ".join(
            f"({t}) Tj 0 -20 Td" for t in text_lines) + " ET"
        stream = f"<< /Length {len(text)} >>\nstream\n{text}\nendstream"
        extra = ""
        if embedded_name and i == 0:
            # embedded file stream (object 9) + /EmbeddedFiles name tree
            objs[9] = (f"<< /Type /EmbeddedFile /Length 3 >>\nstream\nMZ\x00\x00"
                       ).encode()
            objs[10] = f"<< /F 9 0 R /UF 9 0 R >>".encode()
            objs[11] = f"<< /F << /Type /Filespec /F ({embedded_name}) /EF 10 0 R >> >>".encode()
            objs[12] = f"<< /Names [ ({embedded_name}) 11 0 R ] >>".encode()
            objs[13] = b"<< /EmbeddedFiles 12 0 R >>"
            objs[1] = b"<< /Type /Catalog /Pages 2 0 R /Names 13 0 R >>"
        if launch and i == 0:
            # /Launch additional action on the page
            objs[9] = b"<< /S /Launch /F << /F (evil.bat) >> /Win << /F (evil.bat) >> >>"
            extra = " /AA 9 0 R"
        objs[page_num] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 99 0 R >> >> /Contents {content_num} 0 R"
            f"{extra} >>"
        ).encode()
        objs[content_num] = stream.encode()
    objs[99] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    out = b"%PDF-1.4\n"
    offsets = []
    for num in sorted(objs):
        offsets.append((num, len(out)))
        out += f"{num} 0 obj\n".encode() + objs[num] + b"\nendobj\n"
    xref_pos = len(out)
    max_num = max(objs)
    out += b"xref\n0 " + str(max_num + 1).encode() + b"\n0000000000 65535 f \n"
    offset_map = {num: off for num, off in offsets}
    for num in range(1, max_num + 1):
        off = offset_map.get(num, 0)
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(max_num + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    )
    return out


@pytest.fixture()
def gate_env(tmp_path, monkeypatch):
    """All gate storage (hash index, audit log, curated lists) redirected into
    tmp_path — the tests never touch the real devserver exports."""
    import config

    lists = tmp_path / "safety_lists"
    lists.mkdir()
    uploads = tmp_path / "knowledge_uploads"
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path, raising=False)
    monkeypatch.setattr(ug, "_SAFETY_LISTS_DIR", lists, raising=False)
    # _index_path() imports config at call time; the fixture covers it via
    # config.EXPORTS_DIR. The safety lists dir is read at call time too.
    return tmp_path, lists


def _write_list(lists_dir, name, payload):
    (lists_dir / name).write_text(json.dumps(payload, ensure_ascii=False),
                                 encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. File validation
# ---------------------------------------------------------------------------

class TestValidatePdf:
    def test_clean_pdf_passes(self):
        assert ug.validate_pdf(mk_pdf()) is None

    def test_magic_bytes(self):
        assert ug.validate_pdf(b"PK\x03\x04 not a pdf") == ug.REASON_NOT_PDF
        assert ug.validate_pdf(b"%PDF- garbage beyond repair") == ug.REASON_NOT_PDF

    def test_encrypted_rejected(self):
        from pypdf import PdfWriter

        w = PdfWriter()
        w.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        w.encrypt("pw")
        w.write(buf)
        assert ug.validate_pdf(buf.getvalue()) == ug.REASON_ENCRYPTED

    def test_embedded_file_rejected(self):
        data = mk_pdf(embedded_name="evil.exe")
        assert ug.validate_pdf(data) == ug.REASON_EMBEDDED_FILE

    def test_launch_action_rejected(self):
        data = mk_pdf(launch=True)
        assert ug.validate_pdf(data) == ug.REASON_LAUNCH_ACTION

    def test_page_limit(self, monkeypatch):
        monkeypatch.setattr(ug, "MAX_PDF_PAGES", 2)
        assert ug.validate_pdf(mk_pdf(n_pages=3)) == ug.REASON_TOO_MANY_PAGES
        assert ug.validate_pdf(mk_pdf(n_pages=2)) is None


# ---------------------------------------------------------------------------
# 2. Hash formation
# ---------------------------------------------------------------------------

class TestHashes:
    def test_raw_hash_is_sha256(self):
        import hashlib

        assert ug.sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()

    def test_md_hash_whitespace_normalised(self):
        # Same content after a different Docling build (layout whitespace
        # differs) -> same hash. Different content -> different hash.
        assert ug.md_hash("a  b\nc\n\nd") == ug.md_hash("a b c d")
        assert ug.md_hash("a b c") != ug.md_hash("a b d")

    def test_md_hash_empty(self):
        assert ug.md_hash("") == ug.md_hash("   \n  ")


# ---------------------------------------------------------------------------
# 3. Curated lists
# ---------------------------------------------------------------------------

class TestCuratedLists:
    def test_absent_lists_are_empty(self, gate_env):
        _, lists = gate_env
        assert ug.load_curated_lists() == {"86_orgs": [], "further": []}
        assert ug.load_blocked_hashes() == []

    def test_malformed_list_fails_closed(self, gate_env):
        _, lists = gate_env
        _write_list(lists, "upload_gate_86_orgs.json", {"terms": [42]})
        with pytest.raises(RuntimeError):
            ug.load_curated_lists()

    def test_blocked_hash_validation(self, gate_env):
        _, lists = gate_env
        _write_list(lists, "upload_gate_blocked_hashes.json",
                    {"hashes": ["NOT-A-HASH"]})
        with pytest.raises(RuntimeError):
            ug.load_blocked_hashes()

    def test_word_boundary_matching(self, gate_env):
        _, lists = gate_env
        _write_list(lists, "upload_gate_86_orgs.json",
                    {"terms": ["Beispielorganisation"]})
        assert ug.scan_text_layer("die beispielorganisation war aktiv") == ug.REASON_86
        # Word boundary: a longer word containing the term does NOT match.
        assert ug.scan_text_layer("die BeispielorganisationX") is None

    def test_further_category(self, gate_env):
        _, lists = gate_env
        _write_list(lists, "upload_gate_further_categories.json",
                    {"terms": ["glorifizierungsmarke"]})
        assert ug.scan_text_layer("ein text mit glorifizierungsmarke drin") == ug.REASON_FURTHER


class Test86aScan:
    """The §86a path reuses the platform's curated bilingual inventory and the
    SAME tested matcher as the prompt pipeline (test_86a_word_boundaries.py)
    — these tests pin the gate to that matcher, not the inventory itself."""

    def test_86a_hit(self):
        assert ug.scan_text_layer("ein foto mit ss symbol an der wand") == ug.REASON_86A

    def test_86a_no_false_positive(self):
        assert ug.scan_text_layer("The bird as a symbolic companion.") is None

    def test_86a_obfuscation_still_caught(self):
        assert ug.scan_text_layer("ein ha1kenkreuz an der wand") == ug.REASON_86A


class TestScanUnavailableFailsClosed:
    """UCD-140: a §86a matcher that cannot be imported rejects the document.

    Until 2026-09-28 the ImportError only wrote a warning and the scan was
    skipped — the gate answered "clean" over a document nothing had looked at,
    while a curated list file it cannot read raises (test_malformed_list_
    fails_closed above). This is the upload gate's case of the platform rule
    that test_check_cannot_permit.py holds for the prompt chain: a check that
    cannot run does not grant permission."""

    @pytest.fixture()
    def matcher_gone(self, monkeypatch):
        """The matcher module unimportable: None in sys.modules is what makes
        the `from schemas.engine.stage_orchestrator import ...` inside
        scan_text_layer raise ImportError."""
        monkeypatch.setitem(sys.modules, "schemas.engine.stage_orchestrator", None)

    def test_scan_returns_the_reason_and_never_none(self, gate_env, matcher_gone):
        # Text that matches no curated list: the pre-2026-09-28 answer was None.
        reason = ug.scan_text_layer("ein ganz gewöhnlicher satz über ein museum")
        assert reason == ug.REASON_SCAN_UNAVAILABLE
        assert reason is not None

    def test_the_import_error_is_logged_as_an_error(self, gate_env, matcher_gone, caplog):
        with caplog.at_level(logging.ERROR, logger=ug.logger.name):
            ug.scan_text_layer("ein ganz gewöhnlicher satz über ein museum")
        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert errors, "the unavailable matcher must be logged with logger.error"
        assert "[UPLOAD-GATE]" in errors[0].getMessage()

    def test_gate_pdf_upload_rejects(self, gate_env, matcher_gone):
        reason, raw_hash = ug.gate_pdf_upload(mk_pdf())
        assert reason == ug.REASON_SCAN_UNAVAILABLE
        assert not ug.is_duplicate(reason)  # not a 200-with-reference either
        assert len(raw_hash) == 64         # the audit line has its doc hash

    def test_gate_stored_pdf_rejects(self, gate_env, matcher_gone):
        reason, stored_hash = ug.gate_stored_pdf(mk_pdf())
        assert reason == ug.REASON_SCAN_UNAVAILABLE
        assert len(stored_hash) == 64

    def test_the_same_pdf_is_admitted_once_the_matcher_is_there(self, gate_env):
        # Counter-test WITHOUT the fixture: the rejection above comes from the
        # missing matcher and from nothing else in this PDF.
        assert ug.gate_pdf_upload(mk_pdf())[0] is None

    def test_reject_message_is_plain_german_without_internals(self):
        msg = ug.reject_message(ug.REASON_SCAN_UNAVAILABLE)
        assert msg == ("Dokument nicht angenommen: die Sicherheitsprüfung ist "
                       "derzeit nicht verfügbar.")
        for internal in ("scan_unavailable", "importerror", "import", "schemas",
                         "stage_orchestrator", "86a", "matcher", "modul"):
            assert internal not in msg.lower(), internal
        # Anredefrei (rule 17): no second person, no plea.
        for address in (r"\bdu\b", r"\bdeine?\b", r"\bsie\b", r"\bihre?\b",
                        r"\bbitte\b", r"\beuch\b"):
            assert not re.search(address, msg, re.IGNORECASE), address

    def test_audit_line_carries_the_reason_and_no_content(self, gate_env):
        import config

        ug.audit_rejection("f" * 64, ug.REASON_SCAN_UNAVAILABLE, "knowledge/upload")
        audit = Path(config.EXPORTS_DIR) / "knowledge_uploads" / "upload_gate_audit.log"
        line = json.loads(audit.read_text(encoding="utf-8").strip())
        assert line["reason"] == ug.REASON_SCAN_UNAVAILABLE
        assert set(line) == {"ts", "doc_hash", "reason", "origin"}


# ---------------------------------------------------------------------------
# 4. Hash index (double-analysis protection)
# ---------------------------------------------------------------------------

class TestHashIndex:
    def test_record_and_lookup_by_raw_hash(self, gate_env):
        ug.record_hash_index("doc-1", "a" * 64, "b" * 64)
        entry = ug.lookup_hash_index("a" * 64)
        assert entry and entry["doc_id"] == "doc-1"

    def test_lookup_by_md_hash(self, gate_env):
        # Same content, different file garb: the MD hash recognises it.
        ug.record_hash_index("doc-1", "a" * 64, "b" * 64)
        entry = ug.lookup_hash_index("c" * 64, extracted_hash="b" * 64)
        assert entry and entry["doc_id"] == "doc-1"

    def test_no_hit(self, gate_env):
        ug.record_hash_index("doc-1", "a" * 64, "b" * 64)
        assert ug.lookup_hash_index("d" * 64) is None

    def test_remove_by_doc_id(self, gate_env):
        ug.record_hash_index("doc-1", "a" * 64, "b" * 64)
        ug.record_hash_index("doc-2", "c" * 64, "d" * 64)
        ug.remove_hash_index("doc-1")
        assert ug.lookup_hash_index("a" * 64) is None
        assert (ug.lookup_hash_index("c" * 64) or {})["doc_id"] == "doc-2"


# ---------------------------------------------------------------------------
# 5. The gate end-to-end (pure gate level)
# ---------------------------------------------------------------------------

class TestGatePdfUpload:
    def test_clean_admitted(self, gate_env):
        reason, raw_hash = ug.gate_pdf_upload(mk_pdf())
        assert reason is None
        assert len(raw_hash) == 64

    def test_blocked_hash(self, gate_env):
        _, lists = gate_env
        data = mk_pdf()
        h = ug.sha256_hex(data)
        _write_list(lists, "upload_gate_blocked_hashes.json", {"hashes": [h]})
        reason, _ = ug.gate_pdf_upload(data)
        assert reason == ug.REASON_BLOCKED_HASH

    def test_duplicate(self, gate_env):
        data = mk_pdf()
        ug.record_hash_index("existing-doc", ug.sha256_hex(data), None)
        reason, _ = ug.gate_pdf_upload(data)
        assert ug.is_duplicate(reason)

    def test_86a_reject(self, gate_env):
        reason, _ = ug.gate_pdf_upload(
            mk_pdf(text_lines=("ein foto mit ss symbol an der wand",)))
        assert reason == ug.REASON_86A

    def test_reject_message_never_contains_term(self, gate_env):
        # No curated §86a term may surface in the rejection answer.
        import json as _json

        msg = ug.reject_message(ug.REASON_86A).lower()
        inventory = _json.loads(
            (Path(__file__).resolve().parents[1] / "schemas"
             / "stage1_86a_critical_bilingual.json").read_text(encoding="utf-8")
        )
        terms = inventory["filters"]["stage1_critical_86a"]["terms_by_language"]
        for lang_terms in terms.values():
            for term in lang_terms:
                assert term.lower() not in msg, term

    def test_audit_line_has_no_content(self, gate_env):
        import config

        ug.audit_rejection("e" * 64, ug.REASON_86A, "knowledge/upload")
        audit = (Path(config.EXPORTS_DIR) / "knowledge_uploads" / "upload_gate_audit.log")
        line = json.loads(audit.read_text(encoding="utf-8").strip())
        assert set(line) == {"ts", "doc_hash", "reason", "origin"}
        assert line["doc_hash"] == "e" * 64
        assert line["reason"] == ug.REASON_86A


# ---------------------------------------------------------------------------
# 6. Reduced image gate
# ---------------------------------------------------------------------------

class TestGateImageUpload:
    def _png(self):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(buf, format="PNG")
        return buf.getvalue()

    def test_admitted(self, gate_env):
        reason, h = ug.gate_image_upload(self._png())
        assert reason is None and len(h) == 64

    def test_wrong_magic(self, gate_env):
        reason, _ = ug.gate_image_upload(b"BM fake bmp")
        assert reason is not None

    def test_blocked_hash(self, gate_env):
        _, lists = gate_env
        data = self._png()
        _write_list(lists, "upload_gate_blocked_hashes.json",
                    {"hashes": [ug.sha256_hex(data)]})
        reason, _ = ug.gate_image_upload(data)
        assert reason == ug.REASON_BLOCKED_HASH

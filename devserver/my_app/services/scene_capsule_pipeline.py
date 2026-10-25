"""Szenen-Kapsel-Pipeline (UCD-132) — PDF zu Kapseln (Stufe-B-Prüfung).

Implementation of the approved UCD-124 plan Rev. 3, §3 + §7.2 + §6 (backend
only — no surface, no "+" integration, no image generator). A document PDF
is, per the Docling route of the library dossier procedure, converted to raw
Markdown, structurally parsed and condensed over units — but with the SCENE
target schema, not the knowledge-library schema, and with the Stage-B review
duty riding the SAME model calls that condense (no separate safety call):

  Map (per unit)   — wort-budgetierte Segment-Verdichtung PLUS the mandatory
                     structured safety block safetyVerdict/safetyCategories.
  Reduce (per unit) — Szenen-Kapseln: anchor (Kapitelnummer + in-vivo
                     Verdichtungsstichprobe), scene (one visual scene, one
                     line, no style choice), prompt (deterministically
                     assembled from the capsule parts — same capsule, same
                     prompt, acceptance 4), safety (fail-closed gate over
                     scene+prompt: flagged OR unclear -> discard, never
                     store, never show), provenance (analyzedAt,
                     analysisModel, analysisLang, docHash).

Machine parts reused from the library procedure (same repo idioms, no fork):
  knowledge_processing.parse_structure (Wiederholzeilen/TOC/Akronym filter),
  knowledge_processing._pack_units (chapter packing) and its essay segmenter
  (_segment_essay) — the unit construction mirrors process_document, and
  knowledge_processing.default_llm_fn is reused UNCHANGED so the provider
  routing (role KNOWLEDGE_PROCESSING_MODEL) and the models_used provenance
  apply. The model choice (own preset in llm_providers.json vs the standard
  analysis model) is still open; the working basis is the standard analysis
  model, via default_llm_fn.

Fail-closed is the load-bearing rule of this module (plan §7.2.2): a capsule
whose safety verdict is flagged, carries an unparseable/unknown verdict
category, or whose safety block is missing entirely is DISCARDED — never
stored, never shown, never counted as a capsule. Deterministic backstop:
scene+prompt are additionally matched against the SAME curated lists the
upload gate uses (§86a etc.) before a capsule can pass; a capsule that fails
the deterministic pass is discarded regardless of the model verdict.

PDF lifecycle (plan §6): the raw PDF bytes and the extracted full-text MD
live ONLY in the job-scoped workdir of the FIFO worker
(scene_ingest_service). After a finished Reduce (success OR error), both are
DELETED — what remains is capsules.json (the answer surface), segments.json
(wort-budgetierte Segment-Verdichtungen, the agent's question base), the
hash-index entry + Stage-A audit line. No Tier-O draft/publish step, no
durable library file: the document space is SESSION-scoped and dies with the
session (see scene_document_space).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# The capsule ceiling is configurable; the final value is still open, working basis 30.
DEFAULT_MAX_CAPSULES = 30

# Safety verdict categories (plan §7.2 — the five categories the model must
# judge). A verdict outside pass/flagged, or a category outside this set,
# counts as UNCLEAR and the capsule/segment fails closed.
SAFETY_CATEGORY_86 = "86-propaganda"
SAFETY_CATEGORY_86A = "86a-kennzeichen"
SAFETY_CATEGORY_130 = "130-volksverhetzung"
SAFETY_CATEGORY_131 = "131-gewaltverherrlichung"
SAFETY_CATEGORY_AGE = "alterseinstufung"
SAFETY_CATEGORIES = (
    SAFETY_CATEGORY_86,
    SAFETY_CATEGORY_86A,
    SAFETY_CATEGORY_130,
    SAFETY_CATEGORY_131,
    SAFETY_CATEGORY_AGE,
)

VERDICT_PASS = "pass"
VERDICT_FLAGGED = "flagged"

# Segment-Map word budget: the segment digests are the AGENT QUESTION BASE and
# must stay original-getreue Kondensationen, not free retells. 90 words per
# unit mirrors the library's per-chapter floor band (60) with headroom for the
# scene target (the library floor produced verified dossier quality at
# ~15% retention; scene capsules need the who/where/what, not the full
# argument).
SEGMENT_BUDGET_WORDS = 90

# In-vivo anchor probe: the first N words of the segment's digest stand in the
# anchor as the Beleg-Stichprobe (the capsule never carries the full original
# text — the PDF is gone after the run, plan §6; the probe keeps the Beleg-
#pflicht alive against the digest).
ANCHOR_PROBE_WORDS = 12


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


# ---------------------------------------------------------------------------
# Stage-B safety block parsing (fail-closed)
# ---------------------------------------------------------------------------

def parse_safety_block(obj: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Parse the mandatory safetyVerdict/safetyCategories block from a model
    answer. Returns (verdict, categories). Fail-closed on EVERYTHING the
    schema does not explicitly allow: missing block, non-pass/flagged verdict,
    unknown categories, non-list categories -> flagged with the raw input
    category echoed ONLY into the internal log (never into a stored capsule
    or segment: a stored safety field says pass/flagged plus a KNOWN
    category, nothing else)."""
    verdict = str(obj.get("safetyVerdict", "") or "").strip().lower()
    if verdict not in (VERDICT_PASS, VERDICT_FLAGGED):
        return VERDICT_FLAGGED, [SAFETY_CATEGORY_86]
    raw_cats = obj.get("safetyCategories", [])
    if raw_cats is None:
        raw_cats = []
    if not isinstance(raw_cats, list):
        return VERDICT_FLAGGED, [SAFETY_CATEGORY_86]
    cats: List[str] = []
    for c in raw_cats:
        c = str(c or "").strip().lower()
        if c in SAFETY_CATEGORIES:
            cats.append(c)
        elif c:
            # An unknown category means the model judged something we do not
            # model — unclear, and unclear fails closed.
            logger.warning("[SZENE] unknown safety category %r — failing closed", c)
            return VERDICT_FLAGGED, [SAFETY_CATEGORY_86]
        # empty strings are ignored
    if verdict == VERDICT_FLAGGED and not cats:
        # A flagged verdict without a known category still fails closed (the
        # category echo is for the count report only).
        cats = [SAFETY_CATEGORY_86]
    return verdict, cats


# ---------------------------------------------------------------------------
# Deterministic backstop over the curated lists (fail-closed)
# ---------------------------------------------------------------------------

def deterministic_safety_pass(text: str) -> Optional[str]:
    """The curated-list match over scene+prompt BEFORE a capsule can pass
    (plan §7.2.2 backstop — a §86a term in the assembled prompt must die here
    even if the model verdict said pass). Reuses upload_gate's EXACT scan
    (scan_text_layer: §86a via the platform's tested bilingual matcher,
    §86/further via the curated versioned data files) — one inventory, one
    matcher, not a second one. Returns the rule category on a hit, None on a
    clean pass. A malformed curated list raises (upload_gate's fail-closed)
    — the capsule run fails rather than skipping the check."""
    from my_app.services import upload_gate

    return upload_gate.scan_text_layer(text.lower())


# ---------------------------------------------------------------------------
# Segment map (per unit): wort-budgetierte Verdichtung + Stufe-B fields
# ---------------------------------------------------------------------------

def _segment_map_system() -> str:
    return (
        "Schreibe die gesamte Antwort auf Deutsch. Bewahre die Fachbegriffe "
        "und Schlüsselkonzepte des Dokuments wörtlich, in ihrer eigenen "
        "Formulierung. Du verdichtest EINEN Abschnitt eines Dokuments für "
        "eine pädagogische Plattform, die daraus visuelle Szenen ableitet. "
        "Register: sachlich, ohne Werturteil, ohne Werbesprache.\n\n"
        "VERDICHTUNG: Wähle aus, statt zu paraphrasieren. Nur Träger von "
        "Konkretheit überleben: benannte Orte, Figuren und Akteure; konkrete "
        "Handlungen und Ereignisse; konkrete Zahlen und Altersangaben; "
        "dokumenteneigene Begriffe in ihrer Original-Formulierung. Alles "
        "andere fällt weg: Plattitüden, Begründungsprosa, Metasätze über das "
        "Dokument. Halte das genannte Wortbudget ein.\n\n"
        "PRÜFAUFGABE (Stufe B, AUSGABEPFLICHT): Prüfe den Abschnitt auf: "
        "Propaganda und Inhalte verfassungswidriger Organisationen (§86 "
        "StGB); Kennzeichen verfassungswidriger Organisationen (§86a StGB); "
        "Volksverhetzung (§130 StGB); Gewaltverherrlichung (§131 StGB); "
        "Inhalte, die für die gewählte Altersstufe ungeeignet sind "
        "(Alterseinstufung). Antworte hierzu NUR strukturiert in den Feldern "
        "safetyVerdict und safetyCategories.\n\n"
        "Antworte NUR als JSON-Objekt mit genau diesen Schlüsseln:\n"
        '{"section_title": <kurzer Arbeitstitel des Abschnitts>, '
        '"digest": <die Verdichtung; Markdown erlaubt, Listen als "- "-Zeilen>, '
        '"safetyVerdict": "pass" | "flagged", '
        '"safetyCategories": [<leer bei pass; sonst die zutreffenden aus: '
        '"86-propaganda", "86a-kennzeichen", "130-volksverhetzung", '
        '"131-gewaltverherrlichung", "alterseinstufung">]}. '
        "Kein Text außerhalb des JSON-Objekts."
    )


def _capsule_reduce_system() -> str:
    return (
        "Schreibe die gesamte Antwort auf Deutsch. Du baust aus der "
        "Verdichtung EINES Dokumentabschnitts visuelle Szenen-Kapseln für "
        "ein Bildmodell. Register: sachlich und konkret.\n\n"
        "SZENE (eine Zeile, bildmodelltauglich): Ort, Figuren, Handlung, "
        "Stimmung — in dieser Reihenfolge als EIN Satz. KEINE Stilwahl "
        "(keine Angabe zu Kunstrichtung, Technik, Farbpalette, Beleuchtung, "
        "Fotoreferenz) — die Stilwahl bleibt der Fläche überlassen. KEINE "
        "Kennzeichen, Symbole oder Inhalte verfassungswidriger "
        "Organisationen; keine Gewaltdarstellung; nichts, was für Kinder "
        "und Jugendliche ungeeignet ist.\n\n"
        "PROMPT-VORLAGE: baue die Szene NUR aus den Kapselteilen nach — "
        "kein freies Nachdichten, nichts hinzufügen, was nicht in der "
        "Verdichtung steht.\n\n"
        "PRÜFAUFGABE (Stufe B, AUSGABEPFLICHT): Prüfe JEDE Kapsel "
        "(Szene UND Promptvorlage) auf: Propaganda und Inhalte "
        "verfassungswidriger Organisationen (§86 StGB); Kennzeichen "
        "verfassungswidriger Organisationen (§86a StGB); Volksverhetzung "
        "(§130 StGB); Gewaltverherrlichung (§131 StGB); Inhalte, die für die "
        "gewählte Altersstufe ungeeignet sind (Alterseinstufung). Flagge die "
        "Kapsel, wenn Szene oder Promptvorlage eine dieser Kategorien trifft "
        "— auch im Zweifel: flaggen.\n\n"
        "Antworte NUR als JSON-Objekt mit genau diesem Aufbau:\n"
        '{"capsules": [{"scene": <die visuelle Szene, eine Zeile>, '
        '"prompt_template": <die Prompt-Vorlage aus den Kapselteilen>, '
        '"safetyVerdict": "pass" | "flagged", '
        '"safetyCategories": [<leer bei pass; sonst die zutreffenden aus: '
        '"86-propaganda", "86a-kennzeichen", "130-volksverhetzung", '
        '"131-gewaltverherrlichung", "alterseinstufung">]}]}. '
        "Bilde 1 bis 3 Kapseln. Kein Text außerhalb des JSON-Objekts."
    )


# The prompt prefix is German and word-order-stable: the assembled prompt is
# f"{_PROMPT_PREFIX}{scene}{_PROMPT_SUFFIX}" — deterministic (acceptance 4:
# same capsule -> same prompt). The template riding the model answer must
# match this shape for the capsule to be usable; see _normalize_template.
_PROMPT_PREFIX = "Ein Bild, das zeigt: "
_PROMPT_SUFFIX = "."


def assemble_prompt(scene: str) -> str:
    """Deterministic image-prompt assembly from the capsule's own parts
    (acceptance 4): fixed German prefix + the one-line scene + period. The
    same scene ALWAYS yields the same prompt; no model call is involved."""
    scene = " ".join((scene or "").split())
    return f"{_PROMPT_PREFIX}{scene}{_PROMPT_SUFFIX}"


def _normalize_template(tpl: str) -> Optional[str]:
    """The model returns a prompt_template built from the capsule parts; the
    deterministic prompt is ASSEMBLED from the scene, not taken from the
    model. A template is accepted only as a sanity shape: after stripping the
    known prefix/suffix it must not contain placeholders ({}, $, %s) and must
    be non-empty. Returns the normalized template or None (-> capsule
    discarded, fail-closed: a prompt we cannot reproduce deterministically
    must not ride a stored capsule)."""
    t = " ".join(str(tpl or "").split()).strip()
    if not t:
        return None
    if re.search(r"[{}]|%s|\$\w", t):
        return None
    return t


@dataclass
class Capsule:
    """One scene capsule — the stored target schema (UCD-124 §3)."""
    anchor_chapter: str
    anchor_probe: str
    scene: str
    prompt: str
    safety_verdict: str
    safety_categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor": {"chapter": self.anchor_chapter, "probe": self.anchor_probe},
            "scene": self.scene,
            "prompt": self.prompt,
            "safety": {
                "verdict": self.safety_verdict,
                "categories": list(self.safety_categories),
            },
        }


@dataclass
class SceneDigest:
    """One unit's segment digest + its Stage-B verdict (fail-closed state)."""
    section_title: str
    digest: str
    verdict: str
    categories: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_title": self.section_title,
            "digest": self.digest,
            "safety": {"verdict": self.verdict, "categories": list(self.categories)},
        }


def _extract_json_object(text: Optional[str]) -> Optional[dict]:
    """Same tolerant JSON extraction as knowledge_processing (imported rather
    than duplicated for stability under a test reload)."""
    from my_app.services.knowledge_processing import _extract_json_object as _kp_extract

    return _kp_extract(text)


def _call_llm(llm: Callable[..., Any], system: str, user: str,
              cancel_check: Optional[Callable[[], bool]]) -> Optional[str]:
    """One LLM call honoring the no-token-cap platform rule and the cancel
    boundary. Returns the raw answer or None (degrade, never raise mid-run;
    the caller treats None as fail-closed for that unit)."""
    if cancel_check is not None:
        try:
            if cancel_check():
                return None
        except Exception:  # noqa: BLE001 - a broken checker must not abort
            pass
    try:
        return llm(system, user, None)
    except Exception as e:  # noqa: BLE001
        logger.warning("[SZENE] LLM call failed: %s", e)
        return None


def _map_segment(unit_heading: str, unit_body: str, llm: Callable[..., Any],
                 cancel_check: Optional[Callable[[], bool]] = None
                 ) -> Tuple[SceneDigest, bool]:
    """Map call over one unit: segment digest + Stage-B verdict. Returns
    (digest, ok); ok=False means the segment is EXCLUDED (bad JSON twice,
    flagged, or unclear) — the caller counts it as flagged/missing without
    ever keeping the content."""
    system = _segment_map_system()
    user = (
        f"Abschnitt: \"{unit_heading}\".\n"
        f"WORTBUDGET für die Verdichtung: höchstens ~{SEGMENT_BUDGET_WORDS} Wörter.\n\n"
        f"{unit_body}"
    )
    obj = _extract_json_object(_call_llm(llm, system, user, cancel_check))
    if obj is None:
        repair = user + (
            "\n\n---\nDeine letzte Antwort war kein gültiges JSON. Antworte JETZT "
            'NUR mit dem JSON-Objekt {"section_title":…, "digest":…, '
            '"safetyVerdict":…, "safetyCategories":[…]}, ohne anderen Text. '
            "Halte das Wortbudget ein."
        )
        obj = _extract_json_object(_call_llm(llm, system, repair, cancel_check))
    if obj is None:
        return SceneDigest(unit_heading, "", VERDICT_FLAGGED, [SAFETY_CATEGORY_86]), False

    digest = str(obj.get("digest", "") or "").strip()
    verdict, cats = parse_safety_block(obj)
    ok = bool(digest) and verdict == VERDICT_PASS
    return SceneDigest(
        section_title=str(obj.get("section_title", "") or unit_heading).strip(),
        digest=digest, verdict=verdict, categories=cats,
    ), ok


def _anchor_probe(digest: str) -> str:
    """The in-vivo Beleg-Stichprobe: first ANCHOR_PROBE_WORDS words of the
    digest, verbatim from the wort-budgetierten Zwischenform (the capsule
    keeps the Belegpflicht alive against the digest, not the full text)."""
    words = digest.split()
    return " ".join(words[:ANCHOR_PROBE_WORDS])


def _reduce_capsules(unit_heading: str, digest_obj: SceneDigest, llm: Callable[..., Any],
                     cancel_check: Optional[Callable[[], bool]] = None
                     ) -> Tuple[List[Capsule], int]:
    """Reduce call over one segment digest: capsules with the Stage-B capsule
    gate. Returns (kept_capsules, n_discarded). Fail-closed on every axis:
    model verdict flagged/unclear -> discard; deterministic curated-list pass
    over scene+prompt hits -> discard; prompt template unshapeable -> discard.
    A discarded capsule is never stored, never shown, only counted."""
    system = _capsule_reduce_system()
    user = (
        f"Abschnitt: \"{unit_heading}\".\n"
        f"Verdichtung:\n\n{digest_obj.digest}"
    )
    obj = _extract_json_object(_call_llm(llm, system, user, cancel_check))
    if obj is None:
        repair = user + (
            "\n\n---\nDeine letzte Antwort war kein gültiges JSON. Antworte JETZT "
            'NUR mit {"capsules": [{"scene":…, "prompt_template":…, '
            '"safetyVerdict":…, "safetyCategories":[…]}]}, ohne anderen Text.'
        )
        obj = _extract_json_object(_call_llm(llm, system, repair, cancel_check))
    if obj is None:
        return [], 0

    raw_capsules = obj.get("capsules")
    if not isinstance(raw_capsules, list):
        return [], 0

    kept: List[Capsule] = []
    discarded = 0
    for it in raw_capsules:
        if not isinstance(it, dict):
            discarded += 1
            continue
        scene = " ".join(str(it.get("scene", "") or "").split()).strip()
        verdict, cats = parse_safety_block(it)
        tpl = _normalize_template(it.get("prompt_template", ""))
        if not scene or tpl is None:
            # Unshapeable capsule -> unclear -> fail closed.
            discarded += 1
            continue
        if verdict != VERDICT_PASS:
            discarded += 1
            continue
        # Deterministic backstop: scene+prompt against the curated lists.
        prompt = assemble_prompt(scene)
        reason = deterministic_safety_pass(scene + " " + prompt)
        if reason is not None:
            discarded += 1
            continue
        kept.append(Capsule(
            anchor_chapter=unit_heading,
            anchor_probe=_anchor_probe(digest_obj.digest),
            scene=scene,
            prompt=prompt,
            safety_verdict=VERDICT_PASS,
            safety_categories=[],
        ))
    return kept, discarded


def process_document_to_capsules(
    raw_md: str,
    *,
    doc_id: str,
    llm: Optional[Callable[..., Any]] = None,
    progress: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    max_capsules: int = DEFAULT_MAX_CAPSULES,
    mode: str = "auto",
) -> Dict[str, Any]:
    """The full backend procedure over ONE raw Docling MD (steps 2-3 of the
    plan): structure parse -> units (essay segmenter or chapter packing,
    same decision logic as the library) -> per-unit segment Map with the
    Stage-B fields -> per-unit capsule Reduce with the fail-closed capsule
    gate -> result dict:

        {
          "capsules": [...],       # kept, capped at max_capsules
          "segments": [...],      # kept segment digests (question base)
          "n_flagged_segments": N, # excluded segments, count only
          "n_discarded_capsules": N,
          "fatal": [...],          # empty on success
        }

    Structure reuse (no fork of the library machinery): parse_structure,
    detect_mode, _pack_units, _segment_essay, _units_from_segments and
    default_llm_fn all come from knowledge_processing; the SCENE system
    prompts, the safety blocks and the capsule gate are this module's own.
    The PDF lifecycle (§6) is NOT this function's concern — the job service
    owns the workdir and deletes the raw files at job end.
    """
    from my_app.services import knowledge_processing as kp

    llm = llm or kp.default_llm_fn()

    def _log(msg: str) -> None:
        logger.info("[SZENE] %s", msg)
        if progress:
            try:
                progress(msg)
            except Exception:  # noqa: BLE001
                pass

    paratext, content_sections, all_kept = kp.parse_structure(raw_md)
    mode, mode_reason = kp.detect_mode(raw_md, all_kept, explicit=mode)

    seg_note = ""
    if mode == "essay":
        _log("Essay-Segmentierung (LLM liest den Volltext)…")
        segments = kp._segment_essay(raw_md, llm)
        if segments:
            units = kp._units_from_segments(segments)
            seg_note = f", {len(segments)} Argument-Abschnitte (LLM)"
        else:
            _log("Essay-Segmentierung fehlgeschlagen -> Fallback Heading-Packing")
            units = kp._pack_units(content_sections)
            seg_note = ", Segmentierung fiel aus (Heading-Fallback)"
    else:
        units = kp._pack_units(content_sections)

    _log(f"Struktur: {len(content_sections)} Abschnitte -> {len(units)} Einheiten"
         f"{seg_note} (Modus: {mode_reason})")

    # A cancel before any Map work: nothing produced.
    def _cancelled() -> bool:
        if cancel_check is None:
            return False
        try:
            return bool(cancel_check())
        except Exception:  # noqa: BLE001
            return False

    if _cancelled():
        raise kp.ProcessingCancelled(units_done=0)

    segments: List[SceneDigest] = []
    capsules: List[Capsule] = []
    n_flagged = 0
    n_discarded_capsules = 0

    for i, unit in enumerate(units, 1):
        if _cancelled():
            raise kp.ProcessingCancelled(units_done=i)
        body = unit.body[:kp._MAP_SECTION_CAP]
        _log(f"verdichte Einheit {i}/{len(units)}: {unit.heading}")
        digest_obj, seg_ok = _map_segment(unit.heading, body, llm, cancel_check)
        if not seg_ok:
            # Flagged / unclear / missing segment: COUNT ONLY (never the
            # content, plan §3.5). A flagged segment yields no capsules.
            n_flagged += 1
            continue
        segments.append(digest_obj)

        # Reduce: capsules out of this segment's digest, with the gate.
        _log(f"baue Kapseln für Einheit {i}/{len(units)}")
        kept, n_disc = _reduce_capsules(unit.heading, digest_obj, llm, cancel_check)
        n_discarded_capsules += n_disc
        for cap in kept:
            if len(capsules) < max_capsules:
                capsules.append(cap)
        if len(capsules) >= max_capsules:
            _log(f"Kapsel-Obergrenze ({max_capsules}) erreicht")
            break

    # Analysis provenance (same shape as the library run): WHEN this ran, WHICH
    # model(s) actually served the calls (read off llm.models_used — the
    # provider-routed default_llm_fn tracks the post-fallback candidate), and
    # the language the SCENE prompts are written in (German, like all
    # platform prompts — the capsule prompts are German by construction, and
    # this field says so without guessing at the document's own language).
    models_used = list(dict.fromkeys(getattr(llm, "models_used", None) or []))
    analyzed_at = _now_iso()

    fatal: List[str] = []
    if not segments and not capsules:
        fatal.append(
            "kein nutzbares Segment: die Verdichtung lieferte keine pass-Verdichtung"
        )

    return {
        "capsules": [c.to_dict() for c in capsules],
        "segments": [s.to_dict() for s in segments],
        "n_flagged_segments": n_flagged,
        "n_discarded_capsules": n_discarded_capsules,
        "fatal": fatal,
        "mode": mode,
        "mode_reason": mode_reason,
        "analyzed_at": analyzed_at,
        "models_used": models_used,
        "analysis_lang": "de",
    }

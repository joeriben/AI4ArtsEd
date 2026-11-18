"""
The adversarial review of a summary (knowledge_review), with a fake
reviewer: one call per unit (a document of library size is one unit), a
structured verdict in the front matter and the sidecar, draft on a material
finding or a unit without a usable answer, and the retention step reading the
recorded verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

from my_app.services import knowledge_checks as kc
from my_app.services import knowledge_processing as kp
from my_app.services import knowledge_retention as kr
from my_app.services import knowledge_review as krv
from my_app.services.knowledge_extract import Block, Extraction, from_markdown

_MD = """## Ablauf

Die Einheit umfasst 6–8 Doppelstunden zu je 90 Minuten im Kunstraum der Schule.

- Beobachten der Vorlage
- Zeichnen des eigenen Monsters
- Generieren mit dem Bildmodell
- Besprechen in der Gruppe
"""

_SUMMARY = ("## Ablauf\n\nUmfang: 6–8 Doppelstunden à 90 Minuten.\n\n"
            "- Vorlage ansehen\n- eigenes Monster zeichnen\n- Bildmodell nutzen\n"
            "- Gruppengespräch")

_EMPTY = {"omissions": [], "distortions": [], "additions": []}


def _stub(review_answers, calls=None):
    """Summary/type/profile answers for a passing summary; the review calls
    are answered from `review_answers` in turn (the last one repeats)."""
    answers = list(review_answers)

    def llm(system, user, max_tokens=None):
        if "REFUTE" in system:
            if calls is not None:
                calls.append(user)
            a = answers.pop(0) if len(answers) > 1 else answers[0]
            return a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)
        if system.startswith("You classify"):
            return json.dumps({"type": "practice_report", "language": "de", "reason": "x"})
        if "PROFILE" in system:
            return "Praxisbericht zu einer Unterrichtseinheit."
        return _SUMMARY
    return llm


def _fm():
    return {"id": "review-doc", "titel": "Monster-Test", "sprache": "de",
            "status": "published", "lizenz": "Alle Rechte vorbehalten"}


def test_review_without_material_findings_passes_and_publishes_a_reprocess():
    calls = []
    minor = dict(_EMPTY, additions=[{"summary": "Gruppengespräch", "severity": "minor"}])
    res = kp.process_document(from_markdown(_MD), _fm(), llm=_stub([minor], calls), hold="")
    assert len(calls) == 1                       # one call per unit
    assert "=== SOURCE ===" in calls[0] and "=== SUMMARY ===" in calls[0]
    assert "Doppelstunden zu je 90 Minuten" in calls[0] and "### Ablauf" in calls[0]
    assert res.checks == "passed" and res.review_passed
    assert res.status == "published"
    assert "review: passed" in res.markdown
    assert res.review["counts"]["additions"] == {"material": 0, "minor": 1}
    assert res.review["sections"][0]["additions"][0]["summary"] == "Gruppengespräch"


def test_material_finding_holds_the_document_in_draft():
    finding = dict(_EMPTY, omissions=[{"source": "im Kunstraum der Schule", "page": None,
                                        "severity": "material"}])
    res = kp.process_document(from_markdown(_MD), _fm(), llm=_stub([finding]))
    assert res.checks == "passed"                # the checks alone would publish
    assert not res.review_passed and res.status == "draft"
    assert "status: draft" in res.markdown and res.status_reason == "review, release"
    assert res.review["label"] == "failed: 1 material omissions"
    assert "1 material omissions" in res.markdown
    assert "omissions: 1 material, 0 minor" in res.review["note"]


_CORRECTION = "A check of your summary against the document found"


def _correcting(base, answer, corrections):
    """`base` for every call but the correction call, which is recorded in
    `corrections` and answered with `answer`."""
    def llm(system, user, max_tokens=None):
        if _CORRECTION in user:
            corrections.append(user)
            return answer
        return base(system, user, max_tokens)
    return llm


def test_a_correction_that_leaves_fewer_defects_is_kept_and_publishes():
    finding = dict(_EMPTY, omissions=[{"source": "im Kunstraum der Schule", "page": None,
                                        "severity": "material"}])
    corrections, reviews = [], []
    fixed = _SUMMARY.replace("90 Minuten.", "90 Minuten im Kunstraum.")
    res = kp.process_document(from_markdown(_MD), _fm(), hold="", llm=_correcting(
        _stub([finding, _EMPTY], reviews), fixed, corrections))
    assert len(corrections) == 1 and len(reviews) == 2   # the unit is reviewed again
    assert 'Left out: the document says "im Kunstraum der Schule"' in corrections[0]
    assert "Your summary:" in corrections[0] and "Gruppengespräch" in corrections[0]
    assert res.review_passed and res.status == "published"
    assert "90 Minuten im Kunstraum." in res.markdown


def test_a_correction_that_does_not_lower_the_defects_is_discarded():
    finding = dict(_EMPTY, omissions=[{"source": "im Kunstraum der Schule", "page": None,
                                        "severity": "material"}])
    corrections = []
    res = kp.process_document(from_markdown(_MD), _fm(), llm=_correcting(
        _stub([finding]), _SUMMARY.replace("Gruppengespräch", "Plenum"), corrections))
    assert len(corrections) == kp._CORRECTION_ROUNDS
    assert res.status == "draft" and "Plenum" not in res.markdown
    assert "Gruppengespräch" in res.markdown


def _verbatim(share):
    return kc.CheckResult("verbatim_share", kc.COPYRIGHT, share <= 0.20, f"share {share:.1%}",
                          value=share, limit=0.20)


def _verdict(material):
    findings = [{"source": "x", "severity": "material"}] * material
    return krv.ReviewVerdict(reviewer="r", at="t", sections=[krv.SectionReview(
        index=1, section="Ablauf", answered=True, omissions=findings)])


def test_a_lower_verbatim_share_over_the_ceiling_is_kept():
    before = kc.CheckReport([_verbatim(0.251)])
    assert kp._improves(before, _verdict(0), kc.CheckReport([_verbatim(0.212)]), _verdict(0))
    assert not kp._improves(before, _verdict(0),
                            kc.CheckReport([_verbatim(0.262)]), _verdict(0))
    # As many defects, the share lower, but a material finding for a failed
    # page reference: discarded.
    pages = kc.CheckResult("page_refs", kc.QUALITY, False, "1 wrong")
    assert not kp._improves(kc.CheckReport([_verbatim(0.251), pages]), _verdict(0),
                            kc.CheckReport([_verbatim(0.212)]), _verdict(1))
    # Under the ceiling it is one defect fewer, kept as before.
    assert kp._improves(before, _verdict(0), kc.CheckReport([_verbatim(0.18)]), _verdict(0))


def test_copied_passages_go_back_to_the_correction_call():
    copied = ("## Ablauf\n\nDie Einheit umfasst 6–8 Doppelstunden zu je 90 Minuten im "
              "Kunstraum der Schule.\n\n- Vorlage ansehen\n- Gruppengespräch")
    corrections = []
    base = _stub([_EMPTY])

    def llm(system, user, max_tokens=None):
        if _CORRECTION in user:
            corrections.append(user)
            return _SUMMARY
        if "REFUTE" in system or system.startswith("You classify") or "PROFILE" in system:
            return base(system, user, max_tokens)
        return copied
    res = kp.process_document(from_markdown(_MD), _fm(), llm=llm, hold="")
    assert len(corrections) == 1
    assert "- Copied:" in corrections[0] and "Doppelstunden zu je 90 Minuten" in corrections[0]
    assert res.checks == "passed" and res.status == "published"
    assert "Doppelstunden zu je 90 Minuten" not in res.markdown


def test_the_page_a_statement_is_assigned_to_is_not_reviewed():
    """The reviewer is not asked about page assignment (#139), and a page
    finding a reviewer sends anyway is not taken into the verdict."""
    system = krv._system(True)
    assert "wrong_page_refs" not in system
    assert "which page a statement of the summary is assigned to" in system
    assert "[S. 5]" in system and "[S. 5]" not in krv._system(False)
    stray = dict(_EMPTY, wrong_page_refs=[{"summary": "(S. 4)", "given": 4,
                                            "severity": "material"}])
    res = kp.process_document(from_markdown(_MD), _fm(), llm=_stub([stray]), hold="")
    assert res.review_passed and res.status == "published"
    assert "wrong_page_refs" not in res.review["sections"][0]


def test_an_unusable_answer_is_sent_back_once_and_then_fails_closed():
    calls = []
    res = kp.process_document(from_markdown(_MD), _fm(),
                              llm=_stub(["Alles korrekt.", "Keine Befunde."], calls))
    assert len(calls) == 2                       # the call and one repair request
    assert "not the JSON object" in calls[1]
    assert not res.review_passed and res.status == "draft"
    assert res.review["sections"][0]["answered"] is False
    assert "not reviewed" in res.review["label"]


def test_the_repair_answer_counts_when_it_is_usable():
    res = kp.process_document(from_markdown(_MD), _fm(), llm=_stub(["kein JSON", _EMPTY]),
                              hold="")
    assert res.review_passed and res.status == "published"


def test_a_separate_reviewer_gets_the_review_calls():
    calls = []
    reviewer = _stub([_EMPTY], calls)
    res = kp.process_document(from_markdown(_MD), _fm(), llm=_stub(["never"]),
                              review_llm=reviewer)
    assert len(calls) == 1 and res.review_passed


def test_review_false_makes_no_review_and_records_none():
    calls = []
    res = kp.process_document(from_markdown(_MD), _fm(), llm=_stub([_EMPTY], calls),
                              review=False, hold="")
    assert calls == [] and res.review == {}
    assert "\nreview:" not in res.markdown
    assert res.status == "draft" and res.status_reason == "no_review"


def test_the_source_carries_page_markers_and_image_descriptions_go_along():
    blocks = [Block("heading", text="Ablauf", level=2, page=3, seq=0),
              Block("paragraph", text=_MD.split("\n\n")[1], page=3, seq=1),
              Block("figure", page=4, seq=2, figure_no="1", caption="Skizze", image="f.png")]
    ext = Extraction(blocks=blocks, pages=4, source="docling")
    calls = []
    res = kp.process_document(ext, _fm(), llm=_stub([_EMPTY], calls),
                              figure_descriptions={2: "Eine Bleistiftzeichnung."})
    assert res.review_passed
    assert "[S. 3]" in calls[0] and "[S. 4]" in calls[0]
    assert "IMAGE DESCRIPTIONS" in calls[0] and "Abb. 1: Eine Bleistiftzeichnung." in calls[0]



def test_image_descriptions_are_checked_against_what_the_source_says():
    """The reviewer checks a description against the caption and the passage
    that refers to the figure; a passage outside the section goes along."""
    system = krv._system(True)
    assert "not under review" not in system
    assert "contradicts the source" in system and "report a distortion" in system
    blocks = [Block("heading", text="Einleitung", level=2, page=1, seq=0),
              Block("paragraph", text="Abb. 1 zeigt das Wort BLUT auf einer Wand. "
                    + " ".join(f"a{i}" for i in range(1500)), page=1, seq=1),
              Block("heading", text="Material", level=2, page=4, seq=2),
              Block("paragraph", text=" ".join(f"b{i}" for i in range(1500)), page=4, seq=3),
              Block("figure", page=4, seq=4, figure_no="1", caption="Abb. 1: Wand",
                    image="f.png")]
    units = kp.build_units(blocks)
    assert [u.heading for u in units] == ["Einleitung", "Material"]
    digests = [kp.SectionDigest(abschnitt_de=u.heading, verdichtung="Inhalt.", begriffe=[],
                                source_heading=u.heading, unit_index=u.index) for u in units]
    sections = kp.review_sections(units, digests, "de", True, {4: "Das Wort SLUT auf einer Wand."})
    fig_section = next(s for s in sections if s.image_descriptions)
    line = fig_section.image_descriptions[0]
    assert line.startswith("Abb. 1: Das Wort SLUT auf einer Wand.")
    assert "Abb. 1 zeigt das Wort BLUT auf einer Wand." in line
    assert "checked against the source" in krv._user(fig_section)

def test_an_order_finding_without_a_summary_quote_does_not_hold_the_document():
    """#140: the extraction's order differs from the text layer, the summary
    gives the source right; the reviewer reports `order` with no summary
    quote. It is recorded as minor and the review passes."""
    section = krv.ReviewSection(index=0, heading="Ablauf (S. 3)", document="[S. 3]\nB. A.\n\n",
                                output="### Ablauf\n\nA, dann B.", layer="[S. 3]\nA. B.")

    def llm(system, user, max_tokens=None):
        return json.dumps(dict(_EMPTY, order=[{"source": "B. A.", "layer": "A. B.",
                                               "summary": "", "severity": "material"}]))
    review = krv.review_section(section, llm, has_pages=True)
    assert review.order[0]["severity"] == "minor"
    assert krv.ReviewVerdict(reviewer="model: x", sections=[review]).passed
    assert krv.finding_severity("order", "minor", {"summary": "B, dann A."}) == "material"
    assert krv.finding_severity("omissions", "minor", {"summary": "x"}) == "minor"


def test_the_text_layer_goes_along_and_an_order_finding_quoting_the_summary_is_material():
    section = krv.ReviewSection(index=0, heading="Ablauf (S. 3)", document="[S. 3]\nB. A.\n\n",
                                output="### Ablauf\n\nB, dann A.", layer="[S. 3]\nA. B.")
    calls = []

    def llm(system, user, max_tokens=None):
        calls.append((system, user))
        return json.dumps(dict(_EMPTY, order=[{"summary": "B, dann A.", "layer": "A. B.",
                                               "severity": "minor"}]))
    review = krv.review_section(section, llm, has_pages=True)
    assert "TEXT LAYER" in calls[0][0] and "TEXT LAYER (second reading" in calls[0][1]
    assert "[S. 3]\nA. B." in calls[0][1]
    assert review.order[0]["severity"] == "material" and review.order[0]["layer"] == "A. B."
    assert not krv.ReviewVerdict(reviewer="model: x", sections=[review]).passed
    # Without a layer the instruction stays out of the call.
    assert "TEXT LAYER" not in krv._system(True, False)


def test_the_sidecar_carries_the_verdict_and_retention_reads_it(tmp_path):
    lib = tmp_path / "lib"
    src = tmp_path / "src" / "operator" / "kunst"
    src.mkdir(parents=True)
    ext = from_markdown(_MD)
    passed = kp.process_document(ext, dict(_fm(), id="ok-doc"), llm=_stub([_EMPTY]))
    failed = kp.process_document(ext, dict(_fm(), id="bad-doc"), llm=_stub(
        [dict(_EMPTY, distortions=[{"summary": "6–8", "source": "6–8",
                                    "severity": "material"}])]))
    for res in (passed, failed):
        md = kp.write_library_file(res, lib / f"{res.doc_id}.md", ext)
        (src / f"{res.doc_id}.pdf").write_bytes(b"%PDF")
        side = kc.read_sidecar(kc.sidecar_path(md))
        assert side["passed"] is True                    # the checks
        assert side["review"]["passed"] is res.review_passed
        assert side["review"]["reviewer"].startswith("model: ")
        assert side["review"]["at"]
    plan = {i.doc_id: i for i in kr.plan_retention([lib], source_root=tmp_path / "src",
                                                   work_root=None, originals_dir=None)}
    assert plan["ok-doc"].action == "remove"
    assert plan["bad-doc"].action == "keep"
    assert plan["bad-doc"].reason == "no passed adversarial review recorded"


def test_a_new_file_without_review_does_not_inherit_the_old_verdict(tmp_path):
    ext = from_markdown(_MD)
    md = tmp_path / "doc.md"
    kp.write_library_file(kp.process_document(ext, _fm(), llm=_stub([_EMPTY])), md, ext)
    assert kc.read_sidecar(kc.sidecar_path(md))["review"]["passed"]
    kp.write_library_file(kp.process_document(ext, _fm(), llm=_stub([_EMPTY]), review=False),
                          md, ext)
    assert "review" not in kc.read_sidecar(kc.sidecar_path(md))


def test_plan_document_counts_the_review_calls():
    plan = kp.plan_document(from_markdown(_MD), _fm())
    assert plan["totals"]["review_calls"] == len(plan["units"]) == 1
    assert plan["totals"]["review_input_chars_max"] > 2 * len("Doppelstunden zu je 90 Minuten")
    assert plan["totals"]["review_input_chars_max"] == plan["review_calls"][0]["input_chars_max"]
    assert plan["totals"]["correction_calls_max"] == kp._CORRECTION_ROUNDS
    assert plan["totals"]["correction_review_calls_max"] == kp._CORRECTION_ROUNDS


def test_findings_text_lists_each_finding_and_the_unreviewed():
    v = krv.ReviewVerdict(reviewer="model: x", sections=[
        krv.SectionReview(0, "Ablauf (S. 3)", True,
                          omissions=[{"source": "Kunstraum", "page": 3, "severity": "material"}]),
        krv.SectionReview(1, "Schluss", False)])
    text = krv.findings_text(v.to_dict())
    assert '[Ablauf (S. 3)] omissions (material): {"source": "Kunstraum", "page": 3}' in text
    assert "[Schluss] NOT REVIEWED" in text
    assert not v.passed


# Two sections of about equal size; with the unit ceiling lowered below
# their sum (test below) the document is cut into two parts at the heading.
_TWO_SECTIONS_MD = (_MD + "\n" + "Die Gruppe arbeitet im Kunstraum. " * 80
                    + "\n\n## Auswertung\n\n"
                    + "Die Gruppe bespricht die Bilder des Bildmodells. " * 60 + "\n")


def test_a_written_condensation_is_reviewed_again_with_the_sections_the_first_review_read(
        monkeypatch):
    """review_condensation reads the units back from the file (the inverse
    of assemble_markdown) and gives a second reviewer the same input the
    review in process_document had; the file stays as it is."""
    monkeypatch.setattr(kp, "_DOC_UNIT_MAX_CHARS", 4000)
    ext = from_markdown(_TWO_SECTIONS_MD)
    first = []
    res = kp.process_document(ext, _fm(), llm=_stub([_EMPTY], first), hold="")
    assert len(first) == 2
    second = []
    reviewer = _stub([_EMPTY], second)
    reviewer.models_used = ["openrouter/anthropic/claude-opus-5.5"]
    verdict = kp.review_condensation(ext, res.markdown, reviewer, title=_fm()["titel"],
                                     lang="de", source_lang="de")
    assert second == first
    assert verdict.passed and verdict.reviewer == "model: openrouter/anthropic/claude-opus-5.5"


def test_ask_hands_the_document_apart_only_to_a_function_that_takes_it():
    seen = []

    def plain(system, user, max_tokens=None):
        seen.append(("plain", system, user))
        return "a"

    def cached(system, user, max_tokens=None, document=None, cache_ttl=""):
        seen.append(("cached", system, user, document, cache_ttl))
        return "b"
    cached.takes_document = True

    assert krv.ask(plain, "S", "U", "DOC\n\n", "1h") == "a"
    assert krv.ask(cached, "S", "U", "DOC\n\n", "1h") == "b"
    assert krv.ask(cached, "S", "U") == "b"
    assert seen == [("plain", "S", "DOC\n\nU"),
                    ("cached", "S", "U", "DOC\n\n", "1h"),
                    ("cached", "S", "U", None, "")]


def test_an_anchor_that_names_no_unit_is_refused():
    ext = from_markdown(_MD)
    res = kp.process_document(ext, _fm(), llm=_stub([_EMPTY]), hold="")
    units = kp.build_units(kp.clean_blocks(ext, _fm()["titel"])[0], _fm()["titel"])
    assert [d.unit_index for d in kp.digests_from_markdown(res.markdown, units)] == [0]
    moved = res.markdown.replace("<!-- quelle: Ablauf", "<!-- quelle: Ablauf, anders")
    try:
        kp.digests_from_markdown(moved, units)
    except ValueError as e:
        assert "names no unit" in str(e)
    else:
        raise AssertionError("an anchor of another extraction was taken")

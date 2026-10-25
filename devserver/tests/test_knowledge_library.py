"""
Tests for the knowledge library (Tier F): the offline index build +
the read-only runtime service + the two Resona-scoped tools.

Since the Verdichtungs-Umbau (BIBLIOTHEK.md §3, 2026-07-04) the library form is
the COMPACT one: front-matter + ## PROFIL + ## WISSEN (### subsections) +
## GLOSSAR. Full source text (## DOCUMENT) is never present, never indexed.

Covers:
- a tiny fixture corpus (2 docs, one status=draft) -> build the index
- search: finds the published doc, the draft is invisible
- facet filter (sparte) narrows results
- read: returns the WISSEN passage + source metadata (title, year, lizenz, url);
  a draft doc_id is refused
- missing index -> the defined "not built" error string (not a crash)
- policy: a doc without `lizenz` in front-matter is skipped by the index build
- no full-text marker: no library file may carry a ## DOCUMENT section
- scope: get_openai_format(scope='resona') exposes lookup_knowledge +
  read_knowledge; scope=None does NOT (non-inheriting); the universal∩resona
  intersection stays exactly lookup_reference + lookup_interception.

Run: python3 -m pytest devserver/tests/test_knowledge_library.py -q
(from the worktree root; also works from devserver/ directly)
"""

import config
import importlib
import sys
from pathlib import Path
from file_modules import load_index_builder

# devserver/tests/... -> parents[1] == devserver/ (same convention as the
# other resona tests / chat_routes.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


# ---------------------------------------------------------------------------
# Import the offline builder from devserver/scripts (not a package)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fixture corpus (compact Verdichtung form)
# ---------------------------------------------------------------------------

_DOC_PUBLISHED = """---
id: unesco-mini-published-2010
titel: "Mini Framework for Arts Education"
autor: UNESCO
jahr: 2010
sprache: en
tier: F
sparten: [performativ, bildnerisch]
themen: [arts_education, policy]
lizenz: "CC BY-SA 3.0 IGO"
url: "https://unesdoc.unesco.org/ark:/48223/pf0000000001"
status: published
---

# Mini Framework for Arts Education

## PROFIL

Arts education is a right and a driver of creativity across the curriculum. The
document builds on the human-rights-in-education discourse and applies to
performative and visual practice in Sek I/II.

## WISSEN

### Introduction

The framework sets out why arts education matters and how creativity can be
built across the curriculum. It affirms the human right to education and to
cultural participation for every learner.

<!-- quelle: Introduction -->

### Aims

The four aims of arts education are: upholding the human right to education and
cultural participation; developing individual capabilities; improving the
quality of education; and promoting the expression of cultural diversity.

<!-- quelle: Aims -->

## GLOSSAR

- **creativity** — the capacity to generate ideas and forms that are novel and valuable.
- **cultural participation** — taking active part in the cultural life of a community.
"""

_DOC_DRAFT = """---
id: unesco-mini-draft-2011
titel: "Draft Note on Assessment"
autor: UNESCO
jahr: 2011
sprache: en
tier: F
sparten: [medial]
themen: [assessment]
lizenz: "CC BY-SA 3.0 IGO"
url: "https://unesdoc.unesco.org/ark:/48223/pf0000000002"
status: draft
---

# Draft Note on Assessment

## PROFIL

A draft note on assessment in arts education, not yet reviewed.

## WISSEN

### Assessment

This draft note about assessment in arts education mentions creativity and
should remain invisible to the running service until it is published.

<!-- quelle: Assessment -->
"""

_DOC_NO_LICENSE = """---
id: unesco-mini-nolicense
titel: "No License Doc"
autor: UNESCO
jahr: 2012
sprache: en
tier: F
sparten: [bildnerisch]
themen: [misc]
status: published
---

# No License Doc

## PROFIL

This document is missing a lizenz field and must be skipped by the index build.

## WISSEN

### Body

Some body text.

<!-- quelle: Body -->
"""


@pytest.fixture()
def corpus(tmp_path):
    """Write the fixture Markdown corpus into a temp 'library' dir."""
    lib = tmp_path / "library" / "unesco"
    lib.mkdir(parents=True)
    (lib / "unesco-mini-published-2010.md").write_text(_DOC_PUBLISHED, encoding="utf-8")
    (lib / "unesco-mini-draft-2011.md").write_text(_DOC_DRAFT, encoding="utf-8")
    (lib / "unesco-mini-nolicense.md").write_text(_DOC_NO_LICENSE, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def built_db(corpus, tmp_path, monkeypatch):
    """Build the index over the fixture corpus and point the runtime service at it."""
    b = load_index_builder()
    db_path = tmp_path / "knowledge_index.sqlite"
    docs = b.scan_library(corpus / "library", None)
    counts = b.build(db_path, docs)

    # Point the runtime service at the freshly built index: it reads
    # config.KNOWLEDGE_INDEX_DB at call time (finding S-077 of the code review of 2026-10-10).
    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db_path, raising=False)
    kl._QUERY_TRANSLATION_CACHE.clear()
    return kl, counts


# ---------------------------------------------------------------------------
# Index build policy
# ---------------------------------------------------------------------------

def test_build_skips_doc_without_license(built_db):
    _, counts = built_db
    # 3 fixture files, but the no-license one is skipped -> 2 docs indexed.
    assert counts["docs"] == 2


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def test_search_finds_published(built_db):
    kl, _ = built_db
    result = kl.search("creativity arts education")
    assert "unesco-mini-published-2010" in result


def test_search_hides_draft(built_db):
    kl, _ = built_db
    # 'creativity' appears in BOTH the published and the draft doc; only the
    # published one may surface.
    result = kl.search("creativity")
    assert "unesco-mini-published-2010" in result
    assert "unesco-mini-draft-2011" not in result


def test_search_facet_filter(built_db):
    kl, _ = built_db
    # thema/sparte are NON-exclusive (soft-boost, commit 67b5696d): a facet
    # re-ranks toward docs that carry it but never HIDES a query-relevant doc.
    hit = kl.search("creativity", sparte="performativ")
    assert "unesco-mini-published-2010" in hit
    # a non-present sparte must NOT exclude the query-relevant published doc
    still = kl.search("creativity", sparte="tanz-nonexistent")
    assert "unesco-mini-published-2010" in still


def test_search_glossary_surfaces(built_db):
    kl, _ = built_db
    result = kl.search("cultural participation")
    assert "GLOSSARY" in result
    assert "cultural participation" in result


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------

def test_read_returns_passage_and_metadata(built_db):
    kl, _ = built_db
    result = kl.read("unesco-mini-published-2010", section="Aims")
    # passage body (from the WISSEN subsection)
    assert "aims of arts education" in result.lower()
    # source metadata: title/year/url — enough to hand the book across the
    # table. The license is curation plumbing and must NOT be in the text
    # Resona reads (fix 0816d8ee).
    assert "CC BY-SA 3.0 IGO" not in result
    assert "2010" in result
    assert "pf0000000001" in result  # url
    # the review anchor must NOT leak into the returned passage
    assert "quelle:" not in result


def test_read_refuses_draft(built_db):
    kl, _ = built_db
    result = kl.read("unesco-mini-draft-2011")
    assert "not published" in result.lower() or "draft" in result.lower()


def test_read_unknown_doc_lists_available(built_db):
    kl, _ = built_db
    result = kl.read("no-such-doc")
    assert "unesco-mini-published-2010" in result
    assert "unesco-mini-draft-2011" not in result  # draft not offered


# ---------------------------------------------------------------------------
# missing index
# ---------------------------------------------------------------------------

def test_missing_index_message(tmp_path, monkeypatch):
    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", tmp_path / "does-not-exist.sqlite", raising=False)
    msg_search = kl.search("anything")
    msg_read = kl.read("any-doc")
    assert "not built" in msg_search
    assert "build_knowledge_index.py" in msg_search
    assert "not built" in msg_read


# ---------------------------------------------------------------------------
# No full-text marker in any committed library file (Verdichtungs-Umbau core
# rule: full text is never Bestand, never index, never model context).
# ---------------------------------------------------------------------------

def test_no_full_text_marker_in_library():
    """No committed Tier-F library file may carry a ## DOCUMENT section (that was
    the old full-text form). PROFIL/WISSEN/GLOSSAR only."""
    library = Path(__file__).resolve().parents[1] / "my_app" / "knowledge" / "library"
    offenders = []
    for md in library.rglob("*.md"):
        if md.name.upper() == "ATTRIBUTION.MD" or md.name.endswith(".raw.md"):
            continue
        text = md.read_text(encoding="utf-8")
        import re as _re
        if _re.search(r"^##\s+DOCUMENT\s*$", text, _re.MULTILINE):
            offenders.append(md.name)
    assert not offenders, f"full-text ## DOCUMENT marker present in: {offenders}"


# ---------------------------------------------------------------------------
# Tool registration / scope
# ---------------------------------------------------------------------------

def test_tools_registered_in_resona_scope_only():
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    resona = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    universal = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    assert "lookup_knowledge" in resona
    assert "read_knowledge" in resona
    assert "lookup_knowledge" not in universal
    assert "read_knowledge" not in universal


def test_universal_resona_intersection_is_the_grants_only():
    """The tools BOTH agents hold are grants, one at a time: lookup_reference
    and lookup_interception (2026-07-03), lookup_place (2026-08-11). The
    knowledge tools stay resona-only, the research pair stays universal, and
    nothing else joins this set by accident."""
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    resona = {t["function"]["name"] for t in registry.get_openai_format(scope="resona")}
    universal = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    assert resona & universal == {
        "lookup_reference", "lookup_interception", "lookup_place"}
    assert not {"lookup_knowledge", "read_knowledge"} & universal
    assert not {"lookup_research", "read_research"} & resona


def test_research_tools_are_universal_and_tier_pinned():
    """The 2026-08-11 grant: the help agent reaches the research section and
    nothing else. The tier is pinned in the handler, not offered as a parameter,
    and a doc_id from another tier is refused instead of opened."""
    from my_app.services.tool_registry import get_tool_registry
    registry = get_tool_registry()
    universal = {t["function"]["name"] for t in registry.get_openai_format(scope=None)}
    assert {"lookup_research", "read_research"} <= universal

    spec = next(t["function"] for t in registry.get_openai_format(scope=None)
                if t["function"]["name"] == "lookup_research")
    assert "tier" not in spec["parameters"]["properties"]

    # A Tier-F id is a real id; this path must still refuse it.
    refused = registry.execute(
        "read_research",
        {"doc_id": "unesco-a-framework-for-culture-and-arts-education-2024"})
    assert refused.startswith("Error"), refused


# ---------------------------------------------------------------------------
# set_operator_meta — bibliographic front-matter rewrite (Tier-O only).
# App-free: write a compact MD, edit its meta, read the file back. The quoting
# (a citation `quelle` contains ':' and ',') and the FM-slice confinement (a
# stray `quelle:` in the body is never rewritten) are the load-bearing points.
# ---------------------------------------------------------------------------

_META_MD = """---
id: op-meta-2020
titel: Falscher Titel aus Kapitel
autor: ""
jahr: ""
sprache: de
tier: O
sparten: []
themen: []
bereich: some-area
lizenz: "nur interne Nutzung"
url: ""
status: draft
---

# Falscher Titel aus Kapitel

## PROFIL

Ein Text, dessen Titelzeile in Wahrheit eine Kapitelüberschrift war. Der Body
erwähnt beiläufig quelle: als Wort und darf NICHT umgeschrieben werden.

## WISSEN

### Abschnitt

Body.

<!-- quelle: Abschnitt -->
"""


@pytest.fixture()
def meta_doc(tmp_path, monkeypatch):
    import config
    tier_o = tmp_path / "knowledge_library"
    tier_o.mkdir(parents=True)
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)
    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    (tier_o / "op-meta-2020.md").write_text(_META_MD, encoding="utf-8")
    return kl, tier_o


def test_set_operator_meta_rewrites_all_fields_quoted(meta_doc):
    kl, tier_o = meta_doc
    ok = kl.set_operator_meta(
        "op-meta-2020",
        titel="Kunstlabore: Für mehr Kunst in Schulen!",
        autor="J. Heisig, I. Scharf",
        jahr="2019",
        quelle="transcript, Bielefeld, S. 3–48",
    )
    assert ok is True
    md = (tier_o / "op-meta-2020.md").read_text(encoding="utf-8")
    # titel with a colon -> JSON-quoted; autor with comma -> quoted; jahr int;
    # quelle with colon+comma -> quoted. All read back through the index parser.
    assert 'titel: "Kunstlabore: Für mehr Kunst in Schulen!"' in md
    assert 'autor: "J. Heisig, I. Scharf"' in md
    assert "jahr: 2019" in md
    assert 'quelle: "transcript, Bielefeld, S. 3–48"' in md
    # `quelle` inserted in front-matter order (after jahr, before sprache).
    fm = md.split("---", 2)[1]
    assert fm.index("jahr:") < fm.index("quelle:") < fm.index("sprache:")
    # The body's stray "quelle:" word is untouched (FM-slice confinement).
    body = md.split("---", 2)[2]
    assert "erwähnt beiläufig quelle: als Wort" in body
    # The <!-- quelle: Abschnitt --> anchor is likewise untouched.
    assert "<!-- quelle: Abschnitt -->" in body


def test_set_operator_meta_partial_only_touches_given_keys(meta_doc):
    kl, tier_o = meta_doc
    before = (tier_o / "op-meta-2020.md").read_text(encoding="utf-8")
    kl.set_operator_meta("op-meta-2020", titel="Nur der Titel")
    after = (tier_o / "op-meta-2020.md").read_text(encoding="utf-8")
    assert "titel: Nur der Titel" in after
    # autor/jahr lines unchanged (still empty strings), bereich intact, no quelle.
    assert 'autor: ""' in after
    assert 'jahr: ""' in after
    assert "bereich: some-area" in after
    assert "quelle:" not in after.split("---", 2)[1]  # not inserted


def test_set_operator_meta_missing_item_returns_false(meta_doc):
    kl, _ = meta_doc
    assert kl.set_operator_meta("does-not-exist", titel="X") is False


def test_set_operator_meta_refuses_non_tier_o(tmp_path, monkeypatch):
    import config
    tier_o = tmp_path / "knowledge_library"
    lib = tmp_path / "library" / "unesco"
    lib.mkdir(parents=True)
    tier_o.mkdir(parents=True)
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_DIR", tmp_path / "library", raising=False)
    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    # A path that resolves outside the Tier-O dir must be refused even at the
    # service level (defence in depth; the route also 404s a Tier-F id).
    with pytest.raises(PermissionError):
        kl._assert_tier_o(lib / "x.md")


def test_admin_yaml_scalar_quotes_citation_punctuation():
    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    # Values with YAML-significant punctuation get JSON-quoted; a plain word does
    # not. This mirrors knowledge_processing._yaml_scalar so a repaired file reads
    # back identically to a freshly produced one.
    assert kl._admin_yaml_scalar("Plain") == "Plain"
    assert kl._admin_yaml_scalar("Has: colon") == '"Has: colon"'
    assert kl._admin_yaml_scalar("a, b") == '"a, b"'
    assert kl._admin_yaml_scalar("") == '""'
    assert kl._admin_yaml_scalar(2023) == "2023"

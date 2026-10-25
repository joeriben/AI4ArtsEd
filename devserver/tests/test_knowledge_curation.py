"""
Tests for the knowledge-library Phase 2 (Settings/curation layer, BIBLIOTHEK.md
§9) after the Verdichtungs-Umbau (2026-07-04).

The ingest job now runs Docling -> raw.md (here: --md passthrough, no Docling)
-> Verdichtung IN-PROCESS (my_app.services.knowledge_processing) -> reindex. The
Verdichtung's LLM path is stubbed so the test never hits a provider.

Covers:
- upload policy (Formular-Entbürokratisierung): only the FILE is required now.
  Missing title -> still 200 (extracted/filename); missing license -> 200
  (defaults to internal-use-only); wrong extension -> 400.
- happy path (Markdown ingest): upload -> the FIFO job runs the real ingest
  (--md) + in-process Verdichtung + reindex -> the draft appears in the Tier-O
  inventory with a chunk count; its PROFIL (card) + WISSEN are readable.
- status toggle draft->published rewrites the front-matter and, after the
  route's reindex, becomes visible to the published-only runtime search().
- Tier-F protection: status/delete on a library/ doc -> 403/404 (never mutated).
- glossary-override merge in build_knowledge_index: a hidden term disappears
  from the index; a changed definition lands (curated=1).

Run: python3 -m pytest devserver/tests/test_knowledge_curation.py -q
"""

import importlib
import io
import sys
import time
from pathlib import Path
from file_modules import load_index_builder

# devserver/tests/... -> parents[1] == devserver/ (same convention as the other
# knowledge/resona tests).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


# A raw (Docling-style) input Markdown for the --md passthrough path. Long enough
# that the structure parser makes a content section worth a Map call.
_MINI_MD = """# Mini Operator Doc

## Einleitung

Ein kurzes Betreiberdokument ueber dekoloniale Kunstpaedagogik und kulturelle Resilienz. Es baut auf vorhandenen Diskursen auf und richtet sich an die mediale und performative Praxis. Das Dokument entstand aus einer Reihe von Werkstattgespraechen mit Kulturschaffenden, die seit mehreren Jahren an Schulen und in ausserschulischen Bildungsformaten arbeiten und dabei immer wieder auf koloniale Kontinuitaeten in Lehrplaenen und Materialien stossen. Mehrere Regionalgruppen haben in den vergangenen zwei Jahren eigene Varianten dieses Ansatzes erprobt und ihre Erfahrungen in einem gemeinsamen Austauschtreffen zusammengetragen, dessen Ergebnisse wiederum in die vorliegende Fassung eingeflossen sind. Dabei zeigte sich, dass eine rein additive Erweiterung der Lehrmaterialien nicht ausreicht, solange die zugrunde liegenden Strukturen unangetastet bleiben, weshalb dieses Dokument bewusst auf strukturelle Veraenderungen zielt statt auf einzelne Unterrichtseinheiten.

## Abschnitt

Etwas mehr Fliesstext, damit der Struktur-Chunker mindestens einen inhaltstragenden Abschnitt erzeugt. Konkrete Massnahme: drei Schritte, Mindestalter 12, Evaluation alle 6 Monate. Beispiel: ein Projekt mit 30 Teilnehmenden im Jahr 2025. Die drei Schritte umfassen erstens eine Bestandsaufnahme der verwendeten Materialien, zweitens eine Schulung des Lehrpersonals zu kolonialen Bildsprachen und drittens eine externe Begutachtung durch eine Fachstelle vor der Veroeffentlichung. Die Evaluation wird von einer unabhaengigen Stelle alle sechs Monate durchgefuehrt und die Ergebnisse werden dem Kollegium zurueckgemeldet. Das Pilotprojekt lief zunaechst an zwei Standorten und wird nun schrittweise auf weitere Einrichtungen der Region ausgeweitet. Die Finanzierung erfolgt ueber eine Mischung aus kommunalen Mitteln und einer externen Foerderung, die zunaechst auf drei Jahre befristet ist und danach evaluiert werden soll. Teilnehmende Einrichtungen verpflichten sich, ihre Erfahrungen in einem jaehrlichen Bericht zu dokumentieren und diesen der Koordinierungsstelle zur Verfuegung zu stellen, damit die gesammelten Erkenntnisse in eine ueberarbeitete Fassung dieses Dokuments einfliessen koennen.
"""


def _stub_llm(temperature: float = 0.2):
    """A deterministic stand-in for the provider-routed LLM: a bibliographic
    record for the identify_bibliographic call, schema JSON for Map calls, plain
    text for the PROFIL Reduce call. Keeps the in-vivo term and a number so the
    Mittellage expectation is exercised without a network."""
    import json as _json

    def _fn(system: str, user: str, max_tokens: int):
        if "bibliographic cataloguer" in system:
            # The identifier: return a clean work title/author/year so a
            # blank-title upload gets a real bibliography (art105413 shape).
            return _json.dumps({
                "titel": "Bildung für nachhaltige Entwicklung",
                "untertitel": None,
                "autoren": ["Erika Musterfrau"],
                "jahr": 2024,
                "quelle": "Zeitschrift für Kunstpädagogik",
                "teil": None,
                "confidence": "high",
            }, ensure_ascii=False)
        if "PROFIL" in system:
            return ("Das Dokument behandelt dekoloniale Kunstpaedagogik und "
                    "kulturelle Resilienz und baut auf vorhandenen Diskursen auf. "
                    "Anwendbar in medialer und performativer Praxis.")
        return _json.dumps({
            "section_title": "Massnahmen",
            "digest": "- drei Schritte\n- Mindestalter 12\n- Evaluation alle 6 Monate\nBeispiel: 30 Teilnehmende, 2025.",
            "terms": [{"term": "kulturelle Resilienz", "definition": "Widerstandsfaehigkeit kultureller Praxis"}],
        }, ensure_ascii=False)

    return _fn


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """A Flask test client with all knowledge storage redirected into tmp_path,
    the ingest interpreter pointed at the current python (the --md path needs no
    Docling), and the Verdichtung LLM stubbed (no provider call)."""
    import config

    tier_o = tmp_path / "knowledge_library"
    originals = tmp_path / "resources" / "knowledge_originals"
    lib = tmp_path / "library"
    (lib / "unesco").mkdir(parents=True)
    db = tmp_path / "knowledge_index.sqlite"
    overrides = tmp_path / "json" / "knowledge_glossary_overrides.json"

    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_ORIGINALS_DIR", originals, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_DIR", lib, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_GLOSSARY_OVERRIDES", overrides, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INGEST_PYTHON", sys.executable, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_PYTHON", sys.executable, raising=False)

    # Stub the in-process Verdichtung LLM (the job worker imports it lazily).
    import my_app.services.knowledge_processing as kp
    importlib.reload(kp)
    monkeypatch.setattr(kp, "default_llm_fn", _stub_llm, raising=False)

    # Point the runtime service DB at the temp index too.
    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    kl._QUERY_TRANSLATION_CACHE.clear()

    from my_app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    return client, kl, config


def _poll_job(client, job_id, timeout=90):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = client.get(f"/api/knowledge/jobs/{job_id}")
        last = r.get_json()
        if last["state"] in ("done", "error"):
            return last
        time.sleep(0.4)
    return last


def _upload_mini(client, **overrides):
    data = {
        "title": overrides.get("title", "Mini Operator Doc"),
        "lizenz": overrides.get("lizenz", "CC BY 4.0"),
        "autor": "Tester",
        "year": "2026",
        "lang": "de",
        "sparten": "performativ,medial",
        "themen": "dekolonial",
        "document": (io.BytesIO(_MINI_MD.encode("utf-8")),
                     overrides.get("filename", "mini.md")),
    }
    for k in ("title", "lizenz"):
        if overrides.get(k) == "__omit__":
            data.pop(k)
    return client.post("/api/knowledge/upload", data=data,
                       content_type="multipart/form-data")


# ---------------------------------------------------------------------------
# Upload policy (Formular-Entbürokratisierung — only the FILE is required)
# ---------------------------------------------------------------------------

def test_upload_without_license_defaults(app_client):
    client, _, _ = app_client
    r = _upload_mini(client, lizenz="__omit__")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["success"] is True


def test_upload_without_title_ok(app_client):
    client, _, _ = app_client
    r = _upload_mini(client, title="__omit__")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["success"] is True
    # doc_id falls back to the filename stem when title is absent.
    assert r.get_json()["doc_id"].startswith("mini")


def test_upload_rejects_bad_extension(app_client):
    client, _, _ = app_client
    r = _upload_mini(client, filename="evil.exe")
    assert r.status_code == 400
    assert "type" in r.get_json()["error"].lower()


# ---------------------------------------------------------------------------
# Happy path: upload -> ingest job (Docling->Verdichtung->reindex) -> curation
# ---------------------------------------------------------------------------

def test_upload_ingests_and_lists_draft(app_client):
    client, kl, _ = app_client
    r = _upload_mini(client)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["success"] is True
    job_id, doc_id = body["job_id"], body["doc_id"]

    job = _poll_job(client, job_id)
    assert job is not None and job["state"] == "done", job
    # The FINAL id: a fresh upload starts under the provisional id the upload
    # answered, and the ingest renames it to the Author-Year-Title id once the
    # bibliographic fields are resolved. The job view
    # carries the renamed id; the upload response cannot know it yet.
    doc_id = job["doc_id"]

    # The draft is now in the Tier-O inventory with a chunk count.
    items = client.get("/api/knowledge/items").get_json()["items"]
    match = [i for i in items if i["doc_id"] == doc_id]
    assert match, items
    assert match[0]["status"] == "draft"
    assert match[0]["chunks"] >= 1
    assert match[0]["lizenz"] == "CC BY 4.0"

    # The curation view reads the MD (drafts included): PROFIL as `card`, WISSEN.
    item = client.get(f"/api/knowledge/items/{doc_id}").get_json()
    assert item["status"] == "draft"
    assert item["sparten"] == ["performativ", "medial"]
    assert "Resilienz" in item["card"] or "Resilienz" in item.get("wissen", "")
    # The Verdichtung kept a concrete number in WISSEN (Mittellage).
    assert "Mindestalter 12" in item.get("wissen", "")

    # Runtime search must NOT see the draft yet (published-only, unchanged).
    assert doc_id not in kl.search("Resilienz dekolonial")


def test_status_toggle_publishes_to_index(app_client):
    client, kl, _ = app_client
    body = _upload_mini(client).get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]

    # Publish -> front-matter rewritten + reindex; now search() sees it.
    r = client.post(f"/api/knowledge/items/{doc_id}/status",
                    json={"status": "published"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["reindex_rc"] == 0

    item = client.get(f"/api/knowledge/items/{doc_id}").get_json()
    assert item["status"] == "published"
    assert doc_id in kl.search("Resilienz dekolonial")


def test_delete_removes_item(app_client):
    client, _, config = app_client
    body = _upload_mini(client).get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]

    md_path = Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md"
    assert md_path.exists()

    r = client.delete(f"/api/knowledge/items/{doc_id}")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["md_deleted"] is True
    assert not md_path.exists()
    items = client.get("/api/knowledge/items").get_json()["items"]
    assert all(i["doc_id"] != doc_id for i in items)


# ---------------------------------------------------------------------------
# Bibliographic identification at ingest: a blank-title upload gets its
# titel/autor/jahr/quelle from identify_bibliographic (run in _run_verdichtung);
# an upload that PROVIDES a title keeps it verbatim (operator input wins).
# ---------------------------------------------------------------------------

def test_blank_title_upload_gets_identified_bibliography(app_client):
    client, _, config = app_client
    # Upload with NO title/autor/year -> the ingest bibliographic pass fills them.
    r = _upload_mini(client, title="__omit__")
    # Remove autor/year too so all three are blank (the stub identifier answers).
    # _upload_mini always sends autor/year; override the form here directly.
    body = r.get_json()
    assert r.status_code == 200, body
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]

    md = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    # autor/year WERE supplied by _upload_mini (Tester / 2026) -> they win, the
    # identifier does not overwrite them. But the blank TITLE is filled from the
    # identifier (not the filename, not a heading).
    item = client.get(f"/api/knowledge/items/{doc_id}").get_json()
    assert item["titel"] == "Bildung für nachhaltige Entwicklung"
    # quelle was blank -> filled by the identifier and rendered in the front-matter
    # (bare scalar here: this value has no YAML-significant punctuation to quote).
    assert item["quelle"] == "Zeitschrift für Kunstpädagogik"
    assert "quelle: Zeitschrift für Kunstpädagogik" in md
    # autor supplied by the operator is untouched (operator input wins).
    assert item["autor"] == "Tester"


def test_supplied_title_is_not_overwritten_by_identifier(app_client):
    client, _, config = app_client
    # A normal upload PROVIDES a title -> no bibliographic pass runs for it, the
    # operator's title is kept verbatim (even though the stub would offer another).
    body = _upload_mini(client, title="Mein Eigener Titel").get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    item = client.get(f"/api/knowledge/items/{job['doc_id']}").get_json()
    assert item["titel"] == "Mein Eigener Titel"
    assert item["titel"] != "Bildung für nachhaltige Entwicklung"


# ---------------------------------------------------------------------------
# Meta edit route (PUT /items/<id>/meta): operator correction of a mis-identified
# titel/autor/jahr/quelle. Front-matter rewrite + reindex; Tier-F refused.
# ---------------------------------------------------------------------------

def test_put_meta_rewrites_front_matter_and_reindexes(app_client):
    client, kl, config = app_client
    body = _upload_mini(client, title="Falscher Titel").get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]

    r = client.put(f"/api/knowledge/items/{doc_id}/meta", json={
        "titel": "Der Richtige Werktitel", "autor": "A. Autorin, B. Autor",
        "jahr": "2021", "quelle": "Buch: Verlag, S. 3–48",
    })
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["reindex_rc"] == 0

    md = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    assert "titel: Der Richtige Werktitel" in md
    assert 'autor: "A. Autorin, B. Autor"' in md      # comma -> JSON-quoted
    assert "jahr: 2021" in md
    assert 'quelle: "Buch: Verlag, S. 3–48"' in md    # colon+comma -> JSON-quoted
    # The body (PROFIL/WISSEN) is untouched by a meta edit.
    assert "## PROFIL" in md and "## WISSEN" in md
    # The route echoes the normalised values.
    assert r.get_json()["titel"] == "Der Richtige Werktitel"
    assert r.get_json()["jahr"] in (2021, "2021")


def test_put_meta_partial_leaves_other_fields(app_client):
    client, _, config = app_client
    body = _upload_mini(client, title="Nur Titel Aendern").get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]
    before = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")

    # Only titel -> autor/jahr lines unchanged.
    r = client.put(f"/api/knowledge/items/{doc_id}/meta", json={"titel": "Neuer Titel"})
    assert r.status_code == 200, r.get_json()
    after = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    assert "titel: Neuer Titel" in after
    # autor supplied at upload (Tester) is still there.
    assert "autor: Tester" in after
    # nothing else about the front-matter block order changed except titel.
    assert before.count("---") == after.count("---")


def test_put_meta_rejects_empty_body_and_blank_title(app_client):
    client, _, _ = app_client
    body = _upload_mini(client, title="X").get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]

    assert client.put(f"/api/knowledge/items/{doc_id}/meta", json={}).status_code == 400
    assert client.put(f"/api/knowledge/items/{doc_id}/meta",
                      json={"titel": "   "}).status_code == 400
    assert client.put(f"/api/knowledge/items/{doc_id}/meta",
                      json={"jahr": "not-a-year"}).status_code == 400


def test_put_meta_unknown_doc_404(app_client):
    client, _, _ = app_client
    r = client.put("/api/knowledge/items/no-such-doc/meta", json={"titel": "X"})
    assert r.status_code == 404


def test_put_meta_tier_f_refused(app_client):
    client, _, config = app_client
    lib_doc = Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco" / "unesco-protected-2010.md"
    lib_doc.write_text(_TIER_F_DOC, encoding="utf-8")
    before = lib_doc.read_text(encoding="utf-8")
    # A Tier-F-only id is not addressable by the Tier-O meta route -> 404, file
    # untouched (the mutation helper only ever sees Tier-O paths).
    r = client.put("/api/knowledge/items/unesco-protected-2010/meta",
                   json={"titel": "hacked"})
    assert r.status_code == 404
    assert lib_doc.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# Tier-F protection (never mutate committed library/ docs from the curation API)
# ---------------------------------------------------------------------------

_TIER_F_DOC = """---
id: unesco-protected-2010
titel: "Protected Tier-F Doc"
autor: UNESCO
jahr: 2010
sprache: en
tier: F
sparten: [performativ]
themen: [policy]
lizenz: "CC BY-SA 3.0 IGO"
url: ""
status: published
---

# Protected Tier-F Doc

## PROFIL

A committed Tier-F document that the curation API must refuse to touch.

## WISSEN

### Body

Some body.

<!-- quelle: Body -->
"""


def test_tier_f_status_change_forbidden(app_client):
    client, _, config = app_client
    # The curation routes only ever address Tier-O paths, so a Tier-F-only id is
    # "not found" there (404) and the Tier-F file is never touched.
    lib_doc = Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco" / "unesco-protected-2010.md"
    lib_doc.write_text(_TIER_F_DOC, encoding="utf-8")

    r = client.post("/api/knowledge/items/unesco-protected-2010/status",
                    json={"status": "draft"})
    assert r.status_code == 404
    assert "status: published" in lib_doc.read_text(encoding="utf-8")


def test_tier_f_guard_raises_permission_error(app_client):
    """Direct service-level guard: a path under library/ must be refused even if
    something tried to route a mutation there."""
    client, _, config = app_client
    import my_app.services.knowledge_library as kl
    lib_doc = Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco" / "x.md"
    with pytest.raises(PermissionError):
        kl._assert_tier_o(lib_doc)


# ---------------------------------------------------------------------------
# Tier-F read-only transparency views (Settings only): the fixed UNESCO corpus
# is LISTED (readonly:true) and its profile is READABLE, while every write route
# on a Tier-F doc_id stays refused. This is the "show the read-only docs" gap:
# it must never widen the Resona retrieval path or the Tier-O mutation guards.
# ---------------------------------------------------------------------------

def _seed_tier_f(config, n: int) -> list:
    """Write n committed Tier-F docs into the temp library and reindex-source
    them by returning their ids. Bodies are the shared _TIER_F_DOC with a unique
    id/title so the index has distinct rows."""
    ids = []
    lib_unesco = Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco"
    lib_unesco.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        doc_id = f"unesco-fixed-sample-{2000 + i}"
        md = _TIER_F_DOC.replace("unesco-protected-2010", doc_id).replace(
            "Protected Tier-F Doc", f"Fixed Sample {i}")
        (lib_unesco / f"{doc_id}.md").write_text(md, encoding="utf-8")
        ids.append(doc_id)
    return ids


def test_items_bereich_unesco_lists_tier_f_readonly(app_client):
    """GET /items?bereich=unesco returns the committed Tier-F corpus, every row
    flagged readonly:true (a transparency list — no curation actions)."""
    client, _, config = app_client
    ids = _seed_tier_f(config, 9)  # mirror the shipped corpus size
    assert client.post("/api/knowledge/reindex").status_code == 200

    items = client.get("/api/knowledge/items?bereich=unesco").get_json()["items"]
    got_ids = {i["doc_id"] for i in items}
    assert got_ids == set(ids), got_ids
    assert len(items) == 9
    assert all(i["readonly"] is True for i in items)
    # Each carries the list shape the UNESCO panel renders (title/year/chunks).
    # (year comes straight from the index column; compare type-agnostically.)
    sample = items[0]
    assert sample["titel"] and str(sample["jahr"]) == "2010" and sample["chunks"] >= 1

    # The Tier-O inventory (no bereich) must NOT contain the Tier-F docs.
    tier_o = client.get("/api/knowledge/items").get_json()["items"]
    assert not (set(ids) & {i["doc_id"] for i in tier_o})


def test_items_detail_tier_f_readonly_profile(app_client):
    """GET /items/<tier-F-doc> returns the read-only profile view: PROFIL as
    `card`, the WISSEN body, parsed GLOSSAR — and readonly:true."""
    client, _, config = app_client
    [doc_id] = _seed_tier_f(config, 1)
    assert client.post("/api/knowledge/reindex").status_code == 200

    r = client.get(f"/api/knowledge/items/{doc_id}")
    assert r.status_code == 200, r.get_json()
    item = r.get_json()
    assert item["readonly"] is True
    assert item["tier"] == "F"
    assert item["doc_id"] == doc_id
    assert "committed Tier-F document" in item["card"]
    assert "Some body." in item["wissen"]


def test_tier_f_read_visible_but_writes_still_refused(app_client):
    """Even once a Tier-F doc is readable through the transparency views, every
    write route on its doc_id stays refused and the file is never mutated (the
    existing Tier-O guards are unchanged: the mutation helpers only see Tier-O
    paths, so a Tier-F id is 'not found' there)."""
    client, _, config = app_client
    [doc_id] = _seed_tier_f(config, 1)
    assert client.post("/api/knowledge/reindex").status_code == 200
    lib_doc = Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco" / f"{doc_id}.md"
    before = lib_doc.read_text(encoding="utf-8")

    # Readable...
    assert client.get(f"/api/knowledge/items/{doc_id}").status_code == 200
    # ...but not mutable through any curation route.
    assert client.post(f"/api/knowledge/items/{doc_id}/status",
                       json={"status": "draft"}).status_code == 404
    assert client.put(f"/api/knowledge/items/{doc_id}/card",
                      json={"card": "hacked"}).status_code == 404
    assert client.post(f"/api/knowledge/items/{doc_id}/bereich",
                       json={"bereich": None}).status_code == 404
    assert client.delete(f"/api/knowledge/items/{doc_id}").status_code == 404
    # The committed file is byte-for-byte unchanged.
    assert lib_doc.read_text(encoding="utf-8") == before


def test_fixed_md_path_rejects_traversal(app_client):
    """fixed_md_path sanitises the id and never resolves outside the library."""
    client, _, config = app_client
    import my_app.services.knowledge_library as kl
    [doc_id] = _seed_tier_f(config, 1)
    # A real Tier-F id resolves under the library dir.
    p = kl.fixed_md_path(doc_id)
    assert p is not None and Path(config.KNOWLEDGE_LIBRARY_DIR).resolve() in p.resolve().parents
    # Traversal / unknown ids resolve to nothing.
    assert kl.fixed_md_path("../../../etc/passwd") is None
    assert kl.fixed_md_path("does-not-exist") is None
    assert kl.get_fixed_item("../../secrets") is None


# ---------------------------------------------------------------------------
# Glossary-override merge (build_knowledge_index): hidden + changed definition
# ---------------------------------------------------------------------------

_GLOSS_DOC = """---
id: op-gloss-2026
titel: "Gloss Doc"
autor: Tester
jahr: 2026
sprache: de
tier: O
sparten: [medial]
themen: [misc]
lizenz: "CC BY 4.0"
url: ""
status: published
---

# Gloss Doc

## GLOSSAR

- **Resilienz** — urspruengliche Definition aus dem Dokument.
- **Diversitaet** — Vielfalt als Wert.

## WISSEN

### Intro

Fliesstext ueber Resilienz und Diversitaet.

<!-- quelle: Intro -->
"""


def _glossary_terms(db_path: Path):
    import sqlite3
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return {r["term"]: dict(r) for r in
                con.execute("SELECT term, definition, curated FROM glossary").fetchall()}
    finally:
        con.close()


def test_glossary_override_hidden_and_changed(app_client, tmp_path):
    client, kl, config = app_client
    b = load_index_builder()

    # Put a Tier-O doc with two glossary terms into the temp Tier-O dir.
    (Path(config.KNOWLEDGE_TIER_O_DIR)).mkdir(parents=True, exist_ok=True)
    (Path(config.KNOWLEDGE_TIER_O_DIR) / "op-gloss-2026.md").write_text(
        _GLOSS_DOC, encoding="utf-8")

    # Build once WITHOUT overrides -> both terms present, uncurated.
    docs = b.scan_library(Path(config.KNOWLEDGE_LIBRARY_DIR),
                          Path(config.KNOWLEDGE_TIER_O_DIR))
    b.GLOSSARY_OVERRIDES = Path(config.KNOWLEDGE_GLOSSARY_OVERRIDES)  # absent -> no-op
    b.build(Path(config.KNOWLEDGE_INDEX_DB), docs)
    terms = _glossary_terms(Path(config.KNOWLEDGE_INDEX_DB))
    assert "Resilienz" in terms and "Diversitaet" in terms
    assert terms["Resilienz"]["curated"] == 0

    # Write overrides via the route (canonical dict-keyed shape): hide one term,
    # redefine the other.
    ov = {
        "Diversitaet": {"hidden": True},
        "Resilienz": {"definition": "REDIGIERTE Definition der Betreiberin."},
    }
    r = client.put("/api/knowledge/glossary-overrides", json={"overrides": ov})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["reindex_rc"] == 0

    # After the route's reindex: hidden term gone, changed definition + curated=1.
    terms2 = _glossary_terms(Path(config.KNOWLEDGE_INDEX_DB))
    assert "Diversitaet" not in terms2
    assert "Resilienz" in terms2
    assert terms2["Resilienz"]["definition"] == "REDIGIERTE Definition der Betreiberin."
    assert terms2["Resilienz"]["curated"] == 1

    # The override file round-trips through GET.
    got = client.get("/api/knowledge/glossary-overrides").get_json()["overrides"]
    assert got["Diversitaet"]["hidden"] is True


# ---------------------------------------------------------------------------
# Curation view: get_operator_item returns the WISSEN sections + glossary
# (the Settings document view shows more than the PROFIL — BIBLIOTHEK.md §9,
# essay-mode UI gap fix). App-free: writes a compact MD and reads it back.
# ---------------------------------------------------------------------------

_COMPACT_MD = """---
id: sample-essay-2021
titel: Ein Beispiel-Aufsatz
autor: A. Autorin
jahr: 2021
sprache: de
tier: O
sparten: []
themen: []
lizenz: nur interne Nutzung
url: ""
status: draft
---

# Ein Beispiel-Aufsatz

## PROFIL

Der Text setzt sich gegen bloße Inhaltserweiterung ab und entwickelt einen
Kriterienrahmen.

## WISSEN

### Problemaufriss: additive Lösung genügt nicht

Bloße Erweiterung der Lektürelisten lässt die Strukturen unangetastet.

<!-- quelle: Problemaufriss: additive Lösung genügt nicht -->

### Kriterienrahmen: Indikatoren

- Differenz als sozial hergestellt verstehen
- Intersektionalität erkennen
- Willen zur Veränderung entwickeln

<!-- quelle: Kriterienrahmen: Indikatoren -->

## GLOSSAR

- **Critical Diversity Literacy (CDL)** — Rahmen für diskriminierungskritisches Wissen.
- **Diskriminierungskritik** — Kritik an Kategorien der Ungleichheit.
"""


def test_get_operator_item_returns_wissen_sections_and_glossary(tmp_path, monkeypatch):
    """GET /items/<id> -> the curation view must carry the WISSEN body (all ###
    subsections) AND the parsed GLOSSAR, not only the PROFIL (`card`). This is
    the data the Settings document view renders under the profile."""
    import config
    tier_o = tmp_path / "knowledge_library"
    tier_o.mkdir(parents=True)
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)

    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    (tier_o / "sample-essay-2021.md").write_text(_COMPACT_MD, encoding="utf-8")

    item = kl.get_operator_item("sample-essay-2021")
    assert item is not None
    # PROFIL still exposed as the editable `card`.
    assert "Inhaltserweiterung" in item["card"]
    # WISSEN carried in full — BOTH ### subsections and their bodies.
    wissen = item["wissen"]
    assert "Problemaufriss: additive Lösung genügt nicht" in wissen
    assert "Kriterienrahmen: Indikatoren" in wissen
    assert "Intersektionalität erkennen" in wissen
    # GLOSSAR parsed into structured entries.
    terms = {g["term"] for g in item["glossary"]}
    assert "Critical Diversity Literacy (CDL)" in terms
    assert "Diskriminierungskritik" in terms


def test_get_operator_item_without_provenance_keys_still_parses(tmp_path, monkeypatch):
    """A document produced BEFORE the analysis-provenance feature (no
    analyzed_at/analysis_lang/analysis_model in its front-matter, e.g. every
    document analysed prior to 2026-07-10) must still parse cleanly through the
    curation view -- the three fields default to "" (never guessed, never a
    crash), which the frontend renders as a muted "never analyzed" marker. The
    pre-existing `sprache` (source language) field is unaffected."""
    import config
    tier_o = tmp_path / "knowledge_library"
    tier_o.mkdir(parents=True)
    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)

    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    (tier_o / "sample-essay-2021.md").write_text(_COMPACT_MD, encoding="utf-8")

    item = kl.get_operator_item("sample-essay-2021")
    assert item is not None
    assert item["analyzed_at"] == ""
    assert item["analysis_lang"] == ""
    assert item["analysis_model"] == ""
    assert item["sprache"] == "de"


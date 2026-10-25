"""
Tests for the Wissensbereiche (operator areas) layer — the MoJo-Diskursräume
analogue of the knowledge library (Settings curation).

Two halves:

1. Areas CRUD over knowledge_areas (via the knowledge_bp routes): create with id
   sanitisation + collision suffix, rename, kommentar change, delete-only-when-
   empty, and the fixed UNESCO pseudo-area (present in the listing, never
   editable/deletable, never an upload target).

2. bereich + hinweis end-to-end through the real ingest job (--md passthrough,
   Verdichtung stubbed, reindex): the compact file's front-matter carries both;
   the index facets `bereich` (items?bereich filters, the /areas count is right);
   lookup_knowledge surfaces the area's kommentar as ONE context line for hits
   from a commented area; read_knowledge's header carries the document hinweis.

Storage is redirected into tmp_path (index DB, Tier-O dir, originals, library,
glossary overrides, AND the areas store) so nothing touches the real install.

Run: python3 -m pytest devserver/tests/test_knowledge_areas.py -q
"""

import importlib
import io
import sys
import time
from pathlib import Path

# devserver/tests/... -> parents[1] == devserver/ (same convention as the other
# knowledge/resona tests).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


# A raw (Docling-style) input Markdown for the --md passthrough path (same shape
# as test_knowledge_curation._MINI_MD): long enough for one content section.
_MINI_MD = """# Mini Operator Doc

## Einleitung

Ein kurzes Betreiberdokument ueber dekoloniale Kunstpaedagogik und kulturelle Resilienz. Es baut auf vorhandenen Diskursen auf und richtet sich an die mediale und performative Praxis. Das Dokument entstand aus einer Reihe von Werkstattgespraechen mit Kulturschaffenden, die seit mehreren Jahren an Schulen und in ausserschulischen Bildungsformaten arbeiten und dabei immer wieder auf koloniale Kontinuitaeten in Lehrplaenen und Materialien stossen. Mehrere Regionalgruppen haben in den vergangenen zwei Jahren eigene Varianten dieses Ansatzes erprobt und ihre Erfahrungen in einem gemeinsamen Austauschtreffen zusammengetragen, dessen Ergebnisse wiederum in die vorliegende Fassung eingeflossen sind. Dabei zeigte sich, dass eine rein additive Erweiterung der Lehrmaterialien nicht ausreicht, solange die zugrunde liegenden Strukturen unangetastet bleiben, weshalb dieses Dokument bewusst auf strukturelle Veraenderungen zielt statt auf einzelne Unterrichtseinheiten.

## Abschnitt

Etwas mehr Fliesstext, damit der Struktur-Chunker mindestens einen inhaltstragenden Abschnitt erzeugt. Konkrete Massnahme: drei Schritte, Mindestalter 12, Evaluation alle 6 Monate. Beispiel: ein Projekt mit 30 Teilnehmenden im Jahr 2025. Die drei Schritte umfassen erstens eine Bestandsaufnahme der verwendeten Materialien, zweitens eine Schulung des Lehrpersonals zu kolonialen Bildsprachen und drittens eine externe Begutachtung durch eine Fachstelle vor der Veroeffentlichung. Die Evaluation wird von einer unabhaengigen Stelle alle sechs Monate durchgefuehrt und die Ergebnisse werden dem Kollegium zurueckgemeldet. Das Pilotprojekt lief zunaechst an zwei Standorten und wird nun schrittweise auf weitere Einrichtungen der Region ausgeweitet. Die Finanzierung erfolgt ueber eine Mischung aus kommunalen Mitteln und einer externen Foerderung, die zunaechst auf drei Jahre befristet ist und danach evaluiert werden soll. Teilnehmende Einrichtungen verpflichten sich, ihre Erfahrungen in einem jaehrlichen Bericht zu dokumentieren und diesen der Koordinierungsstelle zur Verfuegung zu stellen, damit die gesammelten Erkenntnisse in eine ueberarbeitete Fassung dieses Dokuments einfliessen koennen.
"""


def _stub_llm(temperature: float = 0.2):
    """Deterministic stand-in for the provider-routed LLM (schema JSON for Map,
    plain text for the PROFIL Reduce). Identical to test_knowledge_curation."""
    import json as _json

    def _fn(system: str, user: str, max_tokens: int):
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
    """Flask test client with ALL knowledge storage (incl. the areas store)
    redirected into tmp_path, the ingest interpreter = current python (the --md
    path needs no Docling), and the Verdichtung LLM stubbed."""
    import config

    tier_o = tmp_path / "knowledge_library"
    originals = tmp_path / "resources" / "knowledge_originals"
    lib = tmp_path / "library"
    (lib / "unesco").mkdir(parents=True)
    db = tmp_path / "knowledge_index.sqlite"
    overrides = tmp_path / "json" / "knowledge_glossary_overrides.json"
    areas_store = tmp_path / "json" / "knowledge_areas.json"

    monkeypatch.setattr(config, "KNOWLEDGE_TIER_O_DIR", tier_o, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_ORIGINALS_DIR", originals, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_DIR", lib, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_GLOSSARY_OVERRIDES", overrides, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INGEST_PYTHON", sys.executable, raising=False)
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_PYTHON", sys.executable, raising=False)

    # Redirect the areas store (module-level constant).
    import my_app.services.knowledge_areas as ka
    importlib.reload(ka)
    monkeypatch.setattr(ka, "STORE_PATH", areas_store, raising=False)

    # Stub the in-process Verdichtung LLM.
    import my_app.services.knowledge_processing as kp
    importlib.reload(kp)
    monkeypatch.setattr(kp, "default_llm_fn", _stub_llm, raising=False)

    # Point the runtime service DB at the temp index too, and make sure the
    # library module resolves the freshly-reloaded areas module (its lazy import
    # picks up sys.modules, which reload replaced).
    import my_app.services.knowledge_library as kl
    importlib.reload(kl)
    kl._QUERY_TRANSLATION_CACHE.clear()

    from my_app import create_app
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    return client, kl, ka, config


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


def _upload(client, *, bereich=None, hinweis=None, filename="mini.md", title="Mini Operator Doc"):
    data = {
        "title": title,
        "lizenz": "CC BY 4.0",
        "autor": "Tester",
        "year": "2026",
        "lang": "de",
        "sparten": "performativ,medial",
        "themen": "dekolonial",
        "document": (io.BytesIO(_MINI_MD.encode("utf-8")), filename),
    }
    if bereich is not None:
        data["bereich"] = bereich
    if hinweis is not None:
        data["hinweis"] = hinweis
    return client.post("/api/knowledge/upload", data=data,
                       content_type="multipart/form-data")


# ===========================================================================
# 1) Areas CRUD
# ===========================================================================

def test_areas_listing_has_unesco_only_initially(app_client):
    client, _, _, _ = app_client
    r = client.get("/api/knowledge/areas")
    assert r.status_code == 200
    body = r.get_json()["areas"]
    # Only the fixed UNESCO pseudo-area is present before any is created.
    assert len(body) == 1
    u = body[0]
    assert u["id"] == "unesco" and u["fixed"] is True
    assert u["name"].startswith("UNESCO")
    assert u["count"] == 0  # empty temp library


def test_create_area_sanitizes_id_and_collides(app_client):
    client, _, _, _ = app_client
    r1 = client.post("/api/knowledge/areas",
                     json={"name": "Dekoloniale Kunstpädagogik!", "kommentar": "warum"})
    assert r1.status_code == 200, r1.get_json()
    a1 = r1.get_json()["area"]
    assert a1["id"] == "dekoloniale-kunstp-dagogik"  # non-alnum -> hyphen-collapsed
    assert a1["kommentar"] == "warum"
    assert a1["fixed"] is False and a1["count"] == 0

    # Same name again -> id gets a -2 suffix (collision-free).
    r2 = client.post("/api/knowledge/areas",
                     json={"name": "Dekoloniale Kunstpädagogik!"})
    assert r2.status_code == 200
    assert r2.get_json()["area"]["id"] == "dekoloniale-kunstp-dagogik-2"


def test_create_area_rejects_empty_name(app_client):
    client, _, _, _ = app_client
    r = client.post("/api/knowledge/areas", json={"name": "   "})
    assert r.status_code == 400
    assert "leer" in r.get_json()["error"].lower()


def test_create_area_rejects_unesco_name(app_client):
    client, _, _, _ = app_client
    # A name that sanitises to the reserved id must be rejected.
    r = client.post("/api/knowledge/areas", json={"name": "unesco"})
    assert r.status_code == 400
    assert "reserv" in r.get_json()["error"].lower()


def test_rename_and_edit_kommentar(app_client):
    client, _, _, _ = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Bereich A", "kommentar": "alt"}).get_json()["area"]["id"]

    # Rename (id stays stable) + change kommentar.
    r = client.put(f"/api/knowledge/areas/{aid}",
                   json={"name": "Bereich A neu", "kommentar": "neu"})
    assert r.status_code == 200, r.get_json()
    area = r.get_json()["area"]
    assert area["id"] == aid  # id is stable across rename
    assert area["name"] == "Bereich A neu"
    assert area["kommentar"] == "neu"

    # kommentar can be cleared with an empty string; name left unchanged (None).
    r2 = client.put(f"/api/knowledge/areas/{aid}", json={"kommentar": ""})
    assert r2.status_code == 200
    assert r2.get_json()["area"]["kommentar"] == ""
    assert r2.get_json()["area"]["name"] == "Bereich A neu"


def test_update_missing_area_404(app_client):
    client, _, _, _ = app_client
    r = client.put("/api/knowledge/areas/does-not-exist", json={"name": "x"})
    assert r.status_code == 404


def test_delete_empty_area_ok(app_client):
    client, _, _, _ = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Leer"}).get_json()["area"]["id"]
    r = client.delete(f"/api/knowledge/areas/{aid}")
    assert r.status_code == 200 and r.get_json()["success"] is True
    # Gone from the listing (UNESCO remains).
    ids = [a["id"] for a in client.get("/api/knowledge/areas").get_json()["areas"]]
    assert aid not in ids and "unesco" in ids


def test_unesco_not_editable_or_deletable(app_client):
    client, _, _, _ = app_client
    assert client.put("/api/knowledge/areas/unesco", json={"name": "x"}).status_code == 400
    assert client.delete("/api/knowledge/areas/unesco").status_code == 400


def test_upload_to_unesco_rejected(app_client):
    client, _, _, _ = app_client
    r = _upload(client, bereich="unesco")
    assert r.status_code == 400
    assert "unesco" in r.get_json()["error"].lower()


def test_upload_to_unknown_bereich_rejected(app_client):
    client, _, _, _ = app_client
    r = _upload(client, bereich="ghost-area")
    assert r.status_code == 400
    assert "unbekannt" in r.get_json()["error"].lower()


# ===========================================================================
# 2) bereich + hinweis end-to-end
# ===========================================================================

def test_upload_with_bereich_and_hinweis_flows_through(app_client):
    client, kl, _, config = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Dekoloniale Kunstpädagogik",
                            "kommentar": "Grundlagentexte für die Sommerwerkstatt"}
                      ).get_json()["area"]["id"]

    body = _upload(client, bereich=aid,
                   hinweis="Zentraler Referenztext für Modul 3").get_json()
    assert body["success"] is True
    job = _poll_job(client, body["job_id"])
    assert job is not None and job["state"] == "done", job
    doc_id = job["doc_id"]

    # (a) The compact front-matter carries both bereich and hinweis.
    md = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    assert f"bereich: {aid}" in md
    assert "hinweis:" in md and "Modul 3" in md

    # (b) The curation item exposes them; items?bereich filters to this area.
    item = client.get(f"/api/knowledge/items/{doc_id}").get_json()
    assert item["bereich"] == aid
    assert "Modul 3" in item["hinweis"]

    filtered = client.get(f"/api/knowledge/items?bereich={aid}").get_json()["items"]
    assert [i["doc_id"] for i in filtered] == [doc_id]
    other = client.get("/api/knowledge/items?bereich=some-other").get_json()["items"]
    assert other == []

    # (c) The /areas count reflects the one attached document (draft counts too).
    areas = {a["id"]: a for a in client.get("/api/knowledge/areas").get_json()["areas"]}
    assert areas[aid]["count"] == 1

    # (d) A non-empty area cannot be deleted.
    r = client.delete(f"/api/knowledge/areas/{aid}")
    assert r.status_code == 400
    assert "1" in r.get_json()["error"] or r.get_json().get("count") == 1


def test_lookup_surfaces_bereich_context_line(app_client):
    client, kl, _, _ = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Dekoloniale Kunstpädagogik",
                            "kommentar": "Grundlagentexte für die Sommerwerkstatt"}
                      ).get_json()["area"]["id"]
    body = _upload(client, bereich=aid, hinweis="Referenztext").get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]

    # Publish so the runtime (published-only) search can see it.
    assert client.post(f"/api/knowledge/items/{doc_id}/status",
                       json={"status": "published"}).status_code == 200

    out = kl.search("Resilienz dekolonial")
    assert doc_id in out
    # ONE neutral context line naming the area + the operator's kommentar.
    assert 'Bereich "Dekoloniale Kunstpädagogik"' in out
    assert "Grundlagentexte für die Sommerwerkstatt" in out
    assert "Betreiber-Hinweis" in out


def test_lookup_no_context_line_when_area_has_no_kommentar(app_client):
    client, kl, _, _ = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Ohne Notiz"}).get_json()["area"]["id"]
    body = _upload(client, bereich=aid).get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]
    assert client.post(f"/api/knowledge/items/{doc_id}/status",
                       json={"status": "published"}).status_code == 200

    out = kl.search("Resilienz dekolonial")
    assert doc_id in out
    # No kommentar -> no bereich context line at all (the note is the point).
    assert "Betreiber-Hinweis" not in out
    assert "Bereich \"" not in out


def test_read_header_carries_document_hinweis(app_client):
    client, kl, _, _ = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Bereich X", "kommentar": "k"}).get_json()["area"]["id"]
    body = _upload(client, bereich=aid,
                   hinweis="Zentraler Referenztext für Modul 3").get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    doc_id = job["doc_id"]
    assert client.post(f"/api/knowledge/items/{doc_id}/status",
                       json={"status": "published"}).status_code == 200

    out = kl.read(doc_id)
    # The document hinweis appears as ONE neutral header line.
    assert "[Betreiber-Hinweis: Zentraler Referenztext für Modul 3]" in out
    # And the license is still NOT leaked into the read text (unchanged rule).
    assert "CC BY 4.0" not in out


# ===========================================================================
# 3) Move a document between areas — POST /items/<doc_id>/bereich
# ===========================================================================

def _ingest_into(client, aid=None):
    """Upload the mini doc (optionally into area `aid`), run the job to done,
    and return its FINAL doc_id: the ingest renames a fresh upload's provisional
    id to the Author-Year-Title id, and the job view is
    what carries the renamed id."""
    body = _upload(client, bereich=aid).get_json()
    job = _poll_job(client, body["job_id"])
    assert job["state"] == "done", job
    return job["doc_id"]


def test_move_document_between_areas_happy_path(app_client):
    client, _, _, config = app_client
    src = client.post("/api/knowledge/areas",
                      json={"name": "Quelle"}).get_json()["area"]["id"]
    dst = client.post("/api/knowledge/areas",
                      json={"name": "Ziel"}).get_json()["area"]["id"]
    doc_id = _ingest_into(client, aid=src)

    # Sanity: it starts in the source area.
    assert client.get(f"/api/knowledge/items/{doc_id}").get_json()["bereich"] == src
    assert [i["doc_id"] for i in
            client.get(f"/api/knowledge/items?bereich={src}").get_json()["items"]] == [doc_id]

    # Move it to the destination area.
    r = client.post(f"/api/knowledge/items/{doc_id}/bereich", json={"bereich": dst})
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data["success"] is True
    assert data["old_bereich"] == src and data["bereich"] == dst
    assert data["reindex_rc"] == 0

    # (a) The front-matter `bereich:` was rewritten.
    md = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    assert f"bereich: {dst}" in md
    assert f"bereich: {src}" not in md

    # (b) The index follows after the route's reindex: items?bereich tracks it,
    #     and the /areas counts move with it.
    assert [i["doc_id"] for i in
            client.get(f"/api/knowledge/items?bereich={dst}").get_json()["items"]] == [doc_id]
    assert client.get(f"/api/knowledge/items?bereich={src}").get_json()["items"] == []
    counts = {a["id"]: a["count"] for a in client.get("/api/knowledge/areas").get_json()["areas"]}
    assert counts[dst] == 1 and counts[src] == 0


def test_move_document_to_no_area_clears_field(app_client):
    client, _, _, config = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Bereich"}).get_json()["area"]["id"]
    doc_id = _ingest_into(client, aid=aid)

    # bereich: null -> the field is removed from the front-matter entirely.
    r = client.post(f"/api/knowledge/items/{doc_id}/bereich", json={"bereich": None})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["bereich"] is None
    assert r.get_json()["old_bereich"] == aid

    md = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    assert "bereich:" not in md
    # No longer counted under the (now empty) area, and the empty area is
    # deletable again.
    counts = {a["id"]: a["count"] for a in client.get("/api/knowledge/areas").get_json()["areas"]}
    assert counts[aid] == 0
    assert client.delete(f"/api/knowledge/areas/{aid}").status_code == 200


def test_move_document_from_no_area_into_area(app_client):
    client, _, _, config = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Zielbereich"}).get_json()["area"]["id"]
    # Upload WITHOUT a bereich (area-less), then move it into the area.
    doc_id = _ingest_into(client, aid=None)
    md0 = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    assert "bereich:" not in md0  # area-less upload has no bereich line

    r = client.post(f"/api/knowledge/items/{doc_id}/bereich", json={"bereich": aid})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["old_bereich"] is None and r.get_json()["bereich"] == aid
    md1 = (Path(config.KNOWLEDGE_TIER_O_DIR) / f"{doc_id}.md").read_text(encoding="utf-8")
    assert f"bereich: {aid}" in md1
    assert [i["doc_id"] for i in
            client.get(f"/api/knowledge/items?bereich={aid}").get_json()["items"]] == [doc_id]


def test_move_to_unknown_area_rejected(app_client):
    client, _, _, _ = app_client
    doc_id = _ingest_into(client, aid=None)
    r = client.post(f"/api/knowledge/items/{doc_id}/bereich",
                    json={"bereich": "ghost-area"})
    assert r.status_code == 400
    assert "unbekannt" in r.get_json()["error"].lower()


def test_move_to_unesco_rejected(app_client):
    client, _, _, _ = app_client
    doc_id = _ingest_into(client, aid=None)
    r = client.post(f"/api/knowledge/items/{doc_id}/bereich",
                    json={"bereich": "unesco"})
    assert r.status_code == 400
    assert "unesco" in r.get_json()["error"].lower()


def test_move_missing_bereich_key_rejected(app_client):
    client, _, _, _ = app_client
    doc_id = _ingest_into(client, aid=None)
    # Empty body (no 'bereich' key at all) is a 400 — the move must be explicit.
    r = client.post(f"/api/knowledge/items/{doc_id}/bereich", json={})
    assert r.status_code == 400
    assert "bereich" in r.get_json()["error"].lower()


def test_move_nonexistent_document_404(app_client):
    client, _, _, _ = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Irgendwas"}).get_json()["area"]["id"]
    r = client.post("/api/knowledge/items/no-such-doc/bereich", json={"bereich": aid})
    assert r.status_code == 404


def test_move_tier_f_document_not_addressable(app_client):
    """A Tier-F (committed library/) doc is not a Tier-O item, so the move route
    cannot reach it (404) and the file is never touched."""
    client, _, _, config = app_client
    lib_doc = Path(config.KNOWLEDGE_LIBRARY_DIR) / "unesco" / "unesco-x-2010.md"
    lib_doc.write_text(
        "---\nid: unesco-x-2010\ntitel: X\nautor: UNESCO\njahr: 2010\n"
        "sprache: en\ntier: F\nsparten: []\nthemen: []\nlizenz: x\nurl: \"\"\n"
        "status: published\n---\n\n# X\n\n## PROFIL\n\nBody.\n",
        encoding="utf-8",
    )
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Ziel"}).get_json()["area"]["id"]
    r = client.post("/api/knowledge/items/unesco-x-2010/bereich", json={"bereich": aid})
    assert r.status_code == 404
    assert "tier: F" in lib_doc.read_text(encoding="utf-8")


# ===========================================================================
# 4) Area chip counters: published/total (GET /areas)
# ===========================================================================

def test_areas_counts_published_and_total(app_client):
    """One draft + one published in the same area -> the /areas entry carries
    count_published=1 and count_total=2 (the chips render "1/2 docs"); `count`
    stays the TOTAL for backwards compatibility (delete-safety, older readers)."""
    client, _, _, _ = app_client
    created = client.post("/api/knowledge/areas",
                          json={"name": "Zaehl-Bereich"}).get_json()["area"]
    aid = created["id"]
    # The create response already carries the two-number shape (empty area).
    assert created["count"] == 0
    assert created["count_published"] == 0 and created["count_total"] == 0

    # Two documents into the area; publish exactly one -> 1 published of 2 total.
    doc_a = _ingest_into(client, aid=aid)
    doc_b = _ingest_into(client, aid=aid)
    assert client.post(f"/api/knowledge/items/{doc_a}/status",
                       json={"status": "published"}).status_code == 200
    del doc_b  # stays a draft

    areas_by_id = {a["id"]: a for a in client.get("/api/knowledge/areas").get_json()["areas"]}
    entry = areas_by_id[aid]
    assert entry["count_total"] == 2
    assert entry["count_published"] == 1
    assert entry["count"] == 2  # `count` == total, unchanged contract

    # The UNESCO pseudo-area carries the same shape (empty temp library: 0/0),
    # with published == total (the committed Tier-F corpus ships published).
    unesco = areas_by_id["unesco"]
    assert unesco["count_total"] == unesco["count"]
    assert unesco["count_published"] == unesco["count_total"]

    # The area rename/update response carries the two-number shape too.
    upd = client.put(f"/api/knowledge/areas/{aid}",
                     json={"name": "Zaehl-Bereich neu"}).get_json()["area"]
    assert upd["count_published"] == 1 and upd["count_total"] == 2

    # Draft-holding areas still cannot be deleted (TOTAL guards deletion).
    assert client.delete(f"/api/knowledge/areas/{aid}").status_code == 400


# ===========================================================================
# 5) Reprocess carries status + bereich forward (2026-07-09 fix): a FRESH
# upload always starts draft, but re-running Verdichtung on an ALREADY
# ingested doc (POST /items/<id>/reprocess, no re-upload) must preserve its
# CURRENT status/bereich. Before this fix every reprocess unconditionally
# reset status to draft -- on the owner's planned ~30-document bulk
# re-analysis that would have silently unpublished everything already
# published. No test exercised this route before; this is new coverage, not
# a fix for one of the 20 regressed tests.
# ===========================================================================

def test_reprocess_preserves_published_status_and_bereich(app_client):
    client, _, _, config = app_client
    aid = client.post("/api/knowledge/areas",
                      json={"name": "Reprocess-Bereich"}).get_json()["area"]["id"]
    doc_id = _ingest_into(client, aid=aid)

    # Publish it -- the reprocess below must not silently unpublish this.
    assert client.post(f"/api/knowledge/items/{doc_id}/status",
                       json={"status": "published"}).status_code == 200
    before = client.get(f"/api/knowledge/items/{doc_id}").get_json()
    assert before["status"] == "published" and before["bereich"] == aid

    r = client.post(f"/api/knowledge/items/{doc_id}/reprocess")
    assert r.status_code == 200, r.get_json()
    end = _poll_job(client, r.get_json()["job_id"])
    assert end is not None and end["state"] == "done", end

    after = client.get(f"/api/knowledge/items/{doc_id}").get_json()
    assert after["status"] == "published", after   # NOT reset to draft
    assert after["bereich"] == aid                   # carried over


def test_reprocess_preserves_draft_status(app_client):
    client, _, _, config = app_client
    doc_id = _ingest_into(client, aid=None)
    assert client.get(f"/api/knowledge/items/{doc_id}").get_json()["status"] == "draft"

    r = client.post(f"/api/knowledge/items/{doc_id}/reprocess")
    assert r.status_code == 200, r.get_json()
    end = _poll_job(client, r.get_json()["job_id"])
    assert end is not None and end["state"] == "done", end

    assert client.get(f"/api/knowledge/items/{doc_id}").get_json()["status"] == "draft"

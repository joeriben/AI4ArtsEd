"""scope_summary(): faktische Bestandskarte fuer Resonas GIVEN-LIBRARY-Block.

Nur published zaehlt; fehlender/leerer Index -> '' (fail-safe); Format traegt
Sparten-/Tier-Zaehlungen und das Themen-Vokabular.
"""
import config
import json
import sqlite3

from my_app.services import knowledge_library as KL


def _mk_index(tmp_path, rows):
    db = tmp_path / "knowledge_index.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE docs (doc_id TEXT PRIMARY KEY, tier TEXT,"
        " sparten_json TEXT, themen_json TEXT, status TEXT)"
    )
    for i, r in enumerate(rows):
        con.execute(
            "INSERT INTO docs VALUES (?,?,?,?,?)",
            (
                f"d{i}",
                r.get("tier", "unesco"),
                json.dumps(r.get("sparten", [])),
                json.dumps(r.get("themen", [])),
                r.get("status", "published"),
            ),
        )
    con.commit()
    con.close()
    return db


def test_scope_summary_counts_and_vocabulary(tmp_path, monkeypatch):
    db = _mk_index(tmp_path, [
        {"sparten": ["Kunstpädagogik"], "themen": ["Nachhaltigkeit", "Frieden"], "tier": "unesco"},
        {"sparten": ["Kunstpädagogik", "Kulturelle Bildung"], "themen": ["Nachhaltigkeit"], "tier": "betreiber"},
        {"sparten": ["Musik"], "themen": ["Klang"], "status": "draft"},
    ])
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db)
    monkeypatch.setattr(KL, "_SCOPE_CACHE", (0.0, ""))
    s = KL.scope_summary()
    assert s.startswith("GIVEN LIBRARY: 2 published titles")
    assert "Kunstpädagogik (2)" in s
    assert "Kulturelle Bildung (1)" in s
    assert "Nachhaltigkeit" in s and "Frieden" in s
    assert "Musik" not in s and "Klang" not in s  # drafts bleiben unsichtbar
    assert "unesco (1)" in s and "betreiber (1)" in s
    assert "sparte/thema filters" in s


def test_scope_summary_missing_and_empty_index(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", tmp_path / "absent.sqlite")
    monkeypatch.setattr(KL, "_SCOPE_CACHE", (0.0, ""))
    assert KL.scope_summary() == ""
    db = _mk_index(tmp_path, [])
    monkeypatch.setattr(config, "KNOWLEDGE_INDEX_DB", db)
    assert KL.scope_summary() == ""

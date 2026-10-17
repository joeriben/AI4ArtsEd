"""One Wikipedia cache per process.

get_wikipedia_service builds a service per lookup, because its aiohttp session
belongs to the caller's event loop; until 2026-10-10 each service brought a
cache of its own, so the cache lived for one lookup_multiple and the same term
was asked of Wikipedia again on the next run. WIKIPEDIA_CACHE_TTL bounded
nothing (finding S-027 of the code review of 2026-10-10). The session stays per lookup; the cache is the process's.
"""
from types import SimpleNamespace


def test_two_services_share_one_cache(monkeypatch):
    from my_app.services import wikipedia_service as ws
    monkeypatch.setattr(ws, "_shared_cache", None, raising=False)
    first = ws.get_wikipedia_service(cache_ttl=3600)
    second = ws.get_wikipedia_service(cache_ttl=3600)
    found = SimpleNamespace(title="Bauhaus")
    first._cache.set("Bauhaus", "de", found)
    assert second._cache.get("Bauhaus", "de") is found


def test_the_cache_still_expires(monkeypatch):
    from my_app.services import wikipedia_service as ws
    monkeypatch.setattr(ws, "_shared_cache", None, raising=False)
    service = ws.get_wikipedia_service(cache_ttl=3600)
    now = [1000.0]
    monkeypatch.setattr(ws.time, "time", lambda: now[0])
    service._cache.set("Bauhaus", "de", SimpleNamespace(title="Bauhaus"))
    now[0] += 3601
    assert ws.get_wikipedia_service(cache_ttl=3600)._cache.get("Bauhaus", "de") is None

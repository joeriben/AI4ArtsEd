"""website_search: curated live search/read - parsers, allowlist, fail-safes."""
from my_app.services import website_search as WS


KUBI_FIXTURE = (
    '<div class="views-row result-item" data-counter="1">'
    '<p class="result-headline"><a href="/artikel/kuenste-natur" hreflang="de">'
    '<em>K\u00fcnste</em>, Natur, Nachhaltigkeit</a></p>'
    '<p class="result-from"><span class="result-cite">Von <a href="/autorinnen/goehler">'
    'Goehler, Adrienne</a></span> <span class="result-pub-year">(2020)</span></p>'
    '<p class="result-excerpt">\u2026 mit der kulturellen Dimension \u2026</p></div>'
    '<div class="views-row result-item" data-counter="2">'
    '<p class="result-headline"><a href="/artikel/zweiter">Zweiter Titel</a></p>'
    '<p class="result-excerpt">Text</p></div>'
)

RSS_FIXTURE = (
    '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
    "<title>Search</title>"
    "<item><title>Decolonisation as Sankofa</title>"
    "<link>https://www.explore-vc.org/en/edu/sankofa.html</link>"
    "<description><![CDATA[<p>Art education in <b>Ghana</b></p>]]></description></item>"
    "</channel></rss>"
)

FAKE_SOURCES = [
    {
        "id": "kubi-online",
        "label": "kubi-online (German)",
        "base_url": "https://www.kubi-online.de",
        "search_url": "https://www.kubi-online.de/suche?search_api_fulltext={query}",
        "parser": "drupal_search_api",
        "license_note": "CC BY-NC-ND 4.0",
    },
    {
        "id": "explore-vc",
        "label": "Exploring Visual Cultures",
        "base_url": "https://www.explore-vc.org",
        "search_url": "https://www.explore-vc.org/en/search.feed?q={query}&type=rss",
        "parser": "rss_feed",
        "license_note": "",
    },
]


def test_kubi_parser_extracts_structured_hits(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(WS, "_fetch", lambda url: KUBI_FIXTURE)
    out = WS.search("kubi-online", "Nachhaltigkeit")
    assert "K\u00fcnste, Natur, Nachhaltigkeit (Goehler, Adrienne - 2020)" in out
    assert "https://www.kubi-online.de/artikel/kuenste-natur" in out
    assert "Zweiter Titel" in out
    assert "CC BY-NC-ND 4.0" in out
    assert "read_webpage" in out


def test_rss_parser_extracts_items(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(WS, "_fetch", lambda url: RSS_FIXTURE)
    out = WS.search("explore-vc", "decolonial")
    assert "Decolonisation as Sankofa" in out
    assert "https://www.explore-vc.org/en/edu/sankofa.html" in out
    assert "Art education in Ghana" in out


def test_unknown_site_and_unconfigured(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    assert "unknown site_id" in WS.search("wikipedia", "x")
    monkeypatch.setattr(WS, "_load_sources", lambda: [])
    assert "no external sites are configured" in WS.search("kubi-online", "x")


def test_read_page_allowlist(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    out = WS.read_page("https://evil.example.org/wp")
    assert out.startswith("Error: this page is not on a configured site")

    html = (
        "<html><head><title>Artikel</title><script>nav()</script></head>"
        "<body><div>Haupttext der Seite.</div><style>.x{}</style></body></html>"
    )
    monkeypatch.setattr(WS, "_fetch", lambda url: html)
    out = WS.read_page("https://www.kubi-online.de/artikel/x")
    assert "PAGE: Artikel" in out
    assert "Haupttext der Seite." in out
    assert "nav()" not in out and ".x{}" not in out
    assert "LICENSE: CC BY-NC-ND 4.0" in out


def test_read_page_truncates(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(WS, "_fetch", lambda url: "<html><body>" + "wort " * 5000 + "</body></html>")
    out = WS.read_page("https://www.kubi-online.de/artikel/lang", max_chars=1000)
    assert "[...truncated]" in out


# -- image weaving (read_webpage with_images) ---------------------------------

IMG_PAGE = (
    "<html><head><title>Gallery</title></head><body>"
    "<main><h1>Water Bodies</h1>"
    "<p>Commentary before the picture.</p>"
    '<img src="/images/evc/logo.svg">'
    '<img src="/images/art/piece1.jpg" alt="Installation view">'
    "<p>Fig. 1: The installation from the entrance.</p>"
    '<img src="https://cdn.elsewhere.net/x.jpg" alt="External piece">'
    "<p>Closing interpretation.</p></main></body></html>"
)


def test_read_page_counts_unseen_images(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(WS, "_fetch", lambda url: IMG_PAGE)
    out = WS.read_page("https://www.explore-vc.org/en/galleries/x.html")
    assert "[[IMG:" not in out
    assert "carries 2 content image(s)" in out
    assert "with_images=true" in out
    # the interpretive text is intact
    assert "Commentary before the picture." in out
    assert "Fig. 1: The installation from the entrance." in out
    assert "Closing interpretation." in out


def test_read_page_weaves_image_accounts_in_place(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(WS, "_fetch", lambda url: IMG_PAGE)
    monkeypatch.setattr(WS, "_fetch_image_bytes", lambda url: b"\x89PNG")
    out = WS.read_page(
        "https://www.explore-vc.org/en/galleries/x.html",
        with_images=True,
        describe_image=lambda b: "A hall with two hanging panels.",
    )
    assert "[[IMG:" not in out
    # the visual account stands BETWEEN its neighbouring commentary lines
    before = out.index("Commentary before the picture.")
    account = out.index("A hall with two hanging panels.")
    caption = out.index("Fig. 1: The installation from the entrance.")
    assert before < account < caption
    assert "Installation view" in out
    # the interpretive commentary survives the weaving untouched
    assert "Closing interpretation." in out
    # the svg logo never became an image; the off-site one is named, not fetched
    assert "logo" not in out
    assert "hosted off-site, not fetched" in out


def test_read_page_marks_unseen_on_vision_failure(monkeypatch):
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(WS, "_fetch", lambda url: IMG_PAGE)
    monkeypatch.setattr(WS, "_fetch_image_bytes", lambda url: b"x")
    out = WS.read_page(
        "https://www.explore-vc.org/en/galleries/x.html",
        with_images=True,
        describe_image=lambda b: None,
    )
    assert "you have NOT seen this picture" in out


def test_read_page_image_budget_is_visible(monkeypatch):
    many = "".join(
        f'<img src="/im/p{i}.jpg" alt="P{i}"><p>Text {i}</p>' for i in range(6)
    )
    monkeypatch.setattr(WS, "_load_sources", lambda: FAKE_SOURCES)
    monkeypatch.setattr(
        WS, "_fetch", lambda url: f"<html><body><main>{many}</main></body></html>"
    )
    monkeypatch.setattr(WS, "_fetch_image_bytes", lambda url: b"x")
    out = WS.read_page(
        "https://www.explore-vc.org/x.html",
        with_images=True,
        describe_image=lambda b: "Seen.",
    )
    assert out.count("seen through the vision channel") == 4
    assert out.count("budget of this call - NOT seen") == 2

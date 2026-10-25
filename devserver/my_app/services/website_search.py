"""Live search + read on curated external websites (Resona tools).

Installation configuration: my_app/knowledge/website_sources.json - the operator
curates WHICH sites exist; the tools never browse beyond them. Access is live
(search, then read one page); nothing is mirrored or stored - for kubi-online
(CC BY-NC-ND 4.0) live access is the license-correct route (BIBLIOTHEK.md).
Stdlib-only parsing (html.parser + xml.etree) over requests, following the
knowledge_library house pattern.
"""
from __future__ import annotations

import base64
import html as html_lib
import json
import logging
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin

import requests

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "website_sources.json"
# kubi-online rejects generic clients (403) - a regular browser UA is required.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)
TIMEOUT_S = 12
MAX_FETCH_CHARS = 1_500_000
READ_DEFAULT_MAX_CHARS = 8000
READ_WITH_IMAGES_MAX_CHARS = 14000
MAX_IMAGE_BYTES = 10_000_000
MAX_IMAGES_PER_READ = 4
IMG_ACCOUNT_TRIM = 1000

_SOURCES_CACHE: Tuple[float, Optional[List[Dict]]] = (0.0, None)


def _load_sources() -> List[Dict]:
    global _SOURCES_CACHE
    try:
        mtime = CONFIG_PATH.stat().st_mtime
    except OSError:
        return []
    if _SOURCES_CACHE[0] == mtime and _SOURCES_CACHE[1] is not None:
        return _SOURCES_CACHE[1]
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        sources = [
            s for s in data.get("sources", [])
            if s.get("id") and s.get("base_url") and s.get("search_url")
        ]
    except Exception as e:  # noqa: BLE001 - unreadable config must not break chat
        logger.warning("[WEBSITES] config unreadable: %s", e)
        return []
    _SOURCES_CACHE = (mtime, sources)
    return sources


def sources_summary() -> str:
    """One line naming the configured site ids (for tool descriptions/errors)."""
    return ", ".join(
        f"'{s['id']}' ({s.get('label', s['base_url'])})" for s in _load_sources()
    )


def _fetch(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text[:MAX_FETCH_CHARS]


def _strip_tags(fragment: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", "", fragment or "")).strip()


# -- search parsers -----------------------------------------------------------

def _parse_drupal_search_api(page: str, base_url: str, limit: int) -> List[Dict]:
    """kubi-online: Drupal search_api result rows (headline/cite/year/excerpt)."""
    items: List[Dict] = []
    for chunk in page.split('class="views-row result-item')[1:]:
        head = re.search(
            r'result-headline"><a href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S
        )
        if not head:
            continue
        author = re.search(r'result-cite">Von\s*<a[^>]*>(.*?)</a>', chunk, re.S)
        year = re.search(r'result-pub-year">\((\d{4})\)', chunk)
        excerpt = re.search(r'result-excerpt">(.*?)</p>', chunk, re.S)
        items.append({
            "title": _strip_tags(head.group(2)),
            "url": urljoin(base_url, head.group(1)),
            "author": _strip_tags(author.group(1)) if author else "",
            "year": year.group(1) if year else "",
            "snippet": _strip_tags(excerpt.group(1))[:300] if excerpt else "",
        })
        if len(items) >= limit:
            break
    return items


def _parse_rss_feed(page: str, base_url: str, limit: int) -> List[Dict]:
    """explore-vc: Joomla com_finder search feed (clean RSS items)."""
    items: List[Dict] = []
    try:
        root = ET.fromstring(page)
    except ET.ParseError as e:
        logger.warning("[WEBSITES] rss parse failed: %s", e)
        return []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        desc = _strip_tags(item.findtext("description") or "")[:300]
        items.append({
            "title": title,
            "url": urljoin(base_url, link),
            "author": "",
            "year": "",
            "snippet": desc,
        })
        if len(items) >= limit:
            break
    return items


_PARSERS = {
    "drupal_search_api": _parse_drupal_search_api,
    "rss_feed": _parse_rss_feed,
}


def search(site_id: str, query: str, limit: int = 8) -> str:
    """Live search on ONE configured site; returns a compact hit menu.

    Cross-lingual recall: the curated sites are German-language, but the model
    asks in the workshop's language. We search the query as given AND an English
    variant (mirroring knowledge_library, which already translates); hits from
    both are merged and de-duplicated by URL. This closes the gap the revision
    plan flagged ("Niedlichkeit" -> 0 hits, "cuteness" -> 8 on the same site),
    which matters more now that an empty search counts toward the evidence duty.
    """
    sources = _load_sources()
    if not sources:
        return ("Error: no external sites are configured on this installation "
                "(website_sources.json is missing or empty).")
    source = next((s for s in sources if s["id"] == site_id), None)
    if source is None:
        return f"Error: unknown site_id '{site_id}'. Configured: {sources_summary()}."
    parser = _PARSERS.get(source.get("parser", ""))
    if parser is None:
        return f"Error: site '{site_id}' has no parser configured."
    limit = max(1, min(int(limit or 8), 15))

    # Query as given + an English variant for cross-lingual recall. Lazy import
    # keeps this module import-safe and avoids any import cycle; translate_query
    # returns None when the query is already English or the local model is absent.
    variant: Optional[str] = None
    try:
        from my_app.services.knowledge_library import translate_query
        variant = translate_query(query)
    except Exception as e:  # noqa: BLE001 - translation must never break search
        logger.debug("[WEBSITES] query translation skipped: %s", e)
    queries = [query] + ([variant] if variant else [])

    items: List[Dict] = []
    seen_urls: set = set()
    last_error: Optional[Exception] = None
    fetched_any = False
    for q in queries:
        url = source["search_url"].replace("{query}", quote_plus(q))
        try:
            page = _fetch(url)
        except requests.RequestException as e:
            last_error = e
            continue
        fetched_any = True
        for it in parser(page, source["base_url"], limit):
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            items.append(it)
        if len(items) >= limit:
            items = items[:limit]
            break

    if not fetched_any and last_error is not None:
        return (f"Error: the live search on '{site_id}' failed "
                f"({last_error.__class__.__name__}). The site may be unreachable right now.")
    if not items:
        return (f"No hits on {source.get('label', site_id)} for this query. "
                f"Try other terms (site language matters).")
    lines = [f"Live search on {source.get('label', site_id)} - {len(items)} hit(s):"]
    for i, it in enumerate(items, 1):
        byline = " - ".join(x for x in (it["author"], it["year"]) if x)
        lines.append(f"{i}. {it['title']}" + (f" ({byline})" if byline else ""))
        lines.append(f"   {it['url']}")
        if it["snippet"]:
            lines.append(f"   {it['snippet']}")
    note = source.get("license_note", "")
    lines.append(f"License: {note}." if note else "")
    lines.append("Open a hit with read_webpage(url). Results are live, nothing is stored.")
    return "\n".join(l for l in lines if l)


# -- page reading ---------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Minimal main-text extraction: skip script/style/head noise, keep title."""

    _SKIP = {"script", "style", "noscript", "svg", "template",
             "nav", "header", "footer", "aside", "form", "button"}
    _BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr", "section",
              "article", "blockquote", "dd", "dt"}
    # decoration, not content - never worth a vision call
    _IMG_SKIP = re.compile(r"logo|icon|banner|spacer|badge", re.I)

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._parts: List[str] = []
        self.images: List[Dict[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "img" and not self._skip_depth:
            d = dict(attrs)
            src = (d.get("src") or d.get("data-src") or "").strip()
            if (src and not src.startswith("data:")
                    and not src.lower().endswith(".svg")
                    and not self._IMG_SKIP.search(src)):
                # leave a placeholder IN PLACE so a visual account can later
                # stand between the caption and the commentary it belongs to
                self.images.append({"src": src, "alt": (d.get("alt") or "").strip()})
                self._parts.append(f"\n[[IMG:{len(self.images) - 1}]]\n")
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        if data.strip():
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def _fetch_image_bytes(url: str) -> bytes:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    resp.raise_for_status()
    if len(resp.content) > MAX_IMAGE_BYTES:
        raise ValueError("image too large")
    return resp.content


def _describe_image_bytes(img_bytes: bytes) -> Optional[str]:
    """Neutral visual account via the house vision channel (see view_favorite)."""
    from my_app.services.llm_service import llm_service
    return llm_service.describe_image_neutral(
        base64.b64encode(img_bytes).decode("ascii")
    )


def _weave_images(body, images, page_url, source, *, with_images, max_chars,
                  describe_image):
    """Resolve the [[IMG:i]] placeholders the extractor left in the text.

    with_images=False: placeholders vanish; one closing line counts what the
    page carries, so the reader knows there is something they have not seen.
    with_images=True: each on-site content image (up to MAX_IMAGES_PER_READ)
    is fetched live and described by the vision channel; the account stands
    exactly where the image stands, so captions and the surrounding
    commentary keep their picture. Nothing is stored. describe_image is an
    injection point for tests.
    """
    if not images:
        return body, ""
    if not with_images:
        body = re.sub(r"\n?\[\[IMG:\d+\]\]\n?", "\n", body)
        return body, (
            f"\n\nThis page carries {len(images)} content image(s) you have "
            "not seen. Call again with with_images=true to see them in place."
        )
    base = source["base_url"].rstrip("/")
    describe = describe_image or _describe_image_bytes
    seen = 0
    for i, img in enumerate(images):
        placeholder = f"[[IMG:{i}]]"
        pos = body.find(placeholder)
        if pos < 0:
            continue
        label = img["alt"] or img["src"].rsplit("/", 1)[-1]
        img_url = urljoin(page_url, img["src"])
        if not (img_url.startswith(base + "/") or img_url == base):
            block = f"[IMAGE {label!r}: hosted off-site, not fetched]"
        elif pos > max_chars:
            block = f"[IMAGE {label!r}: beyond this call's text budget - NOT seen]"
        elif seen >= MAX_IMAGES_PER_READ:
            block = (f"[IMAGE {label!r}: beyond the {MAX_IMAGES_PER_READ}-image "
                     "budget of this call - NOT seen]")
        else:
            seen += 1
            account = None
            try:
                account = describe(_fetch_image_bytes(img_url))
            except Exception as e:  # noqa: BLE001 - a broken image must not kill the read
                logger.warning("[WEBSITES] image read failed for %s: %s", img_url, e)
            if account:
                block = (f"[IMAGE {label!r} - seen through the vision channel: "
                         f"{account.strip()[:IMG_ACCOUNT_TRIM]}]")
            else:
                block = (f"[IMAGE {label!r}: the vision channel did not answer - "
                         "you have NOT seen this picture; say so if you speak of it]")
        body = body.replace(placeholder, block)
    return body, ""


def read_page(
    url: str,
    max_chars: Optional[int] = None,
    with_images: bool = False,
    describe_image=None,
) -> str:
    """Read ONE page as clean text - only pages on the configured sites.

    with_images=True additionally fetches the page's on-site content images
    and weaves a neutral visual account into the text at the exact place each
    image occupies - captions and interpretive commentary are kept around it,
    never stripped (live view, nothing stored).
    """
    sources = _load_sources()
    if not sources:
        return ("Error: no external sites are configured on this installation "
                "(website_sources.json is missing or empty).")
    url = (url or "").strip()
    source = next(
        (s for s in sources if url.startswith(s["base_url"].rstrip("/") + "/")
         or url == s["base_url"]),
        None,
    )
    if source is None:
        return (f"Error: this page is not on a configured site. "
                f"Readable sites: {sources_summary()}.")
    if not max_chars:
        max_chars = READ_WITH_IMAGES_MAX_CHARS if with_images else READ_DEFAULT_MAX_CHARS
    max_chars = max(1000, min(int(max_chars), 20000))
    try:
        page = _fetch(url)
    except requests.RequestException as e:
        return f"Error: could not read the page ({e.__class__.__name__})."
    # Prefer the content landmark when the page has one - navigation chrome
    # otherwise eats the text budget before the article starts.
    content = re.search(r"<(main|article).*?</\1>", page, re.S | re.I)
    body_html = content.group(0) if content else page
    title_tag = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    extractor = _TextExtractor()
    try:
        extractor.feed(body_html)
    except Exception as e:  # noqa: BLE001 - malformed HTML must not break chat
        logger.warning("[WEBSITES] extraction failed for %s: %s", url, e)
        return "Error: the page could not be parsed."
    body = extractor.text()
    body, images_note = _weave_images(
        body, extractor.images, url, source,
        with_images=with_images, max_chars=max_chars,
        describe_image=describe_image,
    )
    truncated = len(body) > max_chars
    body = body[:max_chars]
    note = source.get("license_note", "")
    parts = [
        f"PAGE: {(extractor.title.strip() or (_strip_tags(title_tag.group(1)) if title_tag else '') or url)}",
        f"URL: {url}",
        (f"LICENSE: {note}" if note else ""),
        "",
        body + (" [...truncated]" if truncated else "") + images_note,
    ]
    return "\n".join(p for p in parts if p != "")

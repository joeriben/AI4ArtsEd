"""What a room worked out, in the form the board can lay it down.

The entities worked out are represented on the canvas beside the produced
media, if need be only as memory anchors. A small square card, a name on the
front, and on the back an excerpt from the data, in whatever form Resona itself
remembers what the workflow or the object is.

Four kinds, and each one's back is written from a record that already exists:

  apparatus — a strategy kept in the repertoire (canvas_graph_library). Title,
      what it is for, the memo of this version, and the chain of steps.
  note      — something Resona wrote down for the group (remember). Its kind and
      its wording.
  document  — a passage opened in the knowledge library (read_knowledge). Title,
      authors, year, licence and link from the library's own record, and the
      passage that was read. The library holds knowledge it has PROCESSED and
      never the original text, which is why a passage may lie on the surface at
      all.
  page      — a page opened on the curated external sites (read_webpage). Its
      title and its link, and nothing of its body: that text belongs to whoever
      wrote it, and a card is a way back to it, not a copy of it.

What a person brought in themselves already stands on the board as its own node
(resona.vue: a media box with no stream), and a run Resona opens is usually a
run the board is already showing. Those stay in the evidence ledger.
"""

import hashlib
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# What a card back holds of a passage. The read tool fetches up to 6000
# characters for a model to work from; a card is a way back to the document,
# so it carries the opening of what was read and the reference under it.
EXCERPT_CHARS = 700
NAME_CHARS = 120


def _clip(text: Any, n: int) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _page_head(result: str) -> Dict[str, str]:
    """The title and link read_page prints as its first two lines.

    website_search.read_page opens every successful read with `PAGE: <title>`
    and `URL: <url>`; that is the tool's own contract with whoever reads it.
    """
    head = {}
    for line in str(result or "").splitlines()[:4]:
        if line.startswith("PAGE: ") and "title" not in head:
            head["title"] = line[6:].strip()
        elif line.startswith("URL: ") and "url" not in head:
            head["url"] = line[5:].strip()
    return head


def from_tool_call(tool_name: str, tool_args: Dict[str, Any],
                   tool_result: Any) -> Optional[Dict[str, Any]]:
    """One card's worth of an entity this turn worked with, or None.

    Called for tool calls that did NOT return an error. Never raises: a card
    that cannot be written is a card the board does without.
    """
    try:
        return _build(tool_name, tool_args or {}, tool_result)
    except Exception as e:  # noqa: BLE001 - a card must never break a turn
        logger.warning("[RESONA-ENTITY] could not write a card for %s: %s", tool_name, e)
        return None


def _build(tool_name: str, args: Dict[str, Any],
           result: Any) -> Optional[Dict[str, Any]]:
    if tool_name == "canvas_graph_library":
        from my_app.services.tool_registry import take_kept_strategy
        rec = take_kept_strategy()
        if not rec:
            return None
        facts = [f"{rec['id']} · v{rec['version']}"]
        if rec.get("application_type"):
            facts.append(rec["application_type"])
        if rec.get("summary"):
            facts.append(rec["summary"])
        return {
            "kind": "apparatus",
            "key": f"strategy:{rec['id']}:v{rec['version']}",
            "name": _clip(rec.get("title"), NAME_CHARS),
            "detail": _clip(rec.get("memo") or rec.get("description"), EXCERPT_CHARS),
            "facts": [_clip(f, 200) for f in facts],
        }

    if tool_name == "remember":
        content = str(args.get("content") or "").strip()
        if not content:
            return None
        kind = str(args.get("kind") or "").strip()
        return {
            "kind": "note",
            "key": f"note:{kind}:{_fingerprint(content)}",
            "name": _clip(kind or content, NAME_CHARS),
            "detail": _clip(content, EXCERPT_CHARS),
            "facts": [],
        }

    if tool_name == "read_knowledge":
        doc_id = str(args.get("doc_id") or "").strip()
        if not doc_id:
            return None
        from my_app.services import knowledge_library as kl
        card = kl.doc_card(doc_id) or {}
        facts = []
        who = " · ".join(str(card[f]) for f in ("authors", "year")
                         if card.get(f))
        if who:
            facts.append(who)
        if card.get("lizenz"):
            facts.append(str(card["lizenz"]))
        if card.get("url"):
            facts.append(str(card["url"]))
        section = str(args.get("section") or "").strip()
        return {
            "kind": "document",
            "key": f"doc:{doc_id}" + (f"#{section}" if section else ""),
            "name": _clip(card.get("title") or doc_id, NAME_CHARS),
            "detail": _clip(result, EXCERPT_CHARS),
            "facts": [_clip(f, 200) for f in facts],
        }

    if tool_name == "read_webpage":
        head = _page_head(str(result))
        url = head.get("url") or str(args.get("url") or "").strip()
        if not url:
            return None
        return {
            "kind": "page",
            "key": f"web:{url}",
            "name": _clip(head.get("title") or url, NAME_CHARS),
            # The page's own text stays on the page.
            "detail": "",
            "facts": [_clip(url, 200)],
        }

    return None

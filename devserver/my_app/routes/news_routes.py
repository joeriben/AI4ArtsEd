"""
Flask routes for News API

Read-only endpoint serving platform news items from news.json.
News items are curated by the news-curator agent from DEVELOPMENT_LOG.md.
"""
import json
import logging
from flask import Blueprint, jsonify, request
from pathlib import Path

logger = logging.getLogger(__name__)

news_bp = Blueprint('news', __name__, url_prefix='/api/news')

# news.json lives in devserver/ (platform metadata, not user data)
NEWS_FILE = Path(__file__).parent.parent.parent / "news.json"


def _load_news() -> dict:
    """Load news from disk. Returns empty structure on any error."""
    if not NEWS_FILE.exists():
        return {"version": "1.0", "items": []}

    try:
        with open(NEWS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[NEWS] Error loading news.json: {e}")
        return {"version": "1.0", "items": []}


@news_bp.route('', methods=['GET'])
def get_news():
    """
    Get recent news items.

    Query parameters:
        - limit: Max items to return (default 5, max 20)

    Returns:
        200: { items: [...] }
    """
    try:
        limit = min(int(request.args.get('limit', 5)), 20)
    except (ValueError, TypeError):
        limit = 5

    data = _load_news()
    items = data.get('items', [])[:limit]

    return jsonify({'items': items}), 200

"""AI-Origin Disclosure (EU AI Act Art. 50) on the way to the disk, fail-open.

Three recorders write media files themselves and mark them through
watermark_service first. Each of them repeated the same decision: try the
marking, and when the service is unavailable, warn and write the bytes
unmarked, because an unmarked file beats no file. The decision stands here
once; the recorders say which of them is speaking through `tag`.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def mark_or_pass(raw: bytes, entity_type: str, entity_metadata: Optional[Dict[str, Any]],
                 tag: str) -> bytes:
    """The marked bytes, or the bytes as they came when the service cannot
    mark them. The import is made here, so a service that cannot even be
    imported falls open the same way as one that raises."""
    try:
        from my_app.services.watermark_service import watermark_media_bytes

        return watermark_media_bytes(raw, entity_type, entity_metadata)
    except Exception as e:
        logger.warning(f"{tag} watermark service unavailable ({e}); writing unmarked bytes")
        return raw

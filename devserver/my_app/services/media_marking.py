"""AI-Origin Disclosure (EU AI Act Art. 50) on the way to the disk, fail-open.

Four writers put media files on the disk themselves and mark them through
watermark_service first: the three recorders and the sung answer of the
parrot. Each of them repeated the same decision: try the marking, and when
the service is unavailable, warn and write the bytes unmarked, because an
unmarked file beats no file. The decision stands here once; the writers say
which of them is speaking through `tag`.

A generated medium whose bytes do not carry the disclosure afterwards gets
`_ai_generated` before the extension of its name (rule of 2026-11-14):
`mark_for_disk` for the writers, `disclosed_name` for what goes out without
being stored.
"""
import logging
from typing import Any, Dict, Optional, Tuple

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


def disclosed_name(content: Any, entity_type: str, name: str, tag: str) -> str:
    """The name these bytes go under: `name` with `_ai_generated` before its
    extension where they are a generated medium and the disclosure is not in
    them, and without it where they carry it, whatever `name` was before."""
    try:
        from my_app.services.watermark_service import (
            carries_disclosure,
            is_generated_medium,
            plain_filename,
            unmarked_filename,
        )

        plain = plain_filename(name)
        if is_generated_medium(content, entity_type) and not carries_disclosure(content):
            named = unmarked_filename(plain)
            logger.error(f"{tag} {plain} carries no AI-Origin Disclosure; named {named}")
            return named
        return plain
    except Exception as e:
        logger.error(f"{tag} could not check the disclosure of {name} ({e})")
    return name


def mark_for_disk(raw: Any, entity_type: str, entity_metadata: Optional[Dict[str, Any]],
                  filename: str, tag: str) -> Tuple[Any, str]:
    """The bytes to write and the name to write them under."""
    content = mark_or_pass(raw, entity_type, entity_metadata, tag)
    return content, disclosed_name(content, entity_type, filename, tag)

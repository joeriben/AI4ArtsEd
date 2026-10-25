"""The external LLM providers, from one table.

config/llm_providers.json says what a provider IS: the dialect it speaks, where
it answers, and where its key is kept. Every place that used to carry a list of
provider names reads this instead -- the credential loaders in
openai_style_stream.py, the key-present check behind the fallback chain, the
settings page's key handling, the catalogue script. Until 2026-09-12 that list
stood in nine places, and three of them sent 'anthropic/' to three different
places.

What the platform RECORDS about a provider's data path is not here. That is the
operator's entry under llm_presets in hardware_matrix.json, keyed by the same
name, and settings_routes reads it from there.
"""
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# devserver/, the directory the key files live in. Derived from this file and
# NOT read from config: comfyui_nodes/ai4artsed_comfyui/_platform_credentials.py
# loads this module by path inside ComfyUI's process, where nothing of the
# DevServer is importable, so the module stays stdlib-only (the one exception
# to S-077; test_review_d7_findings.py holds it).
DEVSERVER_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_FILE = DEVSERVER_ROOT / "config" / "llm_providers.json"

# The dialects, named once. A caller that routes by dialect compares against
# these rather than against a string of its own.
CHAT_COMPLETIONS = "chat_completions"
MESSAGES = "messages"
BEDROCK = "bedrock"


@lru_cache(maxsize=1)
def providers() -> Dict[str, dict]:
    """Every provider, in table order.

    Read once per process: the file changes when someone edits it, not while
    the service runs, and a provider that appears would need its dispatch
    branch to appear with it anyway.
    """
    with open(REGISTRY_FILE) as f:
        return json.load(f)["providers"]


def provider(name: str) -> Optional[dict]:
    return providers().get(name)


def names(dialect: Optional[str] = None) -> Tuple[str, ...]:
    """The provider names, in table order; only those of one dialect when asked."""
    return tuple(n for n, p in providers().items()
                 if dialect is None or p.get("dialect") == dialect)


def provider_of(model_id: str) -> Optional[str]:
    """The provider a platform model id names, by its first segment.

    The form is exact: '<provider>/<path>', the name spelled as the table
    spells it. None where the first segment names no provider, and for a
    string without '/', which is a bare name -- a bare name and a 'local/' id
    both stay on this machine, and is_local() in model_capabilities says so;
    this does not repeat that answer, it only says which EXTERNAL provider an
    id reaches, or that it reaches none. (A first pass lower-cased and
    stripped the head, which let ' mammouth/x' through as the path '/x' and
    a bare 'mammouth' through as a request for the model ''.)
    """
    head, sep, _ = (model_id or "").partition("/")
    return head if sep and head in providers() else None


def split_provider(model_id: str) -> Tuple[Optional[str], str]:
    """(provider, the path after it) of a platform id, and (None, the id as
    it came) where its first segment names no provider. The one place the
    path is cut off the id; the dispatchers, the image check and the model
    selector read it from here rather than each slicing for itself.
    """
    provider = provider_of(model_id)
    if provider is None:
        return None, model_id
    return provider, model_id[len(provider) + 1:]


def key_file_path(name: str) -> Optional[Path]:
    """Where the provider's key file sits, or None for one that keeps no key file."""
    p = provider(name)
    key_file = p.get("key_file") if p else None
    return DEVSERVER_ROOT / key_file if key_file else None


def _key_from_file(label: str, path: Path, key_prefix: str, quiet: bool) -> str:
    """The first line of the key file that is a key: not blank, not a comment,
    and starting with the provider's key shape where it has one. The log lines
    carry the provider's label, the way the six loaders wrote them, so
    "OpenRouter API key not found" is still the line the setup notes name."""
    try:
        if not path.exists():
            if not quiet:
                logger.warning(f"{label} key file not found: {path}")
            return ""
        for line in path.read_text().strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if key_prefix and not line.startswith(key_prefix):
                continue
            if not quiet:
                logger.info(f"{label} API key loaded from {path}")
            return line
        if not quiet:
            shape = f" (looking for lines starting with '{key_prefix}')" if key_prefix else ""
            logger.error(f"No valid API key found in {path}{shape}")
    except Exception as e:
        if not quiet:
            logger.warning(f"Failed to read {path.name}: {e}")
    return ""


def credentials(name: str, quiet: bool = False) -> Tuple[str, str]:
    """(api_url, key) for a provider: the environment variable first, then the
    key file, then an empty key. The same three sources in the same order the
    six loaders used, and the same log lines -- `quiet` is for a caller that
    only asks whether a key is THERE and has no use for an error line about a
    provider nobody configured.

    A name the table does not carry gets ('', ''): no address, no key, and the
    caller's own "not configured" path takes it from there.
    """
    p = provider(name)
    if not p:
        if not quiet:
            logger.error(f"Unknown provider: {name}")
        return "", ""
    api_url = p.get("api_url", "")
    label = p.get("label", name)
    env_var = p.get("env_var")
    if env_var:
        key = os.environ.get(env_var, "")
        if key:
            if not quiet:
                logger.debug(f"{label} API key from environment variable")
            return api_url, key
    path = key_file_path(name)
    if path is not None:
        key = _key_from_file(label, path, p.get("key_prefix", ""), quiet)
        if key:
            return api_url, key
    if not quiet:
        where = f"Set {env_var} environment variable or create devserver/{p.get('key_file')} file" \
            if env_var else "it keeps no key file"
        logger.error(f"{label} API key not found! {where}")
    return api_url, ""



def key_in_file(name: str) -> str:
    """The key the provider's FILE holds, read the way the platform reads it,
    and nothing from the environment: what the settings page shows masked and
    what it overwrites when the operator saves a key. Empty for a provider
    without a file, or with a file that holds no line of the key's shape."""
    p = provider(name)
    path = key_file_path(name)
    if not p or path is None:
        return ""
    return _key_from_file(p.get("label", name), path, p.get("key_prefix", ""), quiet=True)


def has_key(name: str) -> bool:
    """Whether a credential is present for a provider -- presence, not validity.

    A provider that keeps no key file (bedrock) counts as present: its
    credentials live with the AWS SDK, outside this table. So does 'local',
    which is not a provider at all and never leaves the machine.
    """
    if name == "local":
        return True
    p = provider(name)
    if not p:
        return False
    if not p.get("key_file") and not p.get("env_var"):
        return True
    try:
        return bool(credentials(name, quiet=True)[1])
    except Exception:
        return False

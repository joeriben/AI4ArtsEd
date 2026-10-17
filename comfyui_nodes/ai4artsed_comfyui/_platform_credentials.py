"""
The key nodes' one way to a key: the DevServer's key files, read by the
DevServer's own reader.

`devserver/config/llm_providers.json` says where OpenRouter's key is kept;
`devserver/my_app/services/llm_providers.py` reads it. The key node
(`ai4artsed_openrouter_key`) runs inside
ComfyUI's process, where the DevServer's packages are not importable, so that
module (stdlib only) is loaded by path. The path goes through the repository
this package is linked from: `install_comfyui_nodes.sh` links
`comfyui_nodes/ai4artsed_comfyui/` into ComfyUI's `custom_nodes/`, and
`Path(__file__).resolve()` follows the link back to the repository. A copy of
this package outside the repository has no such path and says so on first use.

One place for API keys. Before, this package carried an
`openrouter.key` of its own, with a second key and, on its second line, a
second address; the DevServer knew nothing of either. The LLM nodes hold no
key at all: their calls go through the DevServer (`_devserver.py`).

Loading happens on first use, not at import: a node registers whether or not
the DevServer directory is reachable.
"""

import importlib.util
from pathlib import Path

_SERVICES = Path(__file__).resolve().parents[2] / "devserver" / "my_app" / "services"
_MODULE_PATH = _SERVICES / "llm_providers.py"
_modules = {}


def _load(name, path):
    """The DevServer module at `path`, loaded once by path (stdlib only)."""
    if name not in _modules:
        if not path.exists():
            raise RuntimeError(
                f"{path.name} not found at {path}. The AI4ArtsEd key nodes read the "
                "DevServer's key files through its own reader and reach it through the "
                "repository they are linked from (install_comfyui_nodes.sh). A copy of this "
                "package outside the repository has no such path.")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _modules[name] = module
    return _modules[name]


def _llm_providers():
    return _load("ai4artsed_llm_providers", _MODULE_PATH)


def get_openrouter_credentials():
    """(chat-completions URL, key) for OpenRouter, from the provider table:
    the URL as config/llm_providers.json spells it, the key from
    OPENROUTER_API_KEY or devserver/openrouter.key. The key is "" where
    neither holds one; the key node refuses in that case, and says so."""
    return _llm_providers().credentials("openrouter")



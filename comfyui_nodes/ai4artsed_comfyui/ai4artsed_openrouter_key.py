from ._platform_credentials import get_openrouter_credentials


class ai4artsed_openrouter_key:
    """Provides the OpenRouter API key to downstream nodes.

    The key is the platform's: OPENROUTER_API_KEY in the environment, else
    devserver/openrouter.key, read through the provider table
    (devserver/config/llm_providers.json).
    Until 2026-09-12 this node read an ``openrouter.key`` of its own next to
    its source, a second place for the same key.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "get_key"
    CATEGORY = "AI4ArtsEd"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Read the key every run. ComfyUI would otherwise cache this node's
        # output until a restart, and a key rotated through the settings page
        # would stay stale in every workflow that wires it.
        return float("nan")

    def get_key(self):
        _, key_line = get_openrouter_credentials()
        if not key_line:
            raise RuntimeError("No OpenRouter API key: set OPENROUTER_API_KEY or write devserver/openrouter.key")
        if not key_line.startswith("sk-or-"):
            raise RuntimeError("The OpenRouter API key (OPENROUTER_API_KEY, else devserver/openrouter.key) does not start with 'sk-or-'.")

        return (key_line,)




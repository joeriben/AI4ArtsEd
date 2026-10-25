# AI4ArtsEd ComfyUI Nodes - Architecture

## Overview

Custom ComfyUI nodes for AI-assisted art education. The nodes that call a language model do so through the DevServer (`POST /api/chat/proxy`), which resolves the model, holds the keys and applies the fallback the settings page regulates; the nodes know no provider.

## Node Structure

```
__init__.py                              # Node registration
ai4artsed_prompt_interception.py         # Prompt Interception via an LLM
ai4artsed_photo_prompt_randomizer.py     # LLM photo prompt generation
ai4artsed_clean_prompt_randomizer.py     # LLM prompt generation
ai4artsed_image_analysis.py              # Image analysis via LLM
ai4artsed_text_remix.py                  # Text remixing
ai4artsed_t5_clip_fusion.py              # T5/CLIP conditioning fusion
ai4artsed_conditioning_fusion.py         # Conditioning fusion
ai4artsed_random_instruction_generator.py
ai4artsed_random_artform_generator.py
ai4artsed_random_language_selector.py
ai4artsed_openrouter_key.py              # API key handling
ai4artsed_vector_dimension_eliminator.py
ai4artsed_switch_promptsafety.py         # Safety filter
_platform_credentials.py                 # The DevServer's key files, read by its own reader loaded by path (the key node)
_devserver.py                            # The DevServer as LLM proxy: model list (GET /api/chat/models) and calls (POST /api/chat/proxy)
```

## LLM Integration Pattern

Nodes with LLM support (prompt interception, the two randomizers, the safety
switch, image analysis) share one path, `_devserver.py`:

```python
ROLE = "STAGE2_INTERCEPTION_MODEL"   # the node's job on the platform (per node)
model_choices(ROLE)                  # dropdown: platform/<ROLE> first, then GET /api/chat/models
chat(label, messages, model, ...)    # POST /api/chat/proxy -> (content, model_used); raises with the cause
```

`platform/<ROLE>` runs the settings' model for that job with the settings'
fallback chain behind it; a model id runs exactly that model, one attempt, no
fallback. The DevServer answers on `AI4ARTSED_DEVSERVER_URL`, else
`http://127.0.0.1:<PORT>` (17802 by default).

## Cache-Breaking Pattern

ComfyUI only re-executes nodes when inputs change. For randomized LLM output:

```python
# Accept INT input from Integer Randomizer (value ignored)
"random_seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff})

# Force re-execution via IS_CHANGED
@classmethod
def IS_CHANGED(cls, **kwargs):
    return float("nan")
```

## API Key Handling

Since 2026-09-12 the nodes hold no key file of their own. The key and the
OpenRouter host are the platform's, from the provider table
`devserver/config/llm_providers.json`, read through
`devserver/my_app/services/llm_providers.py` (loaded by path from
`_platform_credentials.py`): `OPENROUTER_API_KEY` in the environment, else
`devserver/openrouter.key`; the host is the EU host the key's workspace is
bound to.

Chain: Input field -> OPENROUTER_API_KEY -> devserver/openrouter.key

## Model Dropdown Format

```
openrouter/<provider>/<model> [<tag> / <price>]
local/<model> [local / $0.00]
```

Examples:
- `openrouter/anthropic/claude-sonnet-4.5 [multilingual / $3.00/$15.00]`
- `local/llama3.2:3b [local / $0.00]`

## HTTP Routes: the Tokenizers

The package registers three routes on ComfyUI's own server when it loads
(`_tokenizer_routes.py`, `install()` on the `PromptServer` ComfyUI has already
constructed; a fault there is logged and the nodes stay registered), off the
queue: they read a vocabulary file and no model, and a prompt in the queue
would wait behind every picture being made. A tokenizer is loaded from its
snapshot directory in the Hugging Face cache, never by repository id, so no
call leaves the machine. A text over `MAX_TEXT_CHARS` (100 000) answers 413;
a failure inside answers 500 as JSON with its cause.

```
POST /ai4artsed/text/tokenize         {text, model_id}    the cut, from the Hugging Face cache of this machine
POST /ai4artsed/text/tokenizer-facts  {model_ids}         {id: {available, window, matrix}}
POST /ai4artsed/text/token-count      {text, encoder}     encoder: clip_l | clip_g | t5, ComfyUI's own tokenizers
```

The package names no model: which tokenizers the DevServer's comparison
instrument offers is the DevServer's table (`devserver/config/tokenizer_catalogue.json`).

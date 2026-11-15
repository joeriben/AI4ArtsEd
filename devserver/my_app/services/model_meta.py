"""
One construction of the sheet a card shows on its back.

The frontend's ModelProvenanceCard reads a flat dict: what the config declares
about the model (publisher, architecture, parameters, licence, training data),
plus what this particular run did (backend, seed, cfg, steps, and the model it
generated with). It was built inline in the streaming route and nowhere else,
so every other way into a generation — the legacy endpoint the Latent Lab
instruments use, the canvas executor — produced media with no provenance at
all, and the cards over there had nothing to turn to.

Adding a second copy at each of those call sites is what this exists to avoid.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

# Instructions to the machine, not statements about it. They are in the config
# because the pipeline needs them; they have no place on a provenance sheet.
INTERNAL_META_KEYS = {'optimization_instruction', 'stage'}


def _chunk_default(config_params: Dict[str, Any], key: str):
    """The default the config's JSON chunk runs `key` with, or None.

    A ComfyUI chunk carries its generation numbers in its input_mappings; the
    config names only the chunk, and a run overrides a number through the
    lowercase custom parameters the executor injects. Until 2026-10-10 the
    configs on JSON chunks also carried an uppercase block (STEPS, CFG,
    WIDTH, ...) that the generation never read, and this sheet stood in with
    those numbers: 25 steps on the card of a video that ran 6 (finding S-011 of the code review of 2026-10-10). A
    config on a Python chunk keeps its block, which the router passes as
    `execute(**parameters)` and the chunk takes as named parameters; see
    `_config_number`.
    """
    name = (config_params or {}).get('OUTPUT_CHUNK')
    if not name:
        return None
    path = Path(__file__).resolve().parents[2] / 'schemas' / 'chunks' / f'{name}.json'
    try:
        mappings = json.loads(path.read_text(encoding='utf-8')).get('input_mappings') or {}
    except (OSError, ValueError):
        return None
    return (mappings.get(key) or {}).get('default')


def _config_number(config_params: Dict[str, Any], *keys: str) -> Any:
    """The first of `keys` the config carries, else the JSON chunk's default
    for the first key. The uppercase key (CFG, STEPS) is the steering of a
    Python chunk: the router calls `execute(**parameters)`, and the Diffusers
    chunks take STEPS, CFG, WIDTH, HEIGHT, NEGATIVE_PROMPT and SECONDS as
    named parameters before their own DEFAULTS (second review of 2026-10-10,
    S-011)."""
    for key in keys:
        if config_params.get(key) is not None:
            return config_params[key]
    return _chunk_default(config_params, keys[0])


def takes_no_seed(backend_type: str) -> bool:
    """Whether a run on this backend uses no seed: a cloud backend the
    provider table names, and a config model, which writes code with a
    language model (p5.js, Tone.js). The seed a request carries is not the
    run's there, and no sheet names it."""
    from my_app.services.llm_providers import names as provider_names
    return backend_type == 'config_model' or backend_type in provider_names()


def build_model_meta(
    config_obj: Any,
    *,
    seed: Optional[int] = None,
    cfg: Optional[float] = None,
    steps: Optional[int] = None,
    model_used: Optional[str] = None,
) -> Dict[str, Any]:
    """
    The sheet for one run.

    `config_obj` is a ResolvedConfig (or None, when the config could not be
    resolved — then only the run's own values remain, which is still more than
    nothing). `seed`, `cfg` and `steps` are what the run actually used; where a
    caller does not know them, the config's own lowercase parameters stand in,
    and after them the defaults of the config's JSON chunk.

    `model_used` is the model the run generated with, as the run reported it.
    Every successful generation that runs a model answers with it
    (`model_used` in the BackendResponse,
    devserver/schemas/engine/backend_router.py; the runs that load none are
    named in devserver/tests/test_model_used_coverage.py), named the way the
    backend that ran it names it: the file a ComfyUI loader loads, the
    repository id the GPU service loads from, the model an API request names.
    It is the only name the provenance card gives the model. A config's
    `display_name` names the config, which on the Latent Lab's instruments is
    the instrument ("Concept Algebra (SD 3.5)") and on the Stable Audio
    presets the preset.
    """
    config_meta = config_obj.meta if config_obj and config_obj.meta else {}
    config_params = config_obj.parameters if config_obj and config_obj.parameters else {}

    meta = {k: v for k, v in config_meta.items() if k not in INTERNAL_META_KEYS}
    meta.update({
        'backend_type': config_meta.get('backend_type', 'comfyui'),
        'seed': seed,
        'cfg': cfg if cfg is not None else _config_number(config_params, 'cfg', 'cfg_scale', 'CFG'),
        'steps': steps if steps is not None else _config_number(config_params, 'steps', 'STEPS'),
    })
    if model_used:
        meta['model_used'] = model_used
    return meta

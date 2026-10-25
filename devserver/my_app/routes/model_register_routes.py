"""What a model IS -- maker, year, how open its weights are, how big it is.

One register for the whole platform, read by every surface that offers models to
pick from, so the same model says the same thing wherever it is offered. The
facts live in devserver/config/model_register.json; nothing is derived here and
nothing is filled in when the register is silent.

Keys are the bare model name for text models and the output config id for image
models. A caller hands in whatever id it holds -- 'mammouth/glm-5.3' as well as
'glm-5.3' -- and the prefix comes off before the lookup: the same model reaches
this installation through whichever provider is configured, and an entry per
provider would go silent the moment the operator switches.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

model_register_bp = Blueprint('model_register', __name__, url_prefix='/api/models')

_REGISTER_FILE = Path(__file__).parent.parent.parent / 'config' / 'model_register.json'


def load_register() -> dict:
    """The register as it stands on disk, or an empty one.

    An unreadable register costs the cards, never the surfaces: every caller
    treats a missing entry as 'nothing known about this model', which is the
    same state a model that simply is not listed is in.
    """
    try:
        with open(_REGISTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning('[MODELS] %s not found', _REGISTER_FILE)
    except json.JSONDecodeError as e:
        logger.error('[MODELS] invalid JSON in %s: %s', _REGISTER_FILE, e)
    return {}


def bare_name(model_id: str) -> str:
    """The key an id looks up under: everything after the last slash.

    Local ids carry no prefix, cloud ids carry one or two ('openrouter/~google/
    <name>'), and a config id carries none. Taking the last segment answers all
    three without a list of providers to keep current.
    """
    return (model_id or '').rsplit('/', 1)[-1]


def facts_for(model_id: str, register: dict | None = None) -> dict | None:
    """What the register says about this model, or None while it says nothing."""
    reg = load_register() if register is None else register
    return (reg.get('models') or {}).get(bare_name(model_id))


@model_register_bp.route('/register', methods=['GET'])
def get_register():
    """The whole register, for a surface that shows several models at once.

    Handed over in one piece rather than asked per model: a row of chips would
    otherwise open a request per chip for a file that is read once and changes
    only when someone edits it.
    """
    reg = load_register()
    return jsonify({
        'models': reg.get('models') or {},
        'lineups': reg.get('interception_lineups') or {},
    })

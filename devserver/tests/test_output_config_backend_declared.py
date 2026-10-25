#!/usr/bin/env python3
"""
Policy guard: every output config declares the backend that makes its medium.

`build_model_meta` (my_app/services/model_meta.py) falls back to 'comfyui' when
a config's meta omits `backend_type`, and the line that names WHERE a medium was
made reads exactly that field (public/ai4artsed-frontend/src/views/x2x_flow.vue,
`liveIsCloud`).
A config that omits the declaration would therefore be shown as "runs on this
machine" on the strength of a default rather than of a statement — and telling a
room that its material stayed here when it did not is the one error that line
may not make.

Every config declares it today. This keeps it that way.

Run: pytest devserver/tests/test_output_config_backend_declared.py
"""

import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[1] / "schemas" / "configs" / "output"


def test_every_output_config_declares_its_backend():
    missing = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        meta = (json.loads(path.read_text()).get("meta") or {})
        if not str(meta.get("backend_type") or "").strip():
            missing.append(path.name)
    assert not missing, (
        "output configs without meta.backend_type — the surface that names where "
        "a medium was made would call these local by default: " + ", ".join(missing)
    )


def test_there_are_configs_to_check():
    # A glob that matches nothing passes the test above without checking anything.
    assert len(list(CONFIG_DIR.glob("*.json"))) > 20

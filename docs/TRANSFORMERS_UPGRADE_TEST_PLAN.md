# Transformers Upgrade Test Plan

## Why This Exists

`transformers` is pinned in the main AI4ArtsEd environment and is productively used in:

- `gpu_service/services/diffusers_backend.py`
- `gpu_service/services/text_backend.py`
- `research/t5_interpretability/*`

It is **not** just a helper-model dependency. A global upgrade in the main venv can
break productive GPU-service code paths, especially where `diffusers`, quantization,
and Hugging Face model loaders interact.

## Current Risk Assessment

Risk of global main-venv upgrade: `medium-high`

Main reasons:

- `diffusers==0.36.0` and `transformers==4.57.0` are intentionally pinned together.
- Productive code imports newer and relatively brittle classes:
  - `AutoModelForImageTextToText`
  - `PixtralProcessor`
  - `UMT5EncoderModel`
  - `TorchAoConfig`
  - `BitsAndBytesConfig`
- The GPU service is restart-fest and currently stable; breaking it would hit multiple backends at once.

## Safe Test Strategy

Do **not** touch the main venv.

Instead:

1. Create an isolated test venv.
2. Reinstall the pinned base stack there.
3. Override only `transformers` in that isolated venv.
4. Run smoke checks against the productively used import paths.

## Included Repo Assets

- Setup script:
  [scripts/test_transformers_upgrade_isolated.sh](/home/joerissen/ai/ai4artsed_development/scripts/test_transformers_upgrade_isolated.sh)

- Smoke test:
  [devserver/testfiles/test_transformers_upgrade_smoke.py](/home/joerissen/ai/ai4artsed_development/devserver/testfiles/test_transformers_upgrade_smoke.py)

## Recommended Run Modes

### 1. Baseline clone of current pins

```bash
bash scripts/test_transformers_upgrade_isolated.sh
```

This should pass. If it does not, the isolated venv itself is inconsistent and no upgrade conclusion is valid yet.

### 2. Candidate PyPI version

```bash
TEST_TRANSFORMERS_SPEC='transformers==<target-version>' \
bash scripts/test_transformers_upgrade_isolated.sh
```

### 3. Cutting-edge support for very new architectures

```bash
TEST_TRANSFORMERS_SPEC='git+https://github.com/huggingface/transformers.git' \
bash scripts/test_transformers_upgrade_isolated.sh
```

## What A Pass Means

A pass means:

- the isolated venv can still import the productive `transformers` classes AI4ArtsEd uses
- the productively relevant modules still import
- there is no immediate top-level API break

A pass does **not** yet mean:

- all productive models still load
- quantization still behaves identically
- Flux/Wan/Pixtral generations still work end-to-end

## Next Empirical Layer If Imports Pass

If the smoke test passes, the next targeted empirical checks should be:

1. Flux2 load path in `gpu_service/services/diffusers_backend.py`
2. Wan load path in `gpu_service/services/diffusers_backend.py`
3. TextBackend load path in `gpu_service/services/text_backend.py`
4. One T5 research script from `research/t5_interpretability/`

Only after that should a global main-venv upgrade even be considered.

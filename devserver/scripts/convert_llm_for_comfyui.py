#!/usr/bin/env python3
"""Write a local language model's weights as the one file ComfyUI's own
implementation of that model reads.

The local language models are Hugging Face snapshots under ComfyUI's
models/llm/ (download_llm_models.sh). For the models ComfyUI implements
itself (Qwen 3.5 and 3.8, comfy/text_encoders/qwen35.py) the table
devserver/config/local_llm_weights.json names, under "comfy_weights", a file
under ComfyUI's models/text_encoders/ per format. This script writes that
file from the folder. With the file installed the model answers on ComfyUI's
own implementation (comfyui_nodes/ai4artsed_comfyui/_comfy_llm.py); without
it, through transformers, as before.

Formats:
  mxfp8, nvfp4   ComfyUI's mixed-precision formats, 8 and 4 bit. Written
                 from the maker's FP8 release (weights with a
                 weight_scale_inv beside them, 128x128 block scales): every
                 linear weight of the language model and of the MTP head is
                 dequantized and quantized again in ComfyUI's format, with
                 its comfy_quant entry; an FP8 weight of the vision tower
                 becomes bf16; everything else is copied as stored. The
                 quantization runs on the card, under a lease of the
                 DevServer's gate.
  bf16           The maker's unquantized release, its shards laid into one
                 file, nothing recomputed. No card.

Keys keep the checkpoint's names: ComfyUI's loader renames
model.language_model. itself and finds the MTP head by mtp.fc.weight.

Usage (with ComfyUI's Python, which has torch and ComfyUI's requirements):
  <ComfyUI>/venv/bin/python devserver/scripts/convert_llm_for_comfyui.py [ALIAS [FORMAT]]
      [--comfyui PATH] [--gate URL]

  ALIAS    the table's alias of the model; without it, every model of the
           table that is installed under models/llm/ and whose default file
           is not there yet (convert_llm_weights.sh calls it so)
  FORMAT   one of the formats the table names for it; without it, the
           table's default
  --comfyui  ComfyUI's directory (default: $COMFYUI_PATH, else
             <repository>/dlbackend/ComfyUI)
  --gate     the DevServer (default: $AI4ARTSED_DEVSERVER, else
             http://127.0.0.1:17802)

An existing target is left alone and the script ends with an error. The file
is written beside its place as *.partial and renamed when it is whole.
ComfyUI lists a new file at its next validation; no restart.
"""
import argparse
import contextlib
import glob
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLE = os.path.join(REPO, "devserver", "config", "local_llm_weights.json")
QUANT_LAYOUTS = {"nvfp4": "TensorCoreNVFP4Layout", "mxfp8": "TensorCoreMXFP8Layout"}
FORMATS = tuple(QUANT_LAYOUTS) + ("bf16",)
HEARTBEAT_S = 10
# What the quantization holds on the card at a time: one weight in bf16 and
# its quantized form. 4 GB covers the largest matrix of a 27B several times.
CARD_MB = 4000


def _post(url, body, timeout=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


@contextlib.contextmanager
def gpu_lease(gate, model_id, required_mb, label):
    """The card's turn for what runs inside, with its heartbeat; given back
    on the way out. The DevServer's gate over HTTP, in stdlib: this script
    runs under ComfyUI's Python, which has no my_app. A DevServer that does
    not answer ends the script: nothing goes on the card without the turn."""
    try:
        token = _post(f"{gate}/api/gate/lease/acquire",
                      {"kind": "comfyui", "model_id": model_id, "required_mb": float(required_mb),
                       "label": label, "workload": "weight conversion"})["token"]
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        sys.exit(f"The DevServer's gate at {gate} gave no turn on the card ({type(e).__name__}: {e}). "
                 f"The quantization runs on the card and needs it; start the DevServer or name it with --gate.")
    stop = threading.Event()

    def keep_alive():
        while not stop.wait(HEARTBEAT_S):
            try:
                _post(f"{gate}/api/gate/lease/heartbeat", {"token": token}, timeout=5)
            except Exception as e:  # noqa: BLE001 -- a heartbeat may not end the run
                print(f"the lease could not be kept alive ({type(e).__name__}: {e}); asked again", flush=True)

    threading.Thread(target=keep_alive, name="convert-gate-heartbeat", daemon=True).start()
    failed = False
    try:
        yield token
    except BaseException:
        failed = True
        raise
    finally:
        stop.set()
        try:
            _post(f"{gate}/api/gate/lease/release", {"token": token, "failed": failed}, timeout=10)
        except Exception as e:  # noqa: BLE001 -- the gate's reaper collects what is left
            print(f"the lease could not be given back ({type(e).__name__}: {e})", flush=True)


def plan(alias, fmt, comfyui):
    """(folder, target file, format) for an alias, from the table."""
    with open(TABLE, encoding="utf-8") as f:
        table = json.load(f)
    name = table.get("aliases", {}).get(alias, alias)
    entry = table["models"].get(name)
    if entry is None:
        sys.exit(f"{alias} is not in {TABLE}")
    block = entry.get("comfy_weights")
    if not block:
        sys.exit(f"{alias} has no 'comfy_weights' in the table: ComfyUI has no implementation of "
                 f"its own for it that the platform uses, and the model runs through transformers")
    fmt = fmt or block["default"]
    if fmt not in block["files"]:
        sys.exit(f"{alias} has no file of the format {fmt} in the table; it names {sorted(block['files'])}")
    if fmt not in FORMATS:
        sys.exit(f"this script writes {', '.join(FORMATS)}; the table asks for {fmt}")
    folder = os.path.join(comfyui, "models", "llm", entry["dir"])
    target = os.path.join(comfyui, "models", "text_encoders", block["files"][fmt])
    return folder, target, fmt


def missing_defaults(comfyui):
    """The aliases whose folder is installed and whose default file is not
    written yet, in the table's order."""
    with open(TABLE, encoding="utf-8") as f:
        table = json.load(f)
    found = []
    for alias, entry in table["models"].items():
        block = entry.get("comfy_weights")
        if not block:
            continue
        folder = os.path.join(comfyui, "models", "llm", entry["dir"])
        target = os.path.join(comfyui, "models", "text_encoders", block["files"][block["default"]])
        if glob.glob(os.path.join(folder, "*.safetensors")) and not os.path.exists(target):
            found.append(alias)
    return found


def _dequantized(torch, weight, scale):
    """The maker's FP8 weight times its 128x128 block scales, in bf16."""
    out, inn = weight.shape
    full = scale.float().repeat_interleave(128, 0)[:out].repeat_interleave(128, 1)[:, :inn]
    return (weight.float() * full).to(torch.bfloat16)


def convert(folder, target, fmt, comfyui, gate):
    if os.path.exists(target):
        sys.exit(f"{target} exists; it is left alone")
    partial = target + ".partial"
    if os.path.exists(partial):
        sys.exit(f"{partial} exists: another run is writing it, or one ended early. "
                 f"Remove it by hand when no run is writing")
    shards = sorted(glob.glob(os.path.join(folder, "*.safetensors")))
    if not shards:
        sys.exit(f"{folder} holds no safetensors; install the model first (download_llm_models.sh)")
    os.makedirs(os.path.dirname(target), exist_ok=True)

    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file

    handles = [safe_open(f, "pt", device="cpu") for f in shards]
    where = {k: h for h in handles for k in h.keys()}
    fp8 = sorted(k for k in where if k.endswith(".weight_scale_inv"))
    started = time.time()
    out = {}
    counts = {"quantized": 0, "to bf16": 0, "copied": 0}

    if fmt == "bf16":
        if fp8:
            sys.exit(f"{folder} is an FP8 release ({len(fp8)} weights carry block scales); a bf16 file "
                     f"of it would not be the maker's unquantized weights. Convert it to mxfp8 or nvfp4")
        for k in sorted(where):
            out[k] = where[k].get_tensor(k).contiguous()
            counts["copied"] += 1
    else:
        if not fp8:
            sys.exit(f"{folder} is no FP8 release (no weight carries block scales); this script writes "
                     f"{fmt} from the maker's FP8 release only. Convert it to bf16")
        sys.path.insert(0, comfyui)
        from comfy.quant_ops import QuantizedTensor
        layout = QUANT_LAYOUTS[fmt]
        with gpu_lease(gate, f"convert/{os.path.basename(folder)}/{fmt}", CARD_MB,
                       f"convert {os.path.basename(folder)} to {fmt}"):
            for k in sorted(where):
                if k.endswith(".weight_scale_inv"):
                    continue
                tensor = where[k].get_tensor(k)
                scale_key = k[:-len("weight")] + "weight_scale_inv" if k.endswith(".weight") else None
                if scale_key is None or scale_key not in where:
                    out[k] = tensor.contiguous()
                    counts["copied"] += 1
                    continue
                weight = _dequantized(torch, tensor, where[scale_key].get_tensor(scale_key))
                language = k.startswith("model.language_model.") or k.startswith("mtp.")
                if not (language and weight.dim() == 2):
                    out[k] = weight.contiguous()
                    counts["to bf16"] += 1
                    continue
                quantized = QuantizedTensor.from_float(weight.cuda(), layout)
                for kk, vv in quantized.state_dict(k).items():
                    vv = vv.detach().to("cpu").contiguous()
                    if vv.dtype == torch.float8_e8m0fnu:
                        # safetensors has no name for this dtype; ComfyUI's
                        # loader views the bytes back (pop_scale).
                        vv = vv.view(torch.uint8)
                    out[kk] = vv
                out[k[:-len("weight")] + "comfy_quant"] = torch.tensor(
                    list(json.dumps({"format": fmt}).encode("utf-8")), dtype=torch.uint8)
                counts["quantized"] += 1
    print(f"{counts['quantized']} weights quantized ({fmt}), {counts['to bf16']} dequantized to bf16, "
          f"{counts['copied']} copied, {len(out)} keys, {time.time() - started:.0f} s", flush=True)
    save_file(out, partial, metadata={"format": "pt", "source": os.path.basename(folder), "quant": fmt})
    os.rename(partial, target)
    print(f"wrote {target}: {os.path.getsize(target)} bytes, {time.time() - started:.0f} s", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("alias", nargs="?")
    parser.add_argument("format", nargs="?", choices=FORMATS)
    parser.add_argument("--comfyui", default=os.environ.get("COMFYUI_PATH")
                        or os.path.join(REPO, "dlbackend", "ComfyUI"))
    parser.add_argument("--gate", default=os.environ.get("AI4ARTSED_DEVSERVER") or "http://127.0.0.1:17802")
    args = parser.parse_args(argv)
    comfyui = os.path.abspath(args.comfyui)
    aliases = [args.alias] if args.alias else missing_defaults(comfyui)
    if not aliases:
        print("every installed model that ComfyUI implements itself has its default file; nothing to write")
    for alias in aliases:
        folder, target, fmt = plan(alias, args.format, comfyui)
        print(f"{alias}: {folder} -> {target} ({fmt})", flush=True)
        convert(folder, target, fmt, comfyui, args.gate.rstrip("/"))


if __name__ == "__main__":
    main()

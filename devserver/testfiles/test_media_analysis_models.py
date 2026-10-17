"""
Standalone verification for the two media analysis models (Session 2026-07-10).

Loads each model directly (no GPU service involved) and describes REAL
generated outputs from exports/:
  - Audio: MiDashengLM-7B (mispeech/midashenglm-7b, trust_remote_code)
  - Video: Qwen3-VL-8B-Instruct (Qwen/Qwen3-VL-8B-Instruct + qwen-vl-utils)

Prints load time, inference time, and VRAM (torch allocated + nvidia-smi)
for each model. Models are tested sequentially with full unload in between.

Run: ./venv/bin/python devserver/testfiles/test_media_analysis_models.py
"""

import gc
import os
import subprocess
import sys
import time

# Skip the broken torchcodec install (FFmpeg/torch mismatch on this box);
# torchvision reads the videos fine.
os.environ.setdefault("FORCE_QWENVL_VIDEO_READER", "torchvision")

import torch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AUDIO_FILE = os.path.join(
    REPO,
    "exports/json/2026-07-10/65a15fb5-b926-43f7-8d08-6fcf5dfedcf7_2026-07-10",
    "run_1783695996421_ee5ce0/final/05_output_audio.mp3",
)
VIDEO_FILE = os.path.join(
    REPO,
    "exports/json/2026-07-10/65a15fb5-b926-43f7-8d08-6fcf5dfedcf7_2026-07-10",
    "run_1783696139008_b57888/final/05_output_video.mp4",
)

AUDIO_PROMPT = (
    "Listen to this audio and describe it comprehensively: overall sonic "
    "character and mood, musical elements (genre, tempo, instrumentation, "
    "melody, rhythm), sound events and textures, and any speech or vocals "
    "(content, voice character, delivery). Write a rich, flowing description "
    "that could guide someone in recreating this audio."
)
VIDEO_PROMPT = (
    "Watch this video and describe it comprehensively as it unfolds over "
    "time: the scene and setting, all visible subjects and objects, actions "
    "and movements, camera behavior, lighting, colors and atmosphere, and "
    "how everything develops from beginning to end, with reference to when "
    "things happen. Write a rich, flowing description that could guide "
    "someone in recreating this video."
)


def smi_used_mb():
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True,
    )
    return int(out.stdout.strip())


def banner(txt):
    print("\n" + "=" * 78)
    print(txt)
    print("=" * 78, flush=True)


def free_cuda():
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


def test_midashenglm():
    banner("MiDashengLM-7B — audio analysis")
    from transformers import AutoModelForCausalLM, AutoProcessor

    model_id = "mispeech/midashenglm-7b"
    smi_before = smi_used_mb()
    alloc_before = torch.cuda.memory_allocated(0)

    t0 = time.time()
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, trust_remote_code=True, dtype=torch.bfloat16, low_cpu_mem_usage=True,
    )
    model = model.to("cuda")
    model.eval()
    load_s = time.time() - t0

    alloc_after = torch.cuda.memory_allocated(0)
    smi_after = smi_used_mb()
    print(f"load time: {load_s:.1f}s")
    print(f"torch allocated: {(alloc_after - alloc_before)/1024**2:.0f} MB")
    print(f"nvidia-smi delta: {smi_after - smi_before} MB (box total now {smi_after} MB)")

    messages = [
        {"role": "system",
         "content": [{"type": "text", "text": "You are a careful listener who describes audio precisely."}]},
        {"role": "user",
         "content": [
             {"type": "text", "text": AUDIO_PROMPT},
             {"type": "audio", "path": AUDIO_FILE},
         ]},
    ]

    t0 = time.time()
    try:
        inputs = processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            add_special_tokens=True, return_dict=True,
        )
        inputs = inputs.to(device="cuda", dtype=model.dtype)
        with torch.inference_mode():
            generation = model.generate(**inputs, max_new_tokens=2048)
        # MiDashengLM generates from inputs_embeds -> output contains only new tokens
        text = processor.batch_decode(generation, skip_special_tokens=True)[0]
        used_path = "audio-as-path"
    except Exception as e:
        print(f"path-based audio input failed ({type(e).__name__}: {e}); retrying with librosa array")
        import librosa
        wav, sr = librosa.load(AUDIO_FILE, sr=None, mono=True)
        messages[1]["content"][1] = {"type": "audio", "audio": wav, "sampling_rate": sr}
        inputs = processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            add_special_tokens=True, return_dict=True,
        )
        inputs = inputs.to(device="cuda", dtype=model.dtype)
        with torch.inference_mode():
            generation = model.generate(**inputs, max_new_tokens=2048)
        text = processor.batch_decode(generation, skip_special_tokens=True)[0]
        used_path = "audio-as-array"

    infer_s = time.time() - t0
    peak = torch.cuda.max_memory_allocated(0)
    print(f"inference time: {infer_s:.1f}s  (input mode: {used_path})")
    print(f"torch peak allocated during run: {peak/1024**2:.0f} MB")
    print("\n----- AUDIO ANALYSIS -----")
    print(text.strip())
    print("----- END -----")

    del model, processor, inputs, generation
    free_cuda()
    print(f"after unload: nvidia-smi {smi_used_mb()} MB, torch alloc {torch.cuda.memory_allocated(0)/1024**2:.0f} MB")


def test_qwen3vl():
    banner("Qwen3-VL-8B-Instruct — video analysis")
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from qwen_vl_utils import process_vision_info

    model_id = "Qwen/Qwen3-VL-8B-Instruct"
    smi_before = smi_used_mb()
    torch.cuda.reset_peak_memory_stats(0)
    alloc_before = torch.cuda.memory_allocated(0)

    t0 = time.time()
    processor = AutoProcessor.from_pretrained(model_id)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_id, dtype=torch.bfloat16, low_cpu_mem_usage=True,
    )
    model = model.to("cuda")
    model.eval()
    load_s = time.time() - t0

    alloc_after = torch.cuda.memory_allocated(0)
    smi_after = smi_used_mb()
    print(f"load time: {load_s:.1f}s")
    print(f"torch allocated: {(alloc_after - alloc_before)/1024**2:.0f} MB")
    print(f"nvidia-smi delta: {smi_after - smi_before} MB (box total now {smi_after} MB)")

    messages = [
        {"role": "user",
         "content": [
             {"type": "video", "video": "file://" + VIDEO_FILE},
             {"type": "text", "text": VIDEO_PROMPT},
         ]},
    ]

    t0 = time.time()
    text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    mode = None
    try:
        images, videos, video_kwargs = process_vision_info(
            messages, image_patch_size=16,
            return_video_kwargs=True, return_video_metadata=True,
        )
        if videos is not None:
            videos, metadatas = zip(*videos)
            videos, metadatas = list(videos), list(metadatas)
        else:
            metadatas = None
        inputs = processor(
            text=[text_prompt], images=images, videos=videos,
            video_metadata=metadatas, do_resize=False,
            return_tensors="pt", **video_kwargs,
        )
        mode = "qwen-vl-utils"
    except Exception as e:
        print(f"qwen-vl-utils path failed ({type(e).__name__}: {e}); trying native transformers video path")
        native_messages = [
            {"role": "user",
             "content": [
                 {"type": "video", "path": VIDEO_FILE},
                 {"type": "text", "text": VIDEO_PROMPT},
             ]},
        ]
        inputs = processor.apply_chat_template(
            native_messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt",
        )
        mode = "transformers-native"

    inputs = inputs.to("cuda")
    n_video_tokens = int((inputs["input_ids"] == model.config.video_token_id).sum()) if hasattr(model.config, "video_token_id") else -1
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=2048)
    out_ids = generated[:, inputs["input_ids"].shape[1]:]
    text = processor.batch_decode(out_ids, skip_special_tokens=True)[0]
    infer_s = time.time() - t0

    peak = torch.cuda.max_memory_allocated(0)
    print(f"inference time: {infer_s:.1f}s  (vision path: {mode}, video tokens: {n_video_tokens})")
    print(f"torch peak allocated during run: {peak/1024**2:.0f} MB")
    print("\n----- VIDEO ANALYSIS -----")
    print(text.strip())
    print("----- END -----")

    del model, processor, inputs, generated
    free_cuda()
    print(f"after unload: nvidia-smi {smi_used_mb()} MB, torch alloc {torch.cuda.memory_allocated(0)/1024**2:.0f} MB")


if __name__ == "__main__":
    for f in (AUDIO_FILE, VIDEO_FILE):
        if not os.path.exists(f):
            print(f"MISSING TEST FILE: {f}")
            sys.exit(1)
    print(f"audio file: {AUDIO_FILE}")
    print(f"video file: {VIDEO_FILE}")
    print(f"GPU used at start: {smi_used_mb()} MB")

    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("audio", "both"):
        test_midashenglm()
    if which in ("video", "both"):
        test_qwen3vl()

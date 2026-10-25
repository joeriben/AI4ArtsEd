"""Stable Audio 3, run by ComfyUI.

Stage 6 of the move to ComfyUI: what gpu_service/services/
stable_audio_backend.py did with stable-audio-tools, letter for letter, under
ComfyUI's memory management (_card). Text to audio, audio from a prompt
embedding the caller manipulated (the audio synth of the cross-aesthetic
surface, _audio_synth), and audio guided by an ImageBind image embedding
(the image-guided generation, with _imagebind).

The weights are folders under <ComfyUI>/models/stable_audio/<dir>/: the
repository of a Stable Audio 3 checkpoint as it is published --
model_config.json, model.safetensors, and the text conditioner (t5gemma) in
the subfolder the config names. The conditioner is read from that subfolder
here, so a listed folder loads without the hub.

SA3 facts (model_config.json of the medium checkpoint): t5gemma prompt
conditioner, max_length 256, output dim 768; seconds_total conditioning only
(no seconds_start); 44100 Hz, stereo, autoencoder downsampling ratio 4096,
rectified-flow DiT. The model is post-trained for few-step inference: 8
steps, the pingpong sampler, cfg_scale 1.0 (model card and
training.demo.demo_steps). generate_diffusion_cond_inpaint is the entry
point because the medium DiT declares inpaint local conditioning
(inpaint_mask, inpaint_masked_input), which that function supplies as zeros
for pure generation.
"""
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple

import torch

from . import _card, _whole

logger = logging.getLogger(__name__)

FOLDER_NAME = "stable_audio"
KEEP_BUILT = 2

SA3_DEFAULT_STEPS = 8
SA3_DEFAULT_CFG_SCALE = 1.0
SA3_SAMPLER_TYPE = "pingpong"

# The platform's ceiling on one generation (gpu_config STABLE_AUDIO_MAX_DURATION);
# the checkpoint's own ceiling (sample_size / sample_rate) applies where it
# is lower: the small checkpoints render 120 s, the medium 380 s.
MAX_DURATION_S = 240.0

# What a generation needs on the card beyond the weights: the activations of
# the DiT and the autoencoder's decode of up to MAX_DURATION_S of stereo at
# 44.1 kHz in float32. The GPU service loaded the model whole with a 6000 MB
# request to its coordinator and ran every duration inside it.
RESERVE_BYTES = 6 * 1024 ** 3
# A guided run keeps the decode graph and ImageBind's audio tower for the
# backward pass of every warm-up step, at 10 s of audio.
GUIDED_RESERVE_BYTES = 16 * 1024 ** 3

_card.register_folder(FOLDER_NAME)
_registry = _card.Registry("StableAudio", KEEP_BUILT)


# ---------------------------------------------------------------------------
# The folders.

def whole(path: str) -> bool:
    """A checkpoint folder, as _whole.stable_audio defines it for both
    sides: model_config.json, the weights, and every text conditioner
    subfolder the config names, whole."""
    return _whole.whole("stable_audio", path)


def installed_dirs():
    return _card.listed_dirs(FOLDER_NAME, whole)


def weights_path(dir_name: str) -> str:
    return _card.folder_path(FOLDER_NAME, dir_name, whole)


# ---------------------------------------------------------------------------
# The model.

class Loaded:
    """What a generation reads off a built checkpoint."""

    def __init__(self, held: Any):
        self.held = held
        self.model = held.module.sa3
        self.config: dict = held.extra["config"]
        self.sample_rate = int(self.config.get("sample_rate", 44100))
        self.max_sample_size = int(self.config.get("sample_size", 0))
        native_max = self.max_sample_size / float(self.sample_rate)
        self.max_duration = min(MAX_DURATION_S, native_max) if native_max > 0 else MAX_DURATION_S
        self.downsampling_ratio = held.extra["downsampling_ratio"]

    def aligned_sample_size(self, duration_seconds: float) -> int:
        """Audio-sample count for `duration_seconds`, rounded UP to the
        autoencoder downsampling ratio and capped at the model maximum."""
        target = int(round(duration_seconds * self.sample_rate))
        ds = self.downsampling_ratio
        aligned = ((target + ds - 1) // ds) * ds
        return max(ds, min(aligned, self.max_sample_size))

    def clamp_duration(self, duration_seconds: float) -> float:
        if duration_seconds > self.max_duration:
            logger.warning(f"[AI4ArtsEd StableAudio] {duration_seconds:.1f}s requested, this "
                           f"checkpoint tops out at {self.max_duration:.1f}s; generating that")
        return min(duration_seconds, self.max_duration)


def _build(dir_name: str) -> Any:
    """Read the checkpoint into RAM and wrap it for ComfyUI. Nothing goes on
    the card here; on_card does that per call."""
    from stable_audio_tools.models.factory import create_model_from_config
    from stable_audio_tools.models.utils import load_ckpt_state_dict

    path = weights_path(dir_name)
    config = _whole.stable_audio_config(path)
    # The text conditioner is read from its subfolder of this folder, not
    # from the hub: the config as published names repo_id + subfolder, and
    # the conditioner takes model_path in their place.
    for c in (config.get("model", {}).get("conditioning", {}) or {}).get("configs", []) or []:
        cc = c.get("config") or {}
        sub = cc.get("subfolder")
        if sub:
            cc["model_path"] = os.path.join(path, sub)
            cc.pop("repo_id", None)
            cc.pop("subfolder", None)
    logger.info(f"[AI4ArtsEd StableAudio] Building {dir_name} from {path}")
    model = create_model_from_config(config)
    weights = os.path.join(path, "model.safetensors")
    if not os.path.isfile(weights):
        weights = os.path.join(path, "model.ckpt")
    model.load_state_dict(load_ckpt_state_dict(weights))
    # float32 whole, the GPU service's operating point (STABLE_AUDIO_DTYPE):
    # the autoencoder decodes in float32 for stability, and the DiT was run
    # in float32 with it.
    model = model.to(torch.float32).eval()
    try:
        ds = int(model.pretransform.downsampling_ratio)
    except Exception:
        ds = 4096
    container = _card.Container(sa3=model)
    return _card.Held(key=dir_name, patcher=_card.wrap(container), module=container,
                      weight_bytes=_card.module_bytes(container),
                      extra={"config": config, "downsampling_ratio": ds})


def get_built(dir_name: str) -> Any:
    return _registry.get(dir_name, _build, _card.bytes_of_files(weights_path(dir_name)))


def on_card(held: Any, reserve: int = RESERVE_BYTES) -> torch.device:
    return _card.on_card(held, reserve, held.key)


# ---------------------------------------------------------------------------
# Generation.

def _postprocess(audio) -> torch.Tensor:
    """Peak-normalize to [-1, 1] (RF output can exceed unit range) and return
    a float32 CPU tensor shaped [channels, samples]."""
    audio = audio.to(torch.float32).cpu()
    peak = torch.max(torch.abs(audio))
    if peak > 0:
        audio = audio / peak
    return audio.clamp(-1.0, 1.0)



def _progress(steps: int):
    """The sampler's callback: ComfyUI's progress bar for the run, and the
    interrupt between steps."""
    import comfy.utils
    bar = comfy.utils.ProgressBar(steps)

    def callback(_info):
        _card.interrupted()
        bar.update(1)
    return callback


def generate(dir_name: str, prompt: str, duration_seconds: float = 10.0,
             negative_prompt: str = "", steps: int = SA3_DEFAULT_STEPS,
             cfg_scale: float = SA3_DEFAULT_CFG_SCALE, seed: int = 0) -> Tuple[torch.Tensor, int, float]:
    """Text to audio: (audio [channels, samples] float32 on the CPU, sample
    rate, the duration generated)."""
    from stable_audio_tools.inference.generation import generate_diffusion_cond_inpaint

    held = get_built(dir_name)
    with held.lock:
        loaded = Loaded(held)
        device = on_card(held, RESERVE_BYTES)
        duration_seconds = loaded.clamp_duration(duration_seconds)
        sample_size = loaded.aligned_sample_size(duration_seconds)
        conditioning = [{"prompt": prompt, "seconds_total": duration_seconds}]
        negative_conditioning = ([{"prompt": negative_prompt, "seconds_total": duration_seconds}]
                                 if negative_prompt else None)
        logger.info(f"[AI4ArtsEd StableAudio] Generating: prompt='{prompt[:80]}', "
                    f"duration={duration_seconds}s, steps={steps}, cfg={cfg_scale}, seed={seed}")
        with torch.no_grad():
            audio = generate_diffusion_cond_inpaint(
                loaded.model,
                conditioning=conditioning,
                negative_conditioning=negative_conditioning,
                steps=steps,
                cfg_scale=cfg_scale,
                sample_size=sample_size,
                seed=seed,
                device=device,
                # The wrapper pops sampler_type with default "euler", past the
                # sampler's own RF auto-default, so pingpong is passed by name.
                sampler_type=SA3_SAMPLER_TYPE,
                callback=_progress(steps),
            )
        audio = _postprocess(audio[0])
        audio = audio[:, : int(round(duration_seconds * loaded.sample_rate))]
        return audio, loaded.sample_rate, duration_seconds


def encode_prompt(dir_name: str, text: str) -> Tuple[torch.Tensor, torch.Tensor]:
    """The t5gemma conditioner's output for a text: (prompt_embeds [1, 256, 768],
    attention_mask [1, 256]) on the card. The seconds_total used here is
    throwaway (re-applied at generation time)."""
    held = get_built(dir_name)
    with held.lock:
        loaded = Loaded(held)
        device = on_card(held, RESERVE_BYTES)
        with torch.no_grad():
            cond = loaded.model.conditioner([{"prompt": text, "seconds_total": 10.0}], device)
        emb, mask = cond["prompt"]
        return emb, mask


def generate_from_embeddings(dir_name: str, prompt_embeds: torch.Tensor,
                             attention_mask: Optional[torch.Tensor],
                             duration_seconds: float, steps: int = SA3_DEFAULT_STEPS,
                             cfg_scale: float = SA3_DEFAULT_CFG_SCALE,
                             seed: int = 0) -> Tuple[torch.Tensor, int, float]:
    """Audio from a prompt embedding the caller computed (the audio synth):
    the tensor goes into the conditioning dict in place of the text.

    CFG: the negative branch uses zeros in the SAME conditioning space
    (zeros_like(prompt_embeds)), not a text-encoded "": for a manipulated
    embedding the two spaces differ, and a text negative would make the CFG
    subtraction meaningless.
    """
    from stable_audio_tools.inference.generation import generate_diffusion_cond_inpaint

    held = get_built(dir_name)
    with held.lock:
        loaded = Loaded(held)
        device = on_card(held, RESERVE_BYTES)
        duration = max(0.1, min(duration_seconds, loaded.max_duration))
        model_dtype = next(loaded.model.model.parameters()).dtype
        prompt_embeds = prompt_embeds.to(device=device, dtype=model_dtype)
        if attention_mask is not None:
            attention_mask = attention_mask.to(device=device).bool()
        else:
            attention_mask = torch.ones(prompt_embeds.shape[:2], device=device, dtype=torch.bool)
        with torch.no_grad():
            # The conditioner is run only for the seconds_total tensor; the
            # prompt is the injected embedding.
            base = loaded.model.conditioner([{"prompt": "", "seconds_total": duration}], device)
            seconds_tensor = base["seconds_total"]
            cond_tensors = {"prompt": [prompt_embeds, attention_mask], "seconds_total": seconds_tensor}
            neg_tensors = {"prompt": [torch.zeros_like(prompt_embeds), torch.ones_like(attention_mask)],
                           "seconds_total": seconds_tensor}
            sample_size = loaded.aligned_sample_size(duration)
            logger.info(f"[AI4ArtsEd StableAudio] Generating from embeddings: "
                        f"shape={list(prompt_embeds.shape)}, duration={duration}s, steps={steps}, seed={seed}")
            audio = generate_diffusion_cond_inpaint(
                loaded.model,
                conditioning_tensors=cond_tensors,
                negative_conditioning_tensors=neg_tensors,
                steps=steps,
                cfg_scale=cfg_scale,
                sample_size=sample_size,
                seed=seed,
                device=device,
                sampler_type=SA3_SAMPLER_TYPE,
                callback=_progress(steps),
            )
        audio = _postprocess(audio[0])
        audio = audio[:, : int(round(duration * loaded.sample_rate))]
        return audio, loaded.sample_rate, duration


@contextmanager
def _grad_through_decode(pretransform):
    """Let the gradient pass through the autoencoder decode.

    AudioAutoencoder.decode runs its own inner pretransform (the STFT stage)
    under torch.no_grad() unless that pretransform carries enable_grad. With
    the flag off the autograd graph is cut inside the decode: no gradient
    ever reaches the latent, nothing raises, and a guided step silently
    degenerates into an unguided one. Open the flag for the guided decode
    only -- left open, it would keep a decode graph alive on every ordinary
    generation.
    """
    inner = getattr(getattr(pretransform, "model", None), "pretransform", None)
    previous = getattr(inner, "enable_grad", None)
    if inner is not None:
        inner.enable_grad = True
    try:
        yield
    finally:
        if inner is not None and previous is not None:
            inner.enable_grad = previous


# ImageBind audio constants (ImageBind/imagebind/data.py)
IB_SR = 16000
IB_N_MELS = 128
IB_TARGET_LEN = 204
IB_CLIP_DUR = 2.0
IB_N_CLIPS = 3
IB_MEAN = -4.268
IB_STD = 9.138
IB_CLIP_SAMPLES = int(IB_CLIP_DUR * IB_SR)  # 32000
MAX_GRAD_NORM = 1.0


def waveform_to_imagebind_tensor(audio: torch.Tensor, sample_rate: int) -> torch.Tensor:
    """Differentiable analog of ImageBind's load_and_transform_audio_data.
    audio: [B, channels, n_samples] at sample_rate (SA3: stereo, 44100 Hz).
    Returns [B, 3, 1, 128, 204], ready for imagebind_model({AUDIO: ...})."""
    import torch.nn.functional as F
    import torchaudio
    import torchaudio.functional as ta_f

    w = audio.mean(dim=1, keepdim=True) if audio.shape[1] > 1 else audio
    if sample_rate != IB_SR:
        w = ta_f.resample(w, sample_rate, IB_SR)
    n_samples = w.shape[-1]
    duration_w = n_samples / IB_SR
    available = max(0.0, duration_w - IB_CLIP_DUR)
    # Uniform clip start positions (ConstantClipsPerVideoSampler)
    if IB_N_CLIPS > 1:
        starts = [i / (IB_N_CLIPS - 1) * available for i in range(IB_N_CLIPS)]
    else:
        starts = [0.0]
    B_ = w.shape[0]
    clips_out = []
    for pos in starts:
        s = int(pos * IB_SR)
        e = s + IB_CLIP_SAMPLES
        clip = w[..., s:e]
        if clip.shape[-1] < IB_CLIP_SAMPLES:
            clip = F.pad(clip, (0, IB_CLIP_SAMPLES - clip.shape[-1]))
        mel_batch = []
        for b in range(B_):
            wb = clip[b]  # [1, IB_CLIP_SAMPLES]
            wb = wb - wb.mean()
            fb = torchaudio.compliance.kaldi.fbank(
                wb, htk_compat=True, sample_frequency=IB_SR, use_energy=False,
                window_type="hanning", num_mel_bins=IB_N_MELS, dither=0.0,
                frame_length=25, frame_shift=10,
            )
            fb = fb.transpose(0, 1)  # [n_mels, n_frames]
            n_f = fb.shape[1]
            if n_f < IB_TARGET_LEN:
                fb = F.pad(fb, (0, IB_TARGET_LEN - n_f))
            else:
                fb = fb[:, :IB_TARGET_LEN]
            fb = fb.unsqueeze(0)  # [1, n_mels, target_len]
            fb = (fb - IB_MEAN) / IB_STD
            mel_batch.append(fb)
        clips_out.append(torch.stack(mel_batch, dim=0))  # [B, 1, 128, 204]
    return torch.stack(clips_out, dim=1)  # [B, n_clips, 1, 128, 204]


def generate_guided(dir_name: str, imagebind_dir: str, image, prompt: str = "",
                    lambda_guidance: float = 5.0, warmup_steps: int = 8,
                    total_steps: int = SA3_DEFAULT_STEPS, duration_seconds: float = 10.0,
                    cfg_scale: float = SA3_DEFAULT_CFG_SCALE, seed: int = 0) -> Dict[str, Any]:
    """Image to audio via ImageBind gradient guidance, on the RF sampler.

    A pingpong sampling loop with a guided step: at each warm-up step, the
    denoised prediction x0 = x - t * v(x, t) is decoded to audio, the
    audio's ImageBind embedding is compared (cosine) with the image's, and
    the gradient of that similarity with respect to the latent, norm-clipped,
    moves the latent (x <- x + lambda * grad) before the ordinary denoising
    step. After the warm-up the loop runs unguided.

    Returns {audio, sample_rate, duration_seconds, cosine_similarity, seed}.
    """
    import torch.nn.functional as F
    from imagebind.models.imagebind_model import ModalityType
    from stable_audio_tools.inference.sampling import build_schedule

    from . import _imagebind

    t_start = time.time()
    held = get_built(dir_name)
    ib_held = _imagebind.get_built(imagebind_dir)
    # The guided step differentiates through the DiT, the autoencoder and
    # ImageBind; under ComfyUI's inference mode no tensor could be saved for
    # that backward, so the whole run, the move to the card included, is
    # taken out of inference mode (_card.autograd_ready).
    with held.lock, ib_held.lock, torch.inference_mode(False):
        loaded = Loaded(held)
        # Both models on the card in one load, so that making room for the
        # second cannot take the first off again.
        device = _card.on_card_together([held, ib_held], GUIDED_RESERVE_BYTES, held.key)
        _card.autograd_ready(held.module, ib_held.module)
        ib_model = ib_held.module.imagebind
        image_emb = _imagebind.encode_image(ib_held, image).to(device).detach()  # [1, 1024]

        duration_seconds = loaded.clamp_duration(duration_seconds)
        effective_warmup = min(warmup_steps, total_steps)
        torch.manual_seed(seed)

        sample_size = loaded.aligned_sample_size(duration_seconds)
        latent_size = sample_size // loaded.downsampling_ratio
        batch_size = 1
        model = loaded.model
        model_dtype = next(model.model.parameters()).dtype
        pretransform = model.pretransform
        pretransform_dtype = next(pretransform.parameters()).dtype

        cond_tensors = model.conditioner([{"prompt": prompt, "seconds_total": duration_seconds}], device)
        neg_tensors = model.conditioner([{"prompt": "", "seconds_total": duration_seconds}], device)
        # SA3 medium requires inpaint local conditioning (zeros = pure generation)
        zero_mask = torch.zeros((batch_size, 1, latent_size), device=device)
        zero_input = torch.zeros((batch_size, model.io_channels, latent_size), device=device)
        cond_tensors["inpaint_mask"] = [zero_mask]
        cond_tensors["inpaint_masked_input"] = [zero_input]
        neg_tensors["inpaint_mask"] = [zero_mask]
        neg_tensors["inpaint_masked_input"] = [zero_input]
        cond_inputs = model.get_conditioning_inputs(cond_tensors)
        neg_cond_inputs = model.get_conditioning_inputs(neg_tensors, negative=True)
        # The conditioner is a full text encoder and runs in grad mode here,
        # so its outputs carry a graph -- and the same graph is reused by
        # every guidance step. The first backward() frees it and the next
        # step dies with "backward through the graph a second time". The
        # conditioning is a constant for the guidance, so it is cut loose.
        cond_inputs = {k: (v.detach().type(model_dtype) if torch.is_tensor(v) else v)
                       for k, v in cond_inputs.items()}
        neg_cond_inputs = {k: (v.detach() if torch.is_tensor(v) else v)
                           for k, v in neg_cond_inputs.items()}
        extra_args = {**cond_inputs, **neg_cond_inputs, "cfg_scale": cfg_scale,
                      "batch_cfg": True, "rescale_cfg": True}

        sigmas = build_schedule(
            steps=total_steps, sigma_max=1.0,
            dist_shift=getattr(model, "sampling_dist_shift", None),
            effective_seq_len=None, fallback_seq_len=latent_size,
            include_endpoint=True, device=device,
        )
        noise = torch.randn([batch_size, model.io_channels, latent_size], dtype=model_dtype, device=device)

        x = noise
        t = sigmas
        num_steps = t.shape[-1] - 1
        last_cos_sim = 0.0
        skipped_steps = 0
        progress = _progress(num_steps)
        logger.info(f"[AI4ArtsEd StableAudio] Guided: total_steps={total_steps}, "
                    f"warmup={effective_warmup}, lambda={lambda_guidance}, "
                    f"duration={duration_seconds}s, seed={seed}")

        for i in range(num_steps):
            t_curr = t[i].to(x.dtype)
            t_next = t[i + 1].to(x.dtype)
            t_curr_tensor = t_curr * torch.ones((batch_size,), dtype=x.dtype, device=device)

            if i < effective_warmup:
                try:
                    with torch.enable_grad():
                        z = x.detach().requires_grad_(True)
                        # The DiT's attention lowers to Triton's FlexAttention.
                        # In float32 its BACKWARD kernels ask for 128-224 KB
                        # of shared memory per block; the card offers 99 KB,
                        # so autotuning finds no valid config and the guided
                        # step dies without ever producing audio. In bfloat16
                        # the kernel fits. Only the DiT runs reduced: the
                        # autoencoder stays float32 for decode stability, and
                        # the gradient is norm-clipped anyway, so it is used
                        # as a direction, not as a precise value.
                        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                            v = model.model(z, t_curr_tensor, **extra_args)
                        v = v.to(z.dtype)
                        x0_pred = z - t_curr * v
                        with _grad_through_decode(pretransform):
                            audio_pred = pretransform.decode(x0_pred.to(pretransform_dtype))
                        ib_input = waveform_to_imagebind_tensor(audio_pred.to(torch.float32), loaded.sample_rate)
                        ib_out = ib_model({ModalityType.AUDIO: ib_input})
                        audio_emb = ib_out[ModalityType.AUDIO]  # [B, 1024]
                        cos_sim = F.cosine_similarity(audio_emb, image_emb, dim=-1).mean()
                        cos_sim.backward()
                except Exception as step_err:
                    # The GPU service's loop logged this and went on unguided,
                    # and the page reported a guided run. A step that cannot be
                    # guided ends the run, with the step and the cause.
                    raise RuntimeError(
                        f"guidance step {i} of {num_steps} failed: {step_err!r}") from step_err
                if z.grad is None:
                    # No gradient reached the latent: the graph is cut somewhere
                    # between the latent and the ImageBind embedding (a decode
                    # under no_grad, a model whose parameters were not made
                    # autograd-ready). The step would run unguided.
                    raise RuntimeError(
                        f"guidance step {i} of {num_steps}: no gradient reached the latent")
                grad = z.grad.detach()
                grad_norm = grad.norm()
                if torch.isnan(grad_norm) or torch.isinf(grad_norm):
                    # A numerical event of one step: the step runs unguided,
                    # and the count is in the answer.
                    skipped_steps += 1
                    logger.warning(f"[AI4ArtsEd StableAudio] Guided step {i}: NaN/inf gradient, "
                                   f"step runs unguided ({skipped_steps} so far)")
                else:
                    # Clip the gradient norm for stability across image
                    # types; not scaled by t_curr (not classifier guidance).
                    if grad_norm > MAX_GRAD_NORM:
                        grad = grad * (MAX_GRAD_NORM / grad_norm)
                    x = (x + lambda_guidance * grad).detach()
                    last_cos_sim = cos_sim.item()

            with torch.no_grad():
                v2 = model.model(x, t_curr_tensor, **extra_args)
                denoised = x - t_curr * v2
            # Pingpong: fresh noise reinjection (sample_flow_pingpong)
            x = (1 - t_next) * denoised + t_next * torch.randn_like(x)
            progress(None)

        with torch.no_grad():
            audio = pretransform.decode(x.to(pretransform_dtype))
        audio = _postprocess(audio[0])
        audio = audio[:, : int(round(duration_seconds * loaded.sample_rate))]
        return {
            "audio": audio,
            "sample_rate": loaded.sample_rate,
            "duration_seconds": duration_seconds,
            "cosine_similarity": float(last_cos_sim),
            "guidance_steps_skipped": skipped_steps,
            "seed": seed,
            "generation_time_ms": int((time.time() - t_start) * 1000),
        }

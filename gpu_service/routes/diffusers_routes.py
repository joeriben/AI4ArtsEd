"""
GPU Service Diffusers Routes

REST endpoints for all Diffusers generation methods.
Each endpoint maps 1:1 to a DiffusersImageGenerator method.
"""

from routes._async import run_async
import base64
import logging
from flask import Blueprint, request, jsonify

from services.gpu_admission import GpuBusy, gated
from services.generation_cancel import GenerationCancelled, request_cancel
from services.generation_failure import GenerationFailed

logger = logging.getLogger(__name__)

# The model the routes here fall back to when a body names none, from config:
# `available()` below ANSWERS it, so that the DevServer's forwarding can say
# which model a cell is about to be drawn by instead of writing a second copy
# of the name into its own code.
from config import DEFAULT_MODEL_ID

diffusers_bp = Blueprint('diffusers', __name__)


@diffusers_bp.before_request
def _clear_an_older_stop():
    """A fresh request under this label supersedes an older stop.

    The four marks are carried for the whole service in app.py. What stays here
    is this blueprint's own business: run ids are reused when somebody cancels
    and presses again, and a mark that no run ever read — the stop came while
    the run was still queued for the card — would otherwise kill the retry at
    its first step. The DevServer keeps the same rule for its own mark
    (`generation_abort.unmark`). Safe by order: a stop can only be asked for
    after the request it concerns has begun.

    The label is read from the body again — cached, so it costs nothing — and
    not from the context var the app hook sets. Reading the var would make this
    depend on that hook having run FOR THIS REQUEST; the day it does not, this
    reads the previous request's label off the same waitress thread and clears
    a stranger's stop, and that run keeps computing after somebody pressed it.
    """
    label = ""
    try:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            label = str(body.get("run_label") or "")
    except Exception:
        label = ""
    if label and request.endpoint != 'diffusers.cancel':
        from services.generation_cancel import clear_cancel
        clear_cancel(label)


def _get_backend():
    from services.diffusers_backend import get_diffusers_backend
    return get_diffusers_backend()


@diffusers_bp.route('/api/diffusers/progress', methods=['GET'])
def generation_progress():
    """Current generation step progress for frontend polling."""
    from services.diffusers_backend import get_generation_progress
    return jsonify(get_generation_progress())


@diffusers_bp.route('/api/diffusers/cancel', methods=['POST'])
def cancel():
    """Stop the run named in `run_label` -- the twin of ComfyUI's cancel_job.

    The label is the DevServer's run id, the same one every generation
    request already carries. Marking a run that is not running is harmless
    and deliberately answered with 200: the DevServer cannot know whether
    the card had already started, and a stop pressed a moment too late is
    not an error. The mark is swept after half an hour if no run reads it.
    """
    data = request.get_json(silent=True) or {}
    run_label = str(data.get('run_label') or '')
    if not run_label:
        return jsonify({"cancelled": False, "reason": "run_label required"}), 400
    request_cancel(run_label)
    return jsonify({"cancelled": True, "run_label": run_label})


@diffusers_bp.route('/api/diffusers/available', methods=['GET'])
def available():
    """Check if Diffusers backend is available."""
    try:
        from config import DIFFUSERS_ENABLED
        if not DIFFUSERS_ENABLED:
            return jsonify({"available": False, "reason": "disabled"})
        backend = _get_backend()
        is_available = run_async(backend.is_available())
        return jsonify({"available": is_available,
                        "default_model": DEFAULT_MODEL_ID})
    except Exception as e:
        return jsonify({"available": False, "reason": str(e)})


@diffusers_bp.route('/api/diffusers/gpu_info', methods=['GET'])
def gpu_info():
    """Get GPU memory information."""
    backend = _get_backend()
    info = run_async(backend.get_gpu_info())
    return jsonify(info)



@diffusers_bp.route('/api/diffusers/load', methods=['POST'])
def load():
    """Preload a model into GPU memory without generating.

    Used by workshop planning to measure real VRAM cost.
    Body: { "model_id": "sd35_large", "pipeline_class": "StableDiffusion3Pipeline" }
    Returns: { "success": true/false, "model_id": "...", "error": "..." }
    """
    data = request.get_json(silent=True) or {}
    model_id = data.get('model_id')
    pipeline_class = data.get('pipeline_class', 'StableDiffusion3Pipeline')
    prefetch = bool(data.get('prefetch'))
    if not model_id:
        return jsonify({"success": False, "error": "model_id required"}), 400
    if prefetch:
        # A prefetch loads beside a running operation without taking the slot.
        # Whether that is safe is decided HERE, against the gate's own measured
        # arithmetic — never on the caller's say-so. A caller that asks for a
        # prefetch the gate does not currently recommend gets a plain refusal.
        from services.gpu_admission import get_gpu_admission
        advice = get_gpu_admission().prefetch_advice()
        rec = advice.get("recommended") or {}
        if rec.get("model_id") != model_id:
            return jsonify({"success": False, "model_id": model_id, "prefetched": False,
                            "error": f"not warming now: {advice.get('reason', 'no room')}"}), 409
        if not get_gpu_admission().prefetch_claim(model_id):
            return jsonify({"success": False, "model_id": model_id, "prefetched": False,
                            "error": "another warm-up is already running"}), 409
    try:
        backend = _get_backend()
        result = run_async(backend.load_model(model_id, pipeline_class, prefetch=prefetch))
        return jsonify({"success": result, "model_id": model_id, "prefetched": prefetch})
    except GpuBusy:
        raise   # app-level handler answers 503; a busy card is not a failed load
    except Exception as e:
        logger.error(f"[DIFFUSERS] Preload failed for {model_id}: {e}")
        return jsonify({"success": False, "model_id": model_id, "error": str(e)}), 500
    finally:
        if prefetch:
            from services.gpu_admission import get_gpu_admission
            get_gpu_admission().prefetch_done(model_id)


@diffusers_bp.route('/api/diffusers/unload', methods=['POST'])
@gated("diffusers-unload")
def unload():
    """Unload a model from GPU."""
    data = request.get_json(silent=True) or {}
    model_id = data.get('model_id')
    backend = _get_backend()
    result = run_async(backend.unload_model(model_id))
    return jsonify({"success": result})


@diffusers_bp.route('/api/diffusers/encode-info', methods=['POST'])
def encode_info():
    """Analyze how the three SD3.5 text encoders process a prompt.

    Returns tokenization, per-token embedding norms, and encoder agreement.
    Body: { "prompt": "...", "model_id": "..." (optional) }
    Returns: { clip_l, clip_g, t5, encoder_agreement }
    """
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt', '')
    if not prompt:
        return jsonify({"error": "prompt required"}), 400

    backend = _get_backend()
    result = run_async(backend.encode_prompt_info(
        prompt=prompt,
        model_id=data.get('model_id', DEFAULT_MODEL_ID),
    ))

    if 'error' in result:
        return jsonify(result), 500

    return jsonify(result)


@diffusers_bp.route('/api/diffusers/generate', methods=['POST'])
def generate():
    """Standard image generation.

    Returns: { success, image_base64 }
    With `keep_latent`, and only where a latent can be kept, also:
    { latent_base64, latent_meta } -- see Mean Images.
    """
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"success": False, "error": "prompt required"}), 400

    backend = _get_backend()
    # Optional per-encoder prompts for SD3.5 triple-prompt support
    extra_kwargs = {}
    if 'prompt_2' in data:
        extra_kwargs['prompt_2'] = data['prompt_2']
    if 'prompt_3' in data:
        extra_kwargs['prompt_3'] = data['prompt_3']
    # Flux2 visual conditioning / SD3.5 img2img: pass through image bytes
    if 'image_base64' in data:
        extra_kwargs['image_bytes'] = base64.b64decode(data['image_base64'])
    if 'strength' in data:
        extra_kwargs['strength'] = float(data['strength'])
    keep_latent = bool(data.get('keep_latent'))
    latent_sink = {} if keep_latent else None
    try:
        image_bytes = run_async(backend.generate_image(
            prompt=data['prompt'],
            model_id=data.get('model_id', DEFAULT_MODEL_ID),
            negative_prompt=data.get('negative_prompt', ''),
            width=int(data.get('width', 1024)),
            height=int(data.get('height', 1024)),
            steps=int(data.get('steps', 25)),
            cfg_scale=float(data.get('cfg_scale', 4.5)),
            seed=int(data.get('seed', -1)),
            pipeline_class=data.get('pipeline_class', 'StableDiffusion3Pipeline'),
            loras=data.get('loras'),
            keep_latent=keep_latent,
            latent_sink=latent_sink,
            **extra_kwargs,
        ))
    except GenerationCancelled:
        # Asked for. Not a failure, and deliberately not a picture: after an
        # interrupt the pipeline hands back half-denoised latents.
        return jsonify({"success": False, "cancelled": True,
                        "error": "cancelled"}), 409
    except GenerationFailed as failure:
        # The reason CUDA or the pipeline gave, in its own words. The caller
        # reads it: a card that ran out of memory must not be answered by
        # starting a second model on the same card.
        return jsonify({"success": False, "error": str(failure)}), 500

    if image_bytes is None:
        return jsonify({"success": False,
                        "error": "the backend returned no image and no reason"}), 500

    answer = {
        "success": True,
        "image_base64": base64.b64encode(image_bytes).decode('utf-8'),
    }
    # An empty sink is not a failure. The flag is a wish: img2img and every
    # pipeline that is not SD3.5 text-to-image keep no latent, and the caller
    # reads the absence and takes its mean the other way.
    if latent_sink:
        answer["latent_base64"] = base64.b64encode(latent_sink["latent"]).decode('utf-8')
        answer["latent_meta"] = latent_sink["meta"]
    return jsonify(answer)



@diffusers_bp.route('/api/diffusers/generate/fusion', methods=['POST'])
def generate_fusion():
    """T5-CLIP fusion generation (Surrealizer).

    Returns: { success, image_base64 }
    """
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"success": False, "error": "prompt required"}), 400

    backend = _get_backend()
    try:
        image_bytes = run_async(backend.generate_image_with_fusion(
            prompt=data['prompt'],
            t5_prompt=data.get('t5_prompt'),
            alpha_factor=float(data.get('alpha_factor', 0.0)),
            model_id=data.get('model_id', DEFAULT_MODEL_ID),
            negative_prompt=data.get('negative_prompt', ''),
            width=int(data.get('width', 1024)),
            height=int(data.get('height', 1024)),
            steps=int(data.get('steps', 25)),
            cfg_scale=float(data.get('cfg_scale', 4.5)),
            seed=int(data.get('seed', -1)),
            loras=data.get('loras'),
            fusion_strategy=data.get('fusion_strategy', 'legacy'),
            pooled_prompt=data.get('pooled_prompt'),
        ))
    except ValueError as e:
        # An option the backend refuses (Folge-Reihe I, 2026-09-13) reaches the
        # caller as the sentence naming the cause, with a 400, and never as a
        # Flask 500 page.
        return jsonify({"success": False, "error": str(e)}), 400

    if image_bytes is None:
        return jsonify({"success": False, "error": "Fusion generation failed"}), 500

    return jsonify({
        "success": True,
        "image_base64": base64.b64encode(image_bytes).decode('utf-8'),
    })




@diffusers_bp.route('/api/diffusers/generate/decomposition', methods=['POST'])
def generate_decomposition():
    """Decomposition mode — 3×3×3 intervention space.

    Source prompt is encoded baseline; up to 3 stream overrides (clip_l, clip_g, t5)
    are injected during configured step phases and layer bands.

    Required:
      - source_prompt: str

    Optional per stream (each independent):
      - <stream>_prompt: str | null   # null = baseline (no override)
      - <stream>_step_bands:  list ⊆ {composition, semantics, detail}  # default = all
      - <stream>_layer_bands: list ⊆ {shallow, middle, deep}          # default = all

    Plus alpha (-1..1) and standard image params.

    Returns: { success, image_base64 }
    """
    data = request.get_json()
    if not data or 'source_prompt' not in data:
        return jsonify({"success": False, "error": "source_prompt required"}), 400

    def _maybe_list(v):
        return v if isinstance(v, list) else None

    backend = _get_backend()
    try:
        image_bytes = run_async(backend.generate_image_with_decomposition(
            source_prompt=data['source_prompt'],
            cells=_maybe_list(data.get('cells')),
            clip_l_prompt=data.get('clip_l_prompt') or None,
            clip_l_step_bands=_maybe_list(data.get('clip_l_step_bands')),
            clip_l_layer_bands=_maybe_list(data.get('clip_l_layer_bands')),
            clip_g_prompt=data.get('clip_g_prompt') or None,
            clip_g_step_bands=_maybe_list(data.get('clip_g_step_bands')),
            clip_g_layer_bands=_maybe_list(data.get('clip_g_layer_bands')),
            t5_prompt=data.get('t5_prompt') or None,
            t5_step_bands=_maybe_list(data.get('t5_step_bands')),
            t5_layer_bands=_maybe_list(data.get('t5_layer_bands')),
            alpha=float(data.get('alpha', 1.0)),
            model_id=data.get('model_id', DEFAULT_MODEL_ID),
            negative_prompt=data.get('negative_prompt', ''),
            width=int(data.get('width', 1024)),
            height=int(data.get('height', 1024)),
            steps=int(data.get('steps', 25)),
            cfg_scale=float(data.get('cfg_scale', 5.5)),
            seed=int(data.get('seed', -1)),
        ))
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400

    if image_bytes is None:
        return jsonify({"success": False, "error": "Decomposition generation failed"}), 500

    return jsonify({
        "success": True,
        "image_base64": base64.b64encode(image_bytes).decode('utf-8'),
    })



@diffusers_bp.route('/api/diffusers/generate/attention', methods=['POST'])
def generate_attention():
    """Attention cartography generation.

    Returns: { success, image_base64, tokens, word_groups, attention_maps,
               spatial_resolution, image_resolution, seed, capture_layers, capture_steps }
    """
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"success": False, "error": "prompt required"}), 400

    backend = _get_backend()
    result = run_async(backend.generate_image_with_attention(
        prompt=data['prompt'],
        model_id=data.get('model_id', DEFAULT_MODEL_ID),
        negative_prompt=data.get('negative_prompt', ''),
        width=int(data.get('width', 1024)),
        height=int(data.get('height', 1024)),
        steps=int(data.get('steps', 25)),
        cfg_scale=float(data.get('cfg_scale', 4.5)),
        seed=int(data.get('seed', -1)),
        capture_layers=data.get('capture_layers'),
        capture_every_n_steps=int(data.get('capture_every_n_steps', 5)),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Attention generation failed"}), 500

    result["success"] = True
    return jsonify(result)


@diffusers_bp.route('/api/diffusers/generate/probing', methods=['POST'])
def generate_probing():
    """Feature probing generation.

    Returns: { success, image_base64, probing_data, seed } or { error }
    """
    data = request.get_json()
    if not data or 'prompt_a' not in data or 'prompt_b' not in data:
        return jsonify({"success": False, "error": "prompt_a and prompt_b required"}), 400

    backend = _get_backend()
    result = run_async(backend.generate_image_with_probing(
        prompt_a=data['prompt_a'],
        prompt_b=data['prompt_b'],
        encoder=data.get('encoder', 't5'),
        transfer_dims=data.get('transfer_dims'),
        negative_prompt=data.get('negative_prompt', ''),
        width=int(data.get('width', 1024)),
        height=int(data.get('height', 1024)),
        steps=int(data.get('steps', 25)),
        cfg_scale=float(data.get('cfg_scale', 4.5)),
        seed=int(data.get('seed', -1)),
        model_id=data.get('model_id', DEFAULT_MODEL_ID),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Probing generation failed"}), 500

    if 'error' in result:
        return jsonify({"success": False, "error": result['error']}), 500

    result["success"] = True
    return jsonify(result)


@diffusers_bp.route('/api/diffusers/generate/algebra', methods=['POST'])
def generate_algebra():
    """Concept algebra generation.

    Returns: { success, reference_image, result_image, algebra_data, seed }
    """
    data = request.get_json()
    if not data or 'prompt_a' not in data:
        return jsonify({"success": False, "error": "prompt_a required"}), 400

    backend = _get_backend()
    result = run_async(backend.generate_image_with_algebra(
        prompt_a=data['prompt_a'],
        prompt_b=data.get('prompt_b', ''),
        prompt_c=data.get('prompt_c', ''),
        encoder=data.get('encoder', 'all'),
        scale_sub=float(data.get('scale_sub', 1.0)),
        scale_add=float(data.get('scale_add', 1.0)),
        negative_prompt=data.get('negative_prompt', ''),
        width=int(data.get('width', 1024)),
        height=int(data.get('height', 1024)),
        steps=int(data.get('steps', 25)),
        cfg_scale=float(data.get('cfg_scale', 4.5)),
        seed=int(data.get('seed', -1)),
        model_id=data.get('model_id', DEFAULT_MODEL_ID),
        generate_reference=data.get('generate_reference', True),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Algebra generation failed"}), 500

    result["success"] = True
    return jsonify(result)


@diffusers_bp.route('/api/diffusers/generate/video', methods=['POST'])
def generate_video():
    """Text-to-video generation.

    Returns: { success, video_base64, seed }
    """
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"success": False, "error": "prompt required"}), 400

    backend = _get_backend()
    try:
        extra_kwargs = {}
        if 'guidance_scale_2' in data:
            extra_kwargs['guidance_scale_2'] = float(data['guidance_scale_2'])

        video_bytes = run_async(backend.generate_video(
            prompt=data['prompt'],
            model_id=data.get('model_id', 'Wan-AI/Wan2.2-T2V-A14B-Diffusers'),
            negative_prompt=data.get('negative_prompt', ''),
            width=int(data.get('width', 1280)),
            height=int(data.get('height', 720)),
            num_frames=int(data.get('num_frames', 81)),
            steps=int(data.get('steps', 40)),
            cfg_scale=float(data.get('cfg_scale', 4.0)),
            fps=int(data.get('fps', 16)),
            seed=int(data.get('seed', -1)),
            pipeline_class=data.get('pipeline_class', 'WanPipeline'),
            **extra_kwargs,
        ))
    except GpuBusy:
        raise   # 503 via the app-level handler — busy, not broken
    except GenerationCancelled:
        return jsonify({"success": False, "cancelled": True,
                        "error": "cancelled"}), 409
    except Exception as e:
        import traceback
        logger.error(f"Video generation error: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500

    if video_bytes is None:
        return jsonify({"success": False, "error": "Video generation returned None (check GPU service logs)"}), 500

    return jsonify({
        "success": True,
        "video_base64": base64.b64encode(video_bytes).decode('utf-8'),
    })


@diffusers_bp.route('/api/diffusers/generate/video/i2v', methods=['POST'])
def generate_video_i2v():
    """Image-to-video generation.

    Returns: { success, video_base64 }
    """
    data = request.get_json()
    if not data or 'image_base64' not in data:
        return jsonify({"success": False, "error": "image_base64 required"}), 400

    backend = _get_backend()
    try:
        image_bytes = base64.b64decode(data['image_base64'])

        extra_kwargs = {}
        if 'guidance_scale_2' in data:
            extra_kwargs['guidance_scale_2'] = float(data['guidance_scale_2'])

        video_bytes = run_async(backend.generate_video_from_image(
            image_bytes=image_bytes,
            prompt=data.get('prompt', ''),
            model_id=data.get('model_id', 'Wan-AI/Wan2.2-I2V-A14B-Diffusers'),
            negative_prompt=data.get('negative_prompt', ''),
            width=int(data.get('width', 1280)),
            height=int(data.get('height', 720)),
            num_frames=int(data.get('num_frames', 81)),
            steps=int(data.get('steps', 40)),
            cfg_scale=float(data.get('cfg_scale', 4.0)),
            fps=int(data.get('fps', 16)),
            seed=int(data.get('seed', -1)),
            **extra_kwargs,
        ))
    except GpuBusy:
        raise   # 503 via the app-level handler — busy, not broken
    except GenerationCancelled:
        return jsonify({"success": False, "cancelled": True,
                        "error": "cancelled"}), 409
    except Exception as e:
        import traceback
        logger.error(f"I2V video generation error: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500

    if video_bytes is None:
        return jsonify({"success": False, "error": "I2V generation returned None (check GPU service logs)"}), 500

    return jsonify({
        "success": True,
        "video_base64": base64.b64encode(video_bytes).decode('utf-8'),
    })


@diffusers_bp.route('/api/diffusers/generate/archaeology', methods=['POST'])
def generate_archaeology():
    """Denoising archaeology generation.

    Returns: { success, image_base64, step_images, seed, total_steps }
    """
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"success": False, "error": "prompt required"}), 400

    backend = _get_backend()
    result = run_async(backend.generate_image_with_archaeology(
        prompt=data['prompt'],
        model_id=data.get('model_id', DEFAULT_MODEL_ID),
        negative_prompt=data.get('negative_prompt', ''),
        width=int(data.get('width', 1024)),
        height=int(data.get('height', 1024)),
        steps=int(data.get('steps', 25)),
        cfg_scale=float(data.get('cfg_scale', 4.5)),
        seed=int(data.get('seed', -1)),
        capture_every_n=int(data.get('capture_every_n', 1)),
        pipeline_class=data.get('pipeline_class', 'StableDiffusion3Pipeline'),
        scheduler=data.get('scheduler'),
        shift=data.get('shift'),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Archaeology generation failed"}), 500

    result["success"] = True
    return jsonify(result)


@diffusers_bp.route('/api/diffusers/generate/composable', methods=['POST'])
def generate_composable():
    """Composable Diffusion: per-concept noise prediction blending.

    Request body:
        concepts: [{"prompt": str, "weight": float}, ...]
        negative_prompt: str (optional)
        width/height: int (optional, default 1024)
        steps: int (optional, default 25)
        cfg_scale: float (optional, default 4.5)
        seed: int (optional, -1 for random)
        normalize_weights: bool (optional, default true)

    Returns: { success, image_base64, seed, concept_count, weights_used, timing_s }
    """
    data = request.get_json()
    if not data or 'concepts' not in data:
        return jsonify({"success": False, "error": "concepts required"}), 400

    concepts = data['concepts']
    if not isinstance(concepts, list) or len(concepts) < 2:
        return jsonify({"success": False, "error": "Need at least 2 concepts"}), 400

    for i, c in enumerate(concepts):
        if not isinstance(c, dict) or 'prompt' not in c:
            return jsonify({"success": False, "error": f"Concept {i} missing 'prompt'"}), 400

    try:
        backend = _get_backend()
        result = run_async(backend.generate_image_composable(
            concepts=concepts,
            model_id=data.get('model_id', DEFAULT_MODEL_ID),
            negative_prompt=data.get('negative_prompt', ''),
            width=int(data.get('width', 1024)),
            height=int(data.get('height', 1024)),
            steps=int(data.get('steps', 25)),
            cfg_scale=float(data.get('cfg_scale', 4.5)),
            seed=int(data.get('seed', -1)),
            normalize_weights=data.get('normalize_weights', True),
        ))

        if result is None:
            return jsonify({"success": False, "error": "Composable generation failed"}), 500

        result["success"] = True
        return jsonify(result)

    except GpuBusy:
        raise   # 503 via the app-level handler — busy, not broken
    except Exception as e:
        logger.error(f"Composable generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500




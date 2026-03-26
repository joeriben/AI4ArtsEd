"""
GPU Service Diffusers Routes

REST endpoints for all Diffusers generation methods.
Each endpoint maps 1:1 to a DiffusersImageGenerator method.
"""

import asyncio
import base64
import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

diffusers_bp = Blueprint('diffusers', __name__)


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_backend():
    from services.diffusers_backend import get_diffusers_backend
    return get_diffusers_backend()


@diffusers_bp.route('/api/diffusers/progress', methods=['GET'])
def generation_progress():
    """Current generation step progress for frontend polling."""
    from services.diffusers_backend import get_generation_progress
    return jsonify(get_generation_progress())


@diffusers_bp.route('/api/diffusers/available', methods=['GET'])
def available():
    """Check if Diffusers backend is available."""
    try:
        from config import DIFFUSERS_ENABLED
        if not DIFFUSERS_ENABLED:
            return jsonify({"available": False, "reason": "disabled"})
        backend = _get_backend()
        is_available = _run_async(backend.is_available())
        return jsonify({"available": is_available})
    except Exception as e:
        return jsonify({"available": False, "reason": str(e)})


@diffusers_bp.route('/api/diffusers/gpu_info', methods=['GET'])
def gpu_info():
    """Get GPU memory information."""
    backend = _get_backend()
    info = _run_async(backend.get_gpu_info())
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
    if not model_id:
        return jsonify({"success": False, "error": "model_id required"}), 400
    try:
        backend = _get_backend()
        result = _run_async(backend.load_model(model_id, pipeline_class))
        return jsonify({"success": result, "model_id": model_id})
    except Exception as e:
        logger.error(f"[DIFFUSERS] Preload failed for {model_id}: {e}")
        return jsonify({"success": False, "model_id": model_id, "error": str(e)}), 500


@diffusers_bp.route('/api/diffusers/unload', methods=['POST'])
def unload():
    """Unload a model from GPU."""
    data = request.get_json(silent=True) or {}
    model_id = data.get('model_id')
    backend = _get_backend()
    result = _run_async(backend.unload_model(model_id))
    return jsonify({"success": result})


@diffusers_bp.route('/api/diffusers/generate', methods=['POST'])
def generate():
    """Standard image generation.

    Returns: { success, image_base64, seed }
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
    # Flux2 visual conditioning: pass through image bytes
    if 'image_base64' in data:
        extra_kwargs['image_bytes'] = base64.b64decode(data['image_base64'])
    image_bytes = _run_async(backend.generate_image(
        prompt=data['prompt'],
        model_id=data.get('model_id', 'stabilityai/stable-diffusion-3.5-large'),
        negative_prompt=data.get('negative_prompt', ''),
        width=int(data.get('width', 1024)),
        height=int(data.get('height', 1024)),
        steps=int(data.get('steps', 25)),
        cfg_scale=float(data.get('cfg_scale', 4.5)),
        seed=int(data.get('seed', -1)),
        pipeline_class=data.get('pipeline_class', 'StableDiffusion3Pipeline'),
        loras=data.get('loras'),
        **extra_kwargs,
    ))

    if image_bytes is None:
        return jsonify({"success": False, "error": "Generation failed"}), 500

    return jsonify({
        "success": True,
        "image_base64": base64.b64encode(image_bytes).decode('utf-8'),
    })


@diffusers_bp.route('/api/diffusers/generate/fusion', methods=['POST'])
def generate_fusion():
    """T5-CLIP fusion generation (Surrealizer).

    Returns: { success, image_base64 }
    """
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"success": False, "error": "prompt required"}), 400

    backend = _get_backend()
    image_bytes = _run_async(backend.generate_image_with_fusion(
        prompt=data['prompt'],
        t5_prompt=data.get('t5_prompt'),
        alpha_factor=float(data.get('alpha_factor', 0.0)),
        model_id=data.get('model_id', 'stabilityai/stable-diffusion-3.5-large'),
        negative_prompt=data.get('negative_prompt', ''),
        width=int(data.get('width', 1024)),
        height=int(data.get('height', 1024)),
        steps=int(data.get('steps', 25)),
        cfg_scale=float(data.get('cfg_scale', 4.5)),
        seed=int(data.get('seed', -1)),
        loras=data.get('loras'),
        fusion_strategy=data.get('fusion_strategy', 'legacy'),
    ))

    if image_bytes is None:
        return jsonify({"success": False, "error": "Fusion generation failed"}), 500

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
    result = _run_async(backend.generate_image_with_attention(
        prompt=data['prompt'],
        model_id=data.get('model_id', 'stabilityai/stable-diffusion-3.5-large'),
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
    result = _run_async(backend.generate_image_with_probing(
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
        model_id=data.get('model_id', 'stabilityai/stable-diffusion-3.5-large'),
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
    result = _run_async(backend.generate_image_with_algebra(
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
        model_id=data.get('model_id', 'stabilityai/stable-diffusion-3.5-large'),
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

        video_bytes = _run_async(backend.generate_video(
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

        video_bytes = _run_async(backend.generate_video_from_image(
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
    result = _run_async(backend.generate_image_with_archaeology(
        prompt=data['prompt'],
        model_id=data.get('model_id', 'stabilityai/stable-diffusion-3.5-large'),
        negative_prompt=data.get('negative_prompt', ''),
        width=int(data.get('width', 1024)),
        height=int(data.get('height', 1024)),
        steps=int(data.get('steps', 25)),
        cfg_scale=float(data.get('cfg_scale', 4.5)),
        seed=int(data.get('seed', -1)),
        capture_every_n=int(data.get('capture_every_n', 1)),
    ))

    if result is None:
        return jsonify({"success": False, "error": "Archaeology generation failed"}), 500

    result["success"] = True
    return jsonify(result)


@diffusers_bp.route('/api/diffusers/mosaic/segment', methods=['POST'])
def mosaic_segment():
    """Segment attention maps into discrete regions for Arcimboldo Mosaic.

    Request body:
        attention_maps: {step_N: {layer_M: [[int]]}}
        tokens: [str]
        word_groups: [[int]]
        spatial_resolution: [h, w]
        image_base64: str
        grid_size: int (optional, default 16)

    Returns: { success, regions, grid_assignment, grid_size, label_map }
    """
    data = request.get_json()
    if not data or 'attention_maps' not in data:
        return jsonify({"success": False, "error": "attention_maps required"}), 400

    try:
        from services.mosaic_segmentation import segment_attention_maps

        result = segment_attention_maps(
            attention_maps=data['attention_maps'],
            tokens=data['tokens'],
            word_groups=data['word_groups'],
            spatial_resolution=data['spatial_resolution'],
            image_base64=data['image_base64'],
            grid_size=int(data.get('grid_size', 16)),
            selected_layers=data.get('selected_layers'),
            min_region_fraction=float(data.get('min_region_fraction', 0.02)),
        )

        result["success"] = True
        return jsonify(result)

    except Exception as e:
        logger.error(f"Mosaic segmentation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@diffusers_bp.route('/api/diffusers/mosaic/generate-tiles', methods=['POST'])
def mosaic_generate_tiles():
    """Generate tiles via img2img from original image patches.

    Request body:
        grid_assignment: [[int]] grid of region indices
        regions: [{"idx": int, "label": str}]
        original_image_base64: str
        strength: float (optional, default 0.7)
        steps: int (optional, default 8)
        cfg_scale: float (optional, default 3.5)
        seed: int (optional, -1 for random)

    Returns: { success, tiles: {"row_col": base64}, seed, total_generated }
    """
    data = request.get_json()
    if not data or 'grid_assignment' not in data:
        return jsonify({"success": False, "error": "grid_assignment required"}), 400
    if 'original_image_base64' not in data:
        return jsonify({"success": False, "error": "original_image_base64 required"}), 400

    # Build region_labels lookup
    regions = data.get('regions', [])
    region_labels = {str(r.get('idx', i)): r.get('label', 'object') for i, r in enumerate(regions)}

    try:
        backend = _get_backend()
        result = _run_async(backend.generate_mosaic_tiles(
            grid_assignment=data['grid_assignment'],
            region_labels=region_labels,
            original_image_base64=data['original_image_base64'],
            steps=int(data.get('steps', 8)),
            cfg_scale=float(data.get('cfg_scale', 3.5)),
            strength=float(data.get('strength', 0.7)),
            seed=int(data.get('seed', -1)),
        ))

        if result is None:
            return jsonify({"success": False, "error": "Tile generation failed"}), 500

        result["success"] = True
        return jsonify(result)

    except Exception as e:
        logger.error(f"Mosaic tile generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@diffusers_bp.route('/api/diffusers/mosaic/compose', methods=['POST'])
def mosaic_compose():
    """Assemble tiles into final mosaic image.

    Request body:
        grid_assignment: [[int]]
        tiles: {region_idx: [base64]}
        output_width/height: int (optional, default 1024)

    Returns: { success, mosaic_base64 }
    """
    data = request.get_json()
    if not data or 'grid_assignment' not in data or 'tiles' not in data:
        return jsonify({"success": False, "error": "grid_assignment and tiles required"}), 400

    try:
        from services.mosaic_segmentation import compose_mosaic

        mosaic_bytes = compose_mosaic(
            tiles=data['tiles'],
            grid_h=int(data.get('grid_h', 16)),
            grid_w=int(data.get('grid_w', 16)),
            output_width=int(data.get('output_width', 1024)),
            output_height=int(data.get('output_height', 1024)),
        )

        return jsonify({
            "success": True,
            "mosaic_base64": base64.b64encode(mosaic_bytes).decode('utf-8'),
        })

    except Exception as e:
        logger.error(f"Mosaic composition error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


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
        result = _run_async(backend.generate_image_composable(
            concepts=concepts,
            model_id=data.get('model_id', 'stabilityai/stable-diffusion-3.5-large'),
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

    except Exception as e:
        logger.error(f"Composable generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

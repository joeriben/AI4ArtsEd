"""
Output Chunk: Hunyuan3D-2 (Image-to-3D Mesh)

Generates textured 3D meshes from input images using Hunyuan3D-2.
Two-step process:
  1. GPU Service: Hunyuan3D-2 generates a textured GLB mesh from an image
  2. Blender Service: Headless Eevee renders a preview PNG thumbnail

Input (from pipeline parameters):
    - input_image / image_base64: Base64-encoded image (from previous generation or upload)
    - seed: Seed for reproducibility

Output:
    - dict with mesh_data (base64 GLB) + image_data (base64 PNG thumbnail)
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Chunk metadata
CHUNK_META = {
    "name": "output_3d_hunyuan3d",
    "media_type": "3d",
    "output_format": "glb",
    "secondary_format": "png",
    "backend": "hunyuan3d",
    "backend_type": "hunyuan3d",
    "model_id": "tencent/Hunyuan3D-2",
    "estimated_duration_seconds": "30-60",
    "requires_gpu": True,
    "gpu_vram_mb": 16000,
    "img2img": True,
    "optimization_instruction": (
        "This chunk converts an input image into a 3D model. "
        "No text optimization needed — the image IS the input."
    ),
}

# Defaults
DEFAULTS = {
    "seed": "random",
    "num_inference_steps": 50,
    "guidance_scale": 7.5,
    "octree_resolution": 256,
    "camera_distance": 2.5,
    "camera_elevation": 30.0,
    "camera_azimuth": 45.0,
    "render_resolution": 1024,
}


async def execute(
    TEXT_1: str = None,
    TEXT_2: str = None,
    PREVIOUS_OUTPUT: str = None,
    seed: str = None,
    seed_override: int = None,
    OUTPUT_CHUNK: str = None,
    _chunk_name: str = None,
    # 3D-specific parameters
    num_inference_steps: int = None,
    guidance_scale: float = None,
    octree_resolution: int = None,
    # Blender render parameters
    camera_distance: float = None,
    camera_elevation: float = None,
    camera_azimuth: float = None,
    render_resolution: int = None,
    **kwargs
) -> dict:
    """
    Execute Hunyuan3D-2 mesh generation + Blender preview render.

    Returns a dict with:
    - content_marker: 'hunyuan3d_generated'
    - mesh_data: base64-encoded GLB bytes
    - image_data: base64-encoded PNG thumbnail (if Blender available)
    - media_type: '3d'
    """
    from my_app.services.hunyuan3d_client import get_hunyuan3d_client
    from my_app.services.blender_service import get_blender_service
    from my_app.services.backend_registry import get_backend_registry
    import random
    import base64
    import tempfile
    from pathlib import Path

    # --- Check backend availability ---
    registry = get_backend_registry()
    if not registry.is_enabled("hunyuan3d"):
        raise Exception("Hunyuan3D backend disabled in registry")

    client = get_hunyuan3d_client()
    if not await client.is_available():
        raise Exception("Hunyuan3D backend not available (GPU service unreachable or hy3dgen not installed)")

    # --- Get image input ---
    # input_image arrives as a server file path (e.g., /uploads/xxx.png)
    # We need to read it and convert to base64 for the GPU service
    input_image_path = kwargs.get('input_image') or None
    image_b64 = kwargs.get('image_base64') or None

    if not image_b64 and input_image_path:
        # Read image file from server path and encode as base64
        import os
        from pathlib import Path

        # Resolve relative paths against the devserver working directory
        if input_image_path.startswith('/uploads/'):
            full_path = Path(os.environ.get('DEVSERVER_ROOT', '.')) / input_image_path.lstrip('/')
        else:
            full_path = Path(input_image_path)

        if full_path.exists():
            with open(full_path, 'rb') as f:
                image_b64 = base64.b64encode(f.read()).decode('utf-8')
            logger.info(f"[CHUNK:hunyuan3d] Read image from {full_path}: {len(image_b64)//1024}KB base64")
        else:
            logger.warning(f"[CHUNK:hunyuan3d] Image path not found: {full_path}")

    # Fallback: PREVIOUS_OUTPUT might be base64 image data
    if not image_b64 and PREVIOUS_OUTPUT:
        if PREVIOUS_OUTPUT.startswith('data:image/'):
            image_b64 = PREVIOUS_OUTPUT.split(',', 1)[1] if ',' in PREVIOUS_OUTPUT else PREVIOUS_OUTPUT
        elif len(PREVIOUS_OUTPUT) > 1000 and not PREVIOUS_OUTPUT.startswith('{'):
            image_b64 = PREVIOUS_OUTPUT

    if not image_b64:
        raise ValueError(
            "No image provided for 3D generation. Hunyuan3D-2 requires an input image. "
            f"input_image={input_image_path}, PREVIOUS_OUTPUT={'set' if PREVIOUS_OUTPUT else 'empty'}"
        )

    # Seed handling
    actual_seed = seed_override if seed_override is not None else seed
    if actual_seed is None or actual_seed == "random" or actual_seed == -1:
        actual_seed = random.randint(0, 2**32 - 1)
        logger.info(f"[CHUNK:hunyuan3d] Generated random seed: {actual_seed}")
    else:
        actual_seed = int(actual_seed)

    steps = int(num_inference_steps) if num_inference_steps is not None else DEFAULTS["num_inference_steps"]
    cfg = float(guidance_scale) if guidance_scale is not None else DEFAULTS["guidance_scale"]
    octree_res = int(octree_resolution) if octree_resolution is not None else DEFAULTS["octree_resolution"]

    # --- Step 1: Generate mesh via GPU service ---
    logger.info(f"[CHUNK:hunyuan3d] Generating mesh: image={len(image_b64)//1024}KB, seed={actual_seed}")

    glb_bytes, actual_seed = await client.generate_mesh(
        image_base64=image_b64,
        seed=actual_seed,
        num_inference_steps=steps,
        guidance_scale=cfg,
        octree_resolution=octree_res,
    )

    if not glb_bytes:
        raise Exception("Hunyuan3D mesh generation returned empty result")

    logger.info(f"[CHUNK:hunyuan3d] Mesh generated: {len(glb_bytes)} bytes")

    # --- Step 2: Blender preview render (optional, fail-safe) ---
    image_data_b64 = None
    blender = get_blender_service()

    if blender.is_available():
        try:
            # Write GLB to temp file
            with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as tmp_glb:
                tmp_glb.write(glb_bytes)
                tmp_glb_path = tmp_glb.name

            tmp_png_path = tmp_glb_path.replace('.glb', '.png')

            cam_dist = float(camera_distance) if camera_distance is not None else DEFAULTS["camera_distance"]
            cam_elev = float(camera_elevation) if camera_elevation is not None else DEFAULTS["camera_elevation"]
            cam_azim = float(camera_azimuth) if camera_azimuth is not None else DEFAULTS["camera_azimuth"]
            render_res = int(render_resolution) if render_resolution is not None else DEFAULTS["render_resolution"]

            success = await blender.render_mesh(
                glb_path=tmp_glb_path,
                output_path=tmp_png_path,
                camera_distance=cam_dist,
                camera_elevation=cam_elev,
                camera_azimuth=cam_azim,
                resolution=render_res,
            )

            if success and Path(tmp_png_path).exists():
                with open(tmp_png_path, 'rb') as f:
                    image_data_b64 = base64.b64encode(f.read()).decode('utf-8')
                logger.info(f"[CHUNK:hunyuan3d] Blender preview rendered successfully")

            # Cleanup temp files
            Path(tmp_glb_path).unlink(missing_ok=True)
            Path(tmp_png_path).unlink(missing_ok=True)

        except Exception as e:
            logger.warning(f"[CHUNK:hunyuan3d] Blender render failed (non-fatal): {e}")
    else:
        logger.info("[CHUNK:hunyuan3d] Blender not available, skipping preview render")

    # --- Return structured dict ---
    result = {
        "content_marker": "hunyuan3d_generated",
        "chunk_name": "output_3d_hunyuan3d",
        "media_type": "3d",
        "backend": "hunyuan3d",
        "seed": actual_seed,
        "mesh_data": base64.b64encode(glb_bytes).decode('utf-8'),
        "mesh_format": "glb",
        "parameters": {
            "prompt": prompt[:200],
            "steps": steps,
            "guidance_scale": cfg,
            "octree_resolution": octree_res,
        },
    }

    if image_data_b64:
        result["image_data"] = image_data_b64

    return result

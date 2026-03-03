"""
Diffusers HTTP Client — Drop-in replacement for DiffusersImageGenerator

Calls the shared GPU service (port 17803) via HTTP REST instead of
loading models in-process. All method signatures and return types
are identical to DiffusersImageGenerator.

Callers (backend_router.py, chunk files) require zero changes.
"""

import base64
import logging
from typing import Optional, Dict, Any, Callable, AsyncGenerator

logger = logging.getLogger(__name__)


class DiffusersClient:
    """HTTP client for the shared GPU service.

    Drop-in replacement for DiffusersImageGenerator.
    All methods have identical signatures and return types.
    """

    def __init__(self):
        from config import GPU_SERVICE_URL, GPU_SERVICE_TIMEOUT_IMAGE, GPU_SERVICE_TIMEOUT_VIDEO
        self.base_url = GPU_SERVICE_URL.rstrip('/')
        self.timeout_image = GPU_SERVICE_TIMEOUT_IMAGE
        self.timeout_video = GPU_SERVICE_TIMEOUT_VIDEO
        logger.info(f"[DIFFUSERS-CLIENT] Initialized: url={self.base_url}, image={self.timeout_image}s, video={self.timeout_video}s")

    def _post(self, path: str, data: dict, timeout: Optional[int] = None) -> Optional[dict]:
        """Synchronous POST to GPU service. Returns JSON response or None."""
        import requests
        t = timeout or self.timeout_image
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=data, timeout=t)
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            logger.error(f"[DIFFUSERS-CLIENT] GPU service unreachable at {url}")
            return None
        except requests.Timeout:
            logger.error(f"[DIFFUSERS-CLIENT] Request timed out after {t}s: {path}")
            return None
        except Exception as e:
            logger.error(f"[DIFFUSERS-CLIENT] Request failed: {e}")
            return None

    def _get(self, path: str) -> Optional[dict]:
        """Synchronous GET to GPU service. Returns JSON response or None."""
        import requests
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[DIFFUSERS-CLIENT] GET failed: {e}")
            return None

    async def is_available(self) -> bool:
        """Check if GPU service is reachable and Diffusers is available."""
        import asyncio
        try:
            result = await asyncio.to_thread(self._get, '/api/diffusers/available')
            return result is not None and result.get('available', False)
        except Exception:
            return False

    async def get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU memory information from the GPU service."""
        import asyncio
        result = await asyncio.to_thread(self._get, '/api/diffusers/gpu_info')
        return result or {"error": "GPU service unreachable"}

    async def load_model(
        self,
        model_id: str,
        pipeline_class: str = "StableDiffusion3Pipeline",
    ) -> bool:
        """Models are loaded on-demand by the GPU service. Always returns True if service is up."""
        return await self.is_available()

    async def unload_model(self, model_id: Optional[str] = None) -> bool:
        """Unload a model from the GPU service."""
        import asyncio
        result = await asyncio.to_thread(
            self._post, '/api/diffusers/unload', {'model_id': model_id}
        )
        return result is not None and result.get('success', False)

    async def generate_image(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
        pipeline_class: str = "StableDiffusion3Pipeline",
        loras: Optional[list] = None,
        **kwargs
    ) -> Optional[bytes]:
        """Generate an image. Returns PNG bytes or None.

        callback parameter is accepted but ignored (cannot serialize over HTTP).
        """
        import asyncio
        payload = {
            'prompt': prompt,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
            'pipeline_class': pipeline_class,
        }
        if loras:
            payload['loras'] = loras
        # SD3.5 triple-prompt: forward per-encoder prompts
        if kwargs.get('prompt_2'):
            payload['prompt_2'] = kwargs['prompt_2']
        if kwargs.get('prompt_3'):
            payload['prompt_3'] = kwargs['prompt_3']
        # Flux2 visual conditioning: forward image as base64
        if kwargs.get('image_base64'):
            payload['image_base64'] = kwargs['image_base64']
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate', payload)

        if result is None or not result.get('success'):
            return None

        return base64.b64decode(result['image_base64'])

    async def generate_video(
        self,
        prompt: str,
        model_id: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
        negative_prompt: str = "",
        width: int = 1280,
        height: int = 720,
        num_frames: int = 81,
        steps: int = 30,
        cfg_scale: float = 5.0,
        fps: int = 16,
        seed: int = -1,
        pipeline_class: str = "WanPipeline",
        guidance_scale_2: float = None,
        **kwargs
    ) -> Optional[bytes]:
        """Generate a video. Returns MP4 bytes or None.

        Video generation takes significantly longer than images (~4min for 14B).
        """
        import asyncio
        payload = {
            'prompt': prompt,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'num_frames': num_frames,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'fps': fps,
            'seed': seed,
            'pipeline_class': pipeline_class,
        }
        if guidance_scale_2 is not None:
            payload['guidance_scale_2'] = guidance_scale_2
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/video', payload, self.timeout_video)

        if result is None or not result.get('success'):
            return None

        return base64.b64decode(result['video_base64'])

    async def generate_video_from_image(
        self,
        image_bytes: bytes,
        prompt: str = "",
        model_id: str = "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
        negative_prompt: str = "",
        width: int = 1280,
        height: int = 720,
        num_frames: int = 81,
        steps: int = 40,
        cfg_scale: float = 4.0,
        fps: int = 16,
        seed: int = -1,
        guidance_scale_2: float = None,
        **kwargs
    ) -> Optional[bytes]:
        """Generate a video from an image. Returns MP4 bytes or None."""
        import asyncio
        payload = {
            'image_base64': base64.b64encode(image_bytes).decode('utf-8'),
            'prompt': prompt,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'num_frames': num_frames,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'fps': fps,
            'seed': seed,
        }
        if guidance_scale_2 is not None:
            payload['guidance_scale_2'] = guidance_scale_2
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/video/i2v', payload, self.timeout_video)

        if result is None or not result.get('success'):
            return None

        return base64.b64decode(result['video_base64'])

    async def generate_image_with_fusion(
        self,
        prompt: str,
        t5_prompt: Optional[str] = None,
        alpha_factor: float = 0.0,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
        loras: Optional[list] = None,
        fusion_strategy: str = "legacy",
    ) -> Optional[bytes]:
        """T5-CLIP fusion generation. Returns PNG bytes or None."""
        import asyncio
        payload = {
            'prompt': prompt,
            't5_prompt': t5_prompt,
            'alpha_factor': alpha_factor,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
            'fusion_strategy': fusion_strategy,
        }
        if loras:
            payload['loras'] = loras
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/fusion', payload)

        if result is None or not result.get('success'):
            return None

        return base64.b64decode(result['image_base64'])

    async def generate_image_with_attention(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        capture_layers: Optional[list] = None,
        capture_every_n_steps: int = 5,
        callback: Optional[Callable[[int, int, Any], None]] = None
    ) -> Optional[Dict[str, Any]]:
        """Attention cartography. Returns dict with attention maps or None."""
        import asyncio
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/attention', {
            'prompt': prompt,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
            'capture_layers': capture_layers,
            'capture_every_n_steps': capture_every_n_steps,
        })

        if result is None or not result.get('success'):
            return None

        # Remove the 'success' key to match DiffusersImageGenerator return format
        result.pop('success', None)
        return result

    async def generate_image_with_probing(
        self,
        prompt_a: str,
        prompt_b: str,
        encoder: str = "t5",
        transfer_dims: list = None,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
    ) -> Optional[Dict[str, Any]]:
        """Feature probing. Returns dict with probing data or error dict."""
        import asyncio
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/probing', {
            'prompt_a': prompt_a,
            'prompt_b': prompt_b,
            'encoder': encoder,
            'transfer_dims': transfer_dims,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
            'model_id': model_id,
        })

        if result is None:
            return {'error': 'GPU service unreachable'}

        if not result.get('success'):
            return {'error': result.get('error', 'Probing generation failed')}

        result.pop('success', None)
        return result

    async def generate_image_with_algebra(
        self,
        prompt_a: str,
        prompt_b: str,
        prompt_c: str,
        encoder: str = "all",
        scale_sub: float = 1.0,
        scale_add: float = 1.0,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        generate_reference: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Concept algebra. Returns dict with images and algebra data or None."""
        import asyncio
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/algebra', {
            'prompt_a': prompt_a,
            'prompt_b': prompt_b,
            'prompt_c': prompt_c,
            'encoder': encoder,
            'scale_sub': scale_sub,
            'scale_add': scale_add,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
            'model_id': model_id,
            'generate_reference': generate_reference,
        })

        if result is None or not result.get('success'):
            return None

        result.pop('success', None)
        return result

    async def generate_image_with_archaeology(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        capture_every_n: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """Denoising archaeology. Returns dict with step images or None."""
        import asyncio
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/archaeology', {
            'prompt': prompt,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
            'capture_every_n': capture_every_n,
        })

        if result is None or not result.get('success'):
            return None

        result.pop('success', None)
        return result

    async def generate_image_streaming(
        self,
        prompt: str,
        model_id: str = "stabilityai/stable-diffusion-3.5-large",
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming generation — not implemented over HTTP yet.

        Falls back to non-streaming generate and yields a single 'complete' event.
        """
        image_bytes = await self.generate_image(prompt=prompt, model_id=model_id, **kwargs)
        if image_bytes:
            yield {
                "type": "complete",
                "image": base64.b64encode(image_bytes).decode('utf-8')
            }
        else:
            yield {"type": "error", "message": "Generation failed"}

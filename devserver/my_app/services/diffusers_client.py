"""
Diffusers HTTP Client — Drop-in replacement for DiffusersImageGenerator

Calls the shared GPU service (port 17803) via HTTP REST instead of
loading models in-process. All method signatures and return types
are identical to DiffusersImageGenerator.

Callers (backend_router.py, chunk files) require zero changes.
"""

import base64
import logging
from typing import Optional, Dict, Any, Callable

from my_app.services.gpu_lease_client import GpuBusyError, BackendGenerationError
from my_app.services.streaming_response import note_dispatch


def _note_model_of(path: str, data: dict) -> None:
    """Say which model this call is about to put on the card.

    Every generation, every fusion, both video paths and the latent decode go
    out through the two POST methods below with `model_id` in the body, so this
    is the one place that reads it. `/unload` is left out: taking weights off
    the card is the opposite of a model being at work.
    """
    if not isinstance(data, dict) or path.endswith('/unload'):
        return
    note_dispatch(data.get('model_id'), local=True)

logger = logging.getLogger(__name__)


def _one_line(text, cap: int = 200) -> str:
    """A reason fit to be read by whoever is waiting.

    Whatever comes back travels all the way to a tooltip in the flow surface
    and to the face of a Resona card, so it leaves here as one line, capped,
    and never as a raw response body: an HTML error page carries the server's
    own file paths, and those have no business on a workshop screen. The same
    treatment already exists 500 lines into backend_router for the same reason.
    """
    from my_app.utils.response_reason import reason_line
    return reason_line(text, cap)



class DiffusersClient:
    """HTTP client for the shared GPU service.

    Drop-in replacement for DiffusersImageGenerator.
    All methods have identical signatures and return types.
    """

    def __init__(self):
        from config import GPU_SERVICE_URL
        self.base_url = GPU_SERVICE_URL.rstrip('/')
        logger.info(f"[DIFFUSERS-CLIENT] Initialized: url={self.base_url}")

    # Connect phase only. A hard READ timeout on a generation call silently turns a
    # slow-but-healthy run into a failure: how long a request takes depends on model,
    # resolution, concept count and cold-load state (an SD3.5-Large cold load alone
    # can exceed two minutes, and composable diffusion runs N+1 passes per step).
    # The connect bound still catches a GPU service that is down.
    _CONNECT_TIMEOUT = 15

    def _with_run_label(self, data: dict) -> dict:
        """The payload with the run it belongs to named on it.

        Name the run, so the gate can report a queue in terms of the runs people
        are waiting for rather than anonymous slots; name the config, because
        that is what the durations are measured against. The ComfyUI path
        carries both in its lease already. This stood inside _post and is a
        method of its own since the latent decode below became a second call
        that goes through the same door.

        The decode brings NEITHER name. It is asked for outside any generation
        and on a pool thread of its own, which starts with an empty context, so
        both variables read empty and the payload goes out bare. The GPU service
        files it under its own workload, `vae-decode`. Since 2026-09-14 the
        platform decodes a mean in ComfyUI (my_app/services/latent_decoder.py)
        and nothing on it calls that decode; stage 8 of the move removes it.
        """
        try:
            from my_app.services.generation_abort import (CURRENT_RUN_ID,
                                                            CURRENT_OUTPUT_CONFIG)
            _label = CURRENT_RUN_ID.get() or ""
            if _label and isinstance(data, dict) and "run_label" not in data:
                data = {**data, "run_label": _label}
            _cfg = CURRENT_OUTPUT_CONFIG.get() or ""
            if _cfg and isinstance(data, dict) and "workload" not in data:
                data = {**data, "workload": _cfg}
        except Exception:
            pass
        return data

    def _post(self, path: str, data: dict) -> Optional[dict]:
        """Synchronous POST to GPU service. Returns JSON response or None.

        Only the connect phase is bounded (_CONNECT_TIMEOUT); a read cap is
        deliberately not applied.
        """
        import requests
        url = f"{self.base_url}{path}"
        data = self._with_run_label(data)
        _note_model_of(path, data)
        try:
            resp = requests.post(url, json=data, timeout=(self._CONNECT_TIMEOUT, None))
            if resp.status_code == 409:
                # The run was stopped on request and the GPU service says so
                # rather than handing back the half-denoised latents. Somebody
                # pressed stop; that is not an error and must not be logged
                # with a traceback as if the card had broken.
                try:
                    _cancelled = (resp.json() or {}).get('cancelled')
                except Exception:
                    _cancelled = False
                if _cancelled:
                    note_dispatch(None, local=True)
                    logger.info(f"[DIFFUSERS-CLIENT] Run stopped on request: {path}")
                    return None
            if resp.status_code == 503:
                # The card is occupied, not broken. Flattening this to None turns
                # "wait a moment" into "your generation failed" for the user.
                # Which refusal it is travels with it, so the surface can say
                # what is actually holding the card.
                raise GpuBusyError.from_response(resp)
            if resp.status_code >= 400:
                # The service said why. Until 2026-09-07 this was raise_for_status
                # into a blanket catch, so the reason died here and every failure
                # reached the chunk as "returned empty result".
                raise BackendGenerationError.from_response(resp)
            resp.raise_for_status()
            return resp.json()
        except (GpuBusyError, BackendGenerationError):
            # The two failures that actually happen on a shared card, and both
            # leave the run at no model: 503 says it never got there, a 4xx/5xx
            # from the service says it is out again. Without this the name
            # stands until the next dispatch replaces it — the connect-level
            # branches below would have covered only a dead socket.
            note_dispatch(None, local=True)
            raise
        # `note_dispatch(None)` in each: nothing is at this model any more, and
        # the name would otherwise stand in the bar until the next dispatch
        # replaced it (services/streaming_response.py).
        except requests.ConnectionError:
            note_dispatch(None, local=True)
            logger.error(f"[DIFFUSERS-CLIENT] GPU service unreachable at {url}")
            return None
        except requests.Timeout:
            note_dispatch(None, local=True)
            logger.error(f"[DIFFUSERS-CLIENT] Could not connect within {self._CONNECT_TIMEOUT}s: {path}")
            return None
        except Exception as e:
            note_dispatch(None, local=True)
            logger.error(f"[DIFFUSERS-CLIENT] Request failed: {e}")
            return None


    def _get(self, path: str) -> Optional[dict]:
        """Synchronous GET to GPU service. Returns JSON response or None."""
        payload, _ = self._get_with_reason(path)
        return payload

    def _get_with_reason(self, path: str):
        """The service's answer, and - where there is none - what happened.

        The reason travels as a return value rather than in a ContextVar: these
        calls reach the network through asyncio.to_thread, which runs them on a
        COPY of the context, so anything set inside would be dropped on the way
        back.

        The ten seconds stay. This path carries two questions about state -
        /available and /gpu_info - and never a generation, so a short bound is
        right here; the generation calls go through _post, which is connect-only
        (see _CONNECT_TIMEOUT above).
        """
        import requests
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, timeout=10)
        # ReadTimeout first: ConnectTimeout inherits from BOTH ConnectionError
        # and Timeout, so a ConnectionError branch placed above would swallow
        # every connect timeout and report it as "answering nowhere".
        except requests.ReadTimeout:
            logger.error(f"[DIFFUSERS-CLIENT] {path} stayed silent for 10 s")
            return None, "the GPU service stayed silent for ten seconds"
        except requests.ConnectionError:
            logger.error(f"[DIFFUSERS-CLIENT] nothing answers at {url}")
            return None, "the GPU service is answering nowhere"
        except requests.Timeout:
            logger.error(f"[DIFFUSERS-CLIENT] {path} timed out")
            return None, "the GPU service did not answer in time"
        except Exception as e:
            logger.error(f"[DIFFUSERS-CLIENT] GET failed: {e}")
            return None, f"asking the GPU service broke: {type(e).__name__}"

        if not resp.ok:
            # Only the service's OWN sentence is passed on. The raw body stays
            # in the log: an HTML error page would put a server file path on a
            # workshop screen.
            said = ""
            try:
                body = resp.json()
                if isinstance(body, dict):
                    said = _one_line(body.get("error") or body.get("reason"))
            except ValueError:
                pass
            logger.error(f"[DIFFUSERS-CLIENT] {path} refused ({resp.status_code}): "
                         f"{said or _one_line(resp.text, 300)}")
            logger.error(f"[DIFFUSERS-CLIENT] {path} said, in full: {resp.text[:4000]}")
            return None, said or f"the GPU service refused with status {resp.status_code}"

        try:
            return resp.json(), ""
        except ValueError:
            logger.error(f"[DIFFUSERS-CLIENT] {path} answered with no JSON")
            return None, "the GPU service answered with something unreadable"

    async def availability(self):
        """Whether diffusers is installed over there, and what happened if unknown.

        Two different answers used to collapse into one False: "the service says
        it has no diffusers" and "the service did not answer". The first is
        about the installation and holds until somebody installs it; the second
        is about this moment and the same request works again later. On
        2026-08-25 a run reported the first when the second had happened, and
        the sentence a workshop read was about a broken install that was fine.
        """
        import asyncio
        try:
            payload, reason = await asyncio.to_thread(
                self._get_with_reason, '/api/diffusers/available')
        except Exception as e:
            return False, f"asking the GPU service broke: {type(e).__name__}"
        if payload is None:
            return False, reason or "the GPU service gave no answer"
        if not isinstance(payload, dict):
            # A 200 whose body is a list or a string used to raise AttributeError
            # out of a chunk. It is still a failure, and it says so.
            return False, "the GPU service answered in a shape nobody expects"
        if payload.get('available', False):
            return True, ""
        # `reason` is the field this route actually sends (diffusers_routes.py);
        # without one, diffusers really is missing over there.
        return False, (_one_line(payload.get('reason'))
                       or "the GPU service reports no diffusers installation")

    async def is_available(self) -> bool:
        """Whether diffusers is installed over there. See availability()."""
        ok, _ = await self.availability()
        return ok

    async def get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU memory information from the GPU service."""
        import asyncio
        result, reason = await asyncio.to_thread(
            self._get_with_reason, '/api/diffusers/gpu_info')
        # The caller logs this string. "GPU service unreachable" was the same
        # sentence for a dead service and a busy one.
        return result or {"error": reason or "GPU service unreachable"}


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
        model_id: str,
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
        # Flux2 visual conditioning / SD3.5 img2img: forward image as base64
        if kwargs.get('image_base64'):
            payload['image_base64'] = kwargs['image_base64']
        # SD3.5 img2img: forward strength parameter
        if kwargs.get('strength') is not None:
            payload['strength'] = kwargs['strength']
        # Keep the picture's FINAL latent, for a caller that wants to average a
        # set of them before the decoder rather than after it. The picture is
        # unchanged: it is decoded from exactly this latent.
        if kwargs.get('keep_latent'):
            payload['keep_latent'] = True
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate', payload)

        if result is None or not result.get('success'):
            return None

        # The latent travels in a sink the caller passed in rather than in the
        # return value, because every existing caller of this method reads the
        # PNG bytes it returns and none of them may have to change.
        sink = kwargs.get('latent_sink')
        if isinstance(sink, dict) and result.get('latent_base64'):
            sink['latent'] = base64.b64decode(result['latent_base64'])
            sink['meta'] = result.get('latent_meta') or {}

        return base64.b64decode(result['image_base64'])


    async def generate_video(
        self,
        prompt: str,
        model_id: str,
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
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/video', payload)

        if result is None or not result.get('success'):
            return None

        return base64.b64decode(result['video_base64'])

    async def generate_video_from_image(
        self,
        image_bytes: bytes,
        model_id: str,
        prompt: str = "",
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
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/video/i2v', payload)

        if result is None or not result.get('success'):
            return None

        return base64.b64decode(result['video_base64'])

    async def generate_image_with_fusion(
        self,
        prompt: str,
        model_id: str,
        t5_prompt: Optional[str] = None,
        alpha_factor: float = 0.0,
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


    async def generate_image_with_decomposition(
        self,
        source_prompt: str,
        model_id: str,
        cells: Optional[list] = None,
        clip_l_prompt: Optional[str] = None,
        clip_l_step_bands: Optional[list] = None,
        clip_l_layer_bands: Optional[list] = None,
        clip_g_prompt: Optional[str] = None,
        clip_g_step_bands: Optional[list] = None,
        clip_g_layer_bands: Optional[list] = None,
        t5_prompt: Optional[str] = None,
        t5_step_bands: Optional[list] = None,
        t5_layer_bands: Optional[list] = None,
        alpha: float = 1.0,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 5.5,
        seed: int = -1,
        callback: Optional[Callable[[int, int, Any], None]] = None,
    ) -> Optional[bytes]:
        """Decomposition mode — 3×3×3 intervention space. Returns PNG bytes or None.

        The chunk that called this went with the Decomposition surface; the
        Diffusers station keeps the route, so this stays as the way to it.
        Nothing of the Diffusers station gets dismantled.

        Pass `cells` as [{step, layer, stream, prompt}, ...] for arbitrary
        per-cell control. Old per-stream + bands params still work as fallback.
        """
        import asyncio
        payload = {
            'source_prompt': source_prompt,
            'cells': cells,
            'clip_l_prompt': clip_l_prompt,
            'clip_l_step_bands': clip_l_step_bands,
            'clip_l_layer_bands': clip_l_layer_bands,
            'clip_g_prompt': clip_g_prompt,
            'clip_g_step_bands': clip_g_step_bands,
            'clip_g_layer_bands': clip_g_layer_bands,
            't5_prompt': t5_prompt,
            't5_step_bands': t5_step_bands,
            't5_layer_bands': t5_layer_bands,
            'alpha': alpha,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
        }
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/decomposition', payload)

        if result is None or not result.get('success'):
            return None

        return base64.b64decode(result['image_base64'])

    async def generate_image_with_attention(
        self,
        prompt: str,
        model_id: str,
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
        model_id: str,
        encoder: str = "t5",
        transfer_dims: list = None,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
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
        model_id: str,
        encoder: str = "all",
        scale_sub: float = 1.0,
        scale_add: float = 1.0,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
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
        model_id: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        capture_every_n: int = 1,
        pipeline_class: str = "StableDiffusion3Pipeline",
        scheduler: Optional[str] = None,
        shift: Optional[float] = None,
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
            'pipeline_class': pipeline_class,
            'scheduler': scheduler,
            'shift': shift,
        })

        if result is None or not result.get('success'):
            return None

        result.pop('success', None)
        return result

    async def generate_image_composable(
        self,
        concepts: list,
        model_id: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 4.5,
        seed: int = -1,
        normalize_weights: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Composable diffusion. Returns dict with image_base64 or None."""
        import asyncio
        result = await asyncio.to_thread(self._post, '/api/diffusers/generate/composable', {
            'concepts': concepts,
            'model_id': model_id,
            'negative_prompt': negative_prompt,
            'width': width,
            'height': height,
            'steps': steps,
            'cfg_scale': cfg_scale,
            'seed': seed,
            'normalize_weights': normalize_weights,
        })

        if result is None or not result.get('success'):
            return None

        result.pop('success', None)
        return result


_backend: Optional[DiffusersClient] = None


def get_diffusers_backend() -> DiffusersClient:
    """Return the shared DiffusersClient singleton (lazy-initialized).

    All Diffusers calls in DevServer go through this factory; the client
    itself forwards every method over HTTP to the gpu_service singleton
    that actually owns the GPU. There is only one Diffusers backend in
    the system — `gpu_service/services/diffusers_backend.py`.
    """
    global _backend
    if _backend is None:
        _backend = DiffusersClient()
    return _backend


def reset_diffusers_backend() -> None:
    """Reset the singleton (for testing)."""
    global _backend
    _backend = None

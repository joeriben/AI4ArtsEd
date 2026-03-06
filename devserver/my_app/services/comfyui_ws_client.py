"""
ComfyUI WebSocket Client — Direct connection to ComfyUI

Provides real-time progress tracking, denoising previews, and clean media download
via ComfyUI's HTTP API (no filesystem access).

Architecture:
    DevServer --WebSocket--> ComfyUI (port 17804)
    - JSON events: progress, node completion, errors
    - Binary messages: denoising preview images
    - HTTP: /prompt (submit), /view (download media), /history (outputs)
"""

import asyncio
import aiohttp
import json
import logging
import struct
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MediaFile:
    """A single media file downloaded from ComfyUI."""
    data: bytes
    filename: str
    media_type: str  # "image", "audio", "video"
    subfolder: str = ""
    node_id: str = ""


@dataclass
class ProgressEvent:
    """Progress update from ComfyUI WebSocket."""
    overall_percent: float  # 0.0 – 1.0
    current_percent: float  # step progress within current node
    nodes_done: int
    total_nodes: int
    current_node: Optional[str] = None
    preview_base64: Optional[str] = None  # denoising preview (JPEG base64)


@dataclass
class GenerationResult:
    """Result of a workflow submission and tracking."""
    prompt_id: str
    media_files: list  # List[MediaFile]
    execution_time: float
    outputs_metadata: dict = field(default_factory=dict)  # Raw ComfyUI outputs dict


# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

class ComfyUIWebSocketClient:
    """
    Direct WebSocket client to ComfyUI.

    Provides workflow submission, progress tracking, and media download.
    """

    def __init__(self, base_url: Optional[str] = None, ws_url: Optional[str] = None):
        if base_url is None:
            from config import COMFYUI_PORT
            base_url = f"http://127.0.0.1:{COMFYUI_PORT}"
        if ws_url is None:
            # Derive ws:// from http://
            ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")

        self.base_url = base_url
        self.ws_url = ws_url
        self.client_id = str(uuid.uuid4())

        # Persistent WebSocket connection
        self._ws = None
        self._ws_lock = asyncio.Lock()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

        logger.info(f"[COMFYUI-WS] Initialized client: HTTP={base_url}, WS={ws_url}, client_id={self.client_id[:8]}...")

    # ------------------------------------------------------------------
    # WebSocket connection management
    # ------------------------------------------------------------------

    async def _ensure_ws_connected(self):
        """Ensure WebSocket is connected, reconnect if needed."""
        async with self._ws_lock:
            if self._ws is not None:
                try:
                    # Quick ping to check connection
                    await self._ws.ping()
                    return
                except Exception:
                    logger.debug("[COMFYUI-WS] WebSocket ping failed, reconnecting...")
                    self._ws = None

            await self._connect_ws()

    async def _connect_ws(self):
        """Establish WebSocket connection to ComfyUI."""
        import websockets

        url = f"{self.ws_url}/ws?clientId={self.client_id}"
        try:
            self._ws = await websockets.connect(
                url,
                max_size=100 * 1024 * 1024,  # 100MB for large binary messages
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            self._reconnect_attempts = 0
            logger.info(f"[COMFYUI-WS] Connected to {url}")
        except Exception as e:
            self._reconnect_attempts += 1
            logger.error(f"[COMFYUI-WS] Connection failed (attempt {self._reconnect_attempts}): {e}")
            self._ws = None
            raise

    async def _close_ws(self):
        """Close WebSocket connection."""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ------------------------------------------------------------------
    # Core: Submit workflow and track via WebSocket
    # ------------------------------------------------------------------

    async def submit_and_track(
        self,
        workflow: Dict[str, Any],
        timeout: int = 480,
        on_progress: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> GenerationResult:
        """
        Submit a workflow to ComfyUI and track execution via WebSocket.

        Args:
            workflow: ComfyUI workflow JSON (the prompt dict).
            timeout: Maximum seconds to wait for completion.
            on_progress: Optional callback for progress events.

        Returns:
            GenerationResult with downloaded media files.

        Raises:
            TimeoutError: If execution exceeds timeout.
            RuntimeError: If ComfyUI reports an execution error.
        """
        start_time = time.time()

        # Per-request client_id: ComfyUI's sockets dict is keyed by clientId,
        # so concurrent requests sharing the same clientId overwrite each other
        # and only the last-connected WS receives events. (server.py:254-255)
        request_client_id = str(uuid.uuid4())

        # 1. Submit workflow via HTTP
        prompt_id = await self._submit_workflow(workflow, request_client_id)
        if not prompt_id:
            raise RuntimeError("Failed to submit workflow to ComfyUI")

        logger.info(f"[COMFYUI-WS] Workflow submitted: {prompt_id}")

        # 2. Calculate total nodes for progress
        total_nodes = len(workflow)

        # 3. Track execution via WebSocket
        try:
            await self._track_execution(
                prompt_id=prompt_id,
                total_nodes=total_nodes,
                timeout=timeout,
                on_progress=on_progress,
                start_time=start_time,
                client_id=request_client_id,
            )
        except (RuntimeError, TimeoutError):
            # ComfyUI execution errors and timeouts propagate immediately
            raise
        except Exception as e:
            # Only fall back to polling for WebSocket connection failures
            logger.warning(f"[COMFYUI-WS] WebSocket connection failed: {e}. Falling back to history polling.")
            await self._poll_until_complete(prompt_id, timeout=timeout, start_time=start_time)

        # 4. Download media via HTTP
        execution_time = time.time() - start_time
        media_files, outputs_metadata = await self._download_outputs(prompt_id)

        logger.info(
            f"[COMFYUI-WS] Generation complete: {len(media_files)} file(s) in {execution_time:.1f}s"
        )

        return GenerationResult(
            prompt_id=prompt_id,
            media_files=media_files,
            execution_time=execution_time,
            outputs_metadata=outputs_metadata,
        )

    # ------------------------------------------------------------------
    # HTTP: Workflow submission
    # ------------------------------------------------------------------

    async def _submit_workflow(self, workflow: Dict[str, Any], client_id: str) -> Optional[str]:
        """POST workflow to ComfyUI /prompt endpoint."""
        payload = {
            "prompt": workflow,
            "client_id": client_id,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/prompt",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("prompt_id")
                    else:
                        error_text = await response.text()
                        logger.error(f"[COMFYUI-WS] Submit failed: {response.status} - {error_text[:500]}")
                        return None
        except Exception as e:
            logger.error(f"[COMFYUI-WS] Submit error: {e}")
            return None

    # ------------------------------------------------------------------
    # WebSocket: Execution tracking
    # ------------------------------------------------------------------

    async def _track_execution(
        self,
        prompt_id: str,
        total_nodes: int,
        timeout: int,
        on_progress: Optional[Callable],
        start_time: float,
        client_id: str,
    ):
        """Track workflow execution via WebSocket events."""
        import websockets

        # Use per-request clientId: ComfyUI keys its sockets dict by clientId,
        # so all concurrent requests MUST use different clientIds
        url = f"{self.ws_url}/ws?clientId={client_id}"

        async with websockets.connect(
            url,
            max_size=100 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            # Race condition guard: check if execution already completed before WS connected
            await self._check_already_completed(prompt_id)

            nodes_done = 0
            current_step = 0
            max_steps = 1
            our_execution_started = False

            while True:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"Execution timeout after {timeout}s")

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(30, timeout - elapsed))
                except asyncio.TimeoutError:
                    # No message for 30s — send progress ping
                    continue

                # Binary message = denoising preview
                if isinstance(raw, bytes):
                    preview_b64 = self._parse_binary_preview(raw)
                    if preview_b64 and on_progress:
                        step_progress = current_step / max_steps if max_steps > 0 else 0
                        overall = (nodes_done + step_progress) / total_nodes if total_nodes > 0 else 0
                        on_progress(ProgressEvent(
                            overall_percent=min(overall, 0.99),
                            current_percent=step_progress,
                            nodes_done=nodes_done,
                            total_nodes=total_nodes,
                            preview_base64=preview_b64,
                        ))
                    continue

                # JSON message
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                data = msg.get("data", {})

                # Filter: only react to OUR prompt
                # Check prompt_id on EVERY event (not just execution_start)
                # to handle the race where execution_start fires before WS connects
                event_prompt_id = data.get("prompt_id")
                if event_prompt_id == prompt_id:
                    if not our_execution_started:
                        our_execution_started = True
                        logger.info(f"[COMFYUI-WS] Tracking execution: {prompt_id} (first event: {msg_type})")
                elif event_prompt_id and event_prompt_id != prompt_id:
                    # Event for a different prompt — skip
                    continue

                if msg_type == "execution_start":
                    continue

                # Skip events until we've seen at least one event for our prompt
                if not our_execution_started:
                    continue

                if msg_type == "executing":
                    node = data.get("node")
                    if node is None:
                        # node=None means execution finished
                        logger.info(f"[COMFYUI-WS] Execution finished: {prompt_id}")
                        if on_progress:
                            on_progress(ProgressEvent(
                                overall_percent=1.0,
                                current_percent=1.0,
                                nodes_done=total_nodes,
                                total_nodes=total_nodes,
                            ))
                        return
                    else:
                        nodes_done += 1
                        current_step = 0
                        max_steps = 1
                        if on_progress:
                            overall = nodes_done / total_nodes if total_nodes > 0 else 0
                            on_progress(ProgressEvent(
                                overall_percent=min(overall, 0.99),
                                current_percent=0.0,
                                nodes_done=nodes_done,
                                total_nodes=total_nodes,
                                current_node=node,
                            ))

                elif msg_type == "execution_cached":
                    cached_nodes = data.get("nodes", [])
                    nodes_done += len(cached_nodes)
                    logger.debug(f"[COMFYUI-WS] {len(cached_nodes)} nodes cached")

                elif msg_type == "progress":
                    current_step = data.get("value", 0)
                    max_steps = data.get("max", 1)
                    if on_progress:
                        step_progress = current_step / max_steps if max_steps > 0 else 0
                        overall = (nodes_done + step_progress) / total_nodes if total_nodes > 0 else 0
                        on_progress(ProgressEvent(
                            overall_percent=min(overall, 0.99),
                            current_percent=step_progress,
                            nodes_done=nodes_done,
                            total_nodes=total_nodes,
                        ))

                elif msg_type == "execution_error":
                    error_msg = data.get("exception_message", "Unknown error")
                    node_type = data.get("node_type", "unknown")
                    logger.error(f"[COMFYUI-WS] Execution error in {node_type}: {error_msg}")
                    raise RuntimeError(f"ComfyUI execution error in {node_type}: {error_msg}")

                elif msg_type == "executed":
                    # Final output from a node — execution will end with executing(node=None) next
                    pass

    async def _check_already_completed(self, prompt_id: str):
        """Check if execution already completed before WebSocket connected (race condition guard)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        history = await response.json()
                        if history and prompt_id in history:
                            entry = history[prompt_id]
                            status_str = entry.get("status", {}).get("status_str", "")
                            if status_str == "error":
                                msgs = entry.get("status", {}).get("messages", [])
                                error_msg = "Unknown error"
                                for msg in msgs:
                                    if isinstance(msg, list) and msg[0] == "execution_error":
                                        error_msg = msg[1].get("exception_message", error_msg)
                                raise RuntimeError(f"ComfyUI execution error: {error_msg}")
                            if entry.get("outputs"):
                                logger.info(f"[COMFYUI-WS] Execution already completed (pre-WS)")
                                return  # Will be picked up by _download_outputs
        except RuntimeError:
            raise
        except Exception:
            pass  # History check failed, continue with WS tracking

    # ------------------------------------------------------------------
    # Fallback: History polling (when WebSocket fails)
    # ------------------------------------------------------------------

    async def _poll_until_complete(
        self,
        prompt_id: str,
        timeout: int = 480,
        poll_interval: float = 2.0,
        start_time: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Poll /history until workflow completes. Fallback for WebSocket failures."""
        if start_time is None:
            start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Polling timeout after {timeout}s for {prompt_id}")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}/history/{prompt_id}",
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as response:
                        if response.status == 200:
                            history = await response.json()
                            if history and prompt_id in history:
                                entry = history[prompt_id]
                                status = entry.get("status", {}).get("status_str", "")
                                if status == "error":
                                    raise RuntimeError(f"ComfyUI workflow error: {entry.get('status')}")
                                outputs = entry.get("outputs", {})
                                if outputs:
                                    logger.info(f"[COMFYUI-WS] Poll: completed after {elapsed:.1f}s")
                                    return entry
            except (RuntimeError, TimeoutError):
                raise
            except Exception as e:
                logger.debug(f"[COMFYUI-WS] Poll error: {e}")

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Binary preview parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_binary_preview(data: bytes) -> Optional[str]:
        """Parse binary WebSocket message into base64-encoded preview image.

        ComfyUI binary message format:
        - Bytes 0-3: event type (uint32)
        - Bytes 4-7: format info (uint32)
        - Bytes 8+: image data (JPEG or PNG)
        """
        import base64

        if len(data) < 8:
            return None

        # Event type 1 = preview image, 2 = final output
        try:
            event_type = struct.unpack(">I", data[:4])[0]
        except struct.error:
            return None

        if event_type not in (1, 2):
            return None

        image_data = data[8:]
        if len(image_data) < 100:
            return None

        return base64.b64encode(image_data).decode("ascii")

    # ------------------------------------------------------------------
    # HTTP: Download outputs after completion
    # ------------------------------------------------------------------

    async def _download_outputs(self, prompt_id: str) -> tuple:
        """Download all media files from a completed workflow.

        Returns:
            (media_files: List[MediaFile], outputs_metadata: dict)
        """
        media_files = []
        outputs_metadata = {}

        # 1. Get history to find output filenames
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status != 200:
                        logger.error(f"[COMFYUI-WS] History fetch failed: {response.status}")
                        return media_files, outputs_metadata

                    history = await response.json()

        except Exception as e:
            logger.error(f"[COMFYUI-WS] History fetch error: {e}")
            return media_files, outputs_metadata

        if prompt_id not in history:
            logger.error(f"[COMFYUI-WS] prompt_id {prompt_id} not in history")
            return media_files, outputs_metadata

        entry = history[prompt_id]
        outputs = entry.get("outputs", {})
        outputs_metadata = outputs

        # 2. Extract and download all media files
        async with aiohttp.ClientSession() as session:
            for node_id, node_output in outputs.items():
                # Images
                for img in node_output.get("images", []):
                    file_data = await self._download_view(
                        session, img["filename"],
                        img.get("subfolder", ""), img.get("type", "output")
                    )
                    if file_data:
                        media_files.append(MediaFile(
                            data=file_data,
                            filename=img["filename"],
                            media_type="image",
                            subfolder=img.get("subfolder", ""),
                            node_id=node_id,
                        ))

                # Audio (audio / genaudio keys)
                for key in ("audio", "genaudio"):
                    for aud in node_output.get(key, []):
                        file_data = await self._download_view(
                            session, aud["filename"],
                            aud.get("subfolder", ""), aud.get("type", "output")
                        )
                        if file_data:
                            media_files.append(MediaFile(
                                data=file_data,
                                filename=aud["filename"],
                                media_type="audio",
                                subfolder=aud.get("subfolder", ""),
                                node_id=node_id,
                            ))

                # Video (video / genvideo / gifs keys)
                for key in ("video", "genvideo", "gifs"):
                    for vid in node_output.get(key, []):
                        file_data = await self._download_view(
                            session, vid["filename"],
                            vid.get("subfolder", ""), vid.get("type", "output")
                        )
                        if file_data:
                            media_files.append(MediaFile(
                                data=file_data,
                                filename=vid["filename"],
                                media_type="video",
                                subfolder=vid.get("subfolder", ""),
                                node_id=node_id,
                            ))

        return media_files, outputs_metadata

    async def _download_view(
        self, session: aiohttp.ClientSession,
        filename: str, subfolder: str, type_name: str,
    ) -> Optional[bytes]:
        """Download a single file via ComfyUI /view endpoint."""
        try:
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": type_name,
            }
            async with session.get(
                f"{self.base_url}/view",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 200:
                    data = await response.read()
                    logger.debug(f"[COMFYUI-WS] Downloaded {filename}: {len(data)} bytes")
                    return data
                else:
                    logger.error(f"[COMFYUI-WS] Download failed {filename}: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"[COMFYUI-WS] Download error {filename}: {e}")
            return None

    # ------------------------------------------------------------------
    # Image upload (for img2img workflows)
    # ------------------------------------------------------------------

    async def upload_image(self, image_data: bytes, filename: str) -> Optional[str]:
        """Upload image to ComfyUI for img2img workflows.

        Args:
            image_data: Raw image bytes.
            filename: Target filename.

        Returns:
            Uploaded filename as returned by ComfyUI, or None on failure.
        """
        try:
            form = aiohttp.FormData()
            form.add_field(
                "image", image_data,
                filename=filename,
                content_type="image/png",
            )
            form.add_field("overwrite", "true")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/upload/image",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        uploaded_name = result.get("name", filename)
                        logger.info(f"[COMFYUI-WS] Uploaded image: {uploaded_name}")
                        return uploaded_name
                    else:
                        logger.error(f"[COMFYUI-WS] Upload failed: HTTP {response.status}")
                        return None
        except Exception as e:
            logger.error(f"[COMFYUI-WS] Upload error: {e}")
            return None

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Check if ComfyUI is accessible via GET /system_stats."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/system_stats",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get ComfyUI queue status."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/queue",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        queue_running = len(data.get("queue_running", []))
                        queue_pending = len(data.get("queue_pending", []))
                        return {
                            "queue_running": queue_running,
                            "queue_pending": queue_pending,
                            "total": queue_running + queue_pending,
                        }
        except Exception as e:
            logger.debug(f"[COMFYUI-WS] Queue status unavailable: {e}")

        return {"queue_running": 0, "queue_pending": 0, "total": 0}

    async def get_object_info(self) -> Optional[Dict[str, Any]]:
        """Get all installed nodes and models from ComfyUI."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/object_info",
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            logger.error(f"[COMFYUI-WS] object_info error: {e}")
        return None

    async def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get history for a specific prompt_id."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 200:
                        history = await response.json()
                        if prompt_id in history:
                            return history[prompt_id]
        except Exception as e:
            logger.error(f"[COMFYUI-WS] History error: {e}")
        return None

    async def interrupt(self) -> bool:
        """Interrupt currently running generation."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/interrupt",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"[COMFYUI-WS] Interrupt error: {e}")
            return False

    async def free_memory(self) -> bool:
        """POST /free to release VRAM (unload models)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/free",
                    json={"unload_models": True, "free_memory": True},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"[COMFYUI-WS] Free memory error: {e}")
            return False

    # ------------------------------------------------------------------
    # Legacy compatibility helpers
    # ------------------------------------------------------------------

    async def wait_for_completion(
        self,
        prompt_id: str,
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> Optional[Dict[str, Any]]:
        """Compatibility method: poll history until complete (like old clients).

        Returns the history entry dict, or None on timeout.
        """
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"[COMFYUI-WS] Timeout ({timeout}s) waiting for {prompt_id}")
                return None

            entry = await self.get_history(prompt_id)
            if entry:
                outputs = entry.get("outputs", {})
                if outputs:
                    logger.info(f"[COMFYUI-WS] Completed after {elapsed:.1f}s")
                    return entry
                status = entry.get("status", {}).get("status_str", "")
                if status == "error":
                    logger.error(f"[COMFYUI-WS] Workflow failed: {entry.get('status')}")
                    return None

            await asyncio.sleep(poll_interval)

    async def get_generated_images(self, history_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract image file info from a history entry (compatibility with comfyui_client)."""
        images = []
        for node_id, node_output in history_entry.get("outputs", {}).items():
            for img in node_output.get("images", []):
                images.append({
                    "filename": img.get("filename"),
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output"),
                    "node_id": node_id,
                })
        return images

    async def get_generated_audio(self, history_entry: Dict[str, Any]) -> List[str]:
        """Extract audio file paths from a history entry."""
        audio_files = []
        for node_output in history_entry.get("outputs", {}).values():
            for key in ("audio", "genaudio"):
                for aud in node_output.get(key, []):
                    filename = aud.get("filename")
                    if filename:
                        subfolder = aud.get("subfolder", "")
                        audio_files.append(f"{subfolder}/{filename}" if subfolder else filename)
        return audio_files

    async def get_generated_video(self, history_entry: Dict[str, Any]) -> List[str]:
        """Extract video file paths from a history entry."""
        video_files = []
        for node_output in history_entry.get("outputs", {}).values():
            for key in ("video", "genvideo", "gifs"):
                for vid in node_output.get(key, []):
                    filename = vid.get("filename")
                    if filename:
                        subfolder = vid.get("subfolder", "")
                        video_files.append(f"{subfolder}/{filename}" if subfolder else filename)
        return video_files

    async def get_image(
        self, filename: str, subfolder: str = "", folder_type: str = "output"
    ) -> Optional[bytes]:
        """Download a single file via /view (compatibility with comfyui_client.get_image)."""
        async with aiohttp.ClientSession() as session:
            return await self._download_view(session, filename, subfolder, folder_type)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_client: Optional[ComfyUIWebSocketClient] = None


def get_comfyui_ws_client(base_url: Optional[str] = None) -> ComfyUIWebSocketClient:
    """Get singleton ComfyUI WebSocket client."""
    global _client
    if _client is None:
        _client = ComfyUIWebSocketClient(base_url)
    return _client

"""
Triton Inference Server Client - High-performance batched inference

Session 149: Alternative backend for workshop scenarios
with multiple simultaneous users. Triton provides dynamic batching.

Architecture:
- HTTP/gRPC client for Triton Inference Server
- Supports SD3.5 and other diffusion models compiled to TensorRT
- Dynamic batching bundles concurrent requests for efficiency

Usage:
    client = get_triton_client()
    if await client.health_check():
        image_bytes = await client.generate_image(prompt="A red apple", seed=42)
"""

import logging
from typing import Optional, Dict, Any, List
import asyncio

logger = logging.getLogger(__name__)


class TritonSDClient:
    """
    Client for NVIDIA Triton Inference Server

    Triton hosts TensorRT-compiled SD3.5 models for fast, batched inference.
    Designed for workshop scenarios with 5+ simultaneous users.

    Ports:
    - 8000: HTTP Inference (default)
    - 8001: gRPC Inference (faster for batches)
    - 8002: Prometheus Metrics
    """

    def __init__(self, http_url: Optional[str] = None, grpc_url: Optional[str] = None):
        """
        Initialize Triton client

        Args:
            http_url: Triton HTTP endpoint (default: from config)
            grpc_url: Triton gRPC endpoint (default: from config)
        """
        from config import TRITON_SERVER_URL, TRITON_GRPC_URL, TRITON_TIMEOUT

        self.http_url = http_url or TRITON_SERVER_URL
        self.grpc_url = grpc_url or TRITON_GRPC_URL
        self.timeout = TRITON_TIMEOUT

        # Lazy-loaded clients (avoid import errors if tritonclient not installed)
        self._http_client = None
        self._grpc_client = None

        logger.info(f"[TRITON] Initialized client: HTTP={self.http_url}, gRPC={self.grpc_url}")

    def _get_http_client(self):
        """Lazy-load HTTP client"""
        if self._http_client is None:
            try:
                import tritonclient.http as httpclient
                self._http_client = httpclient.InferenceServerClient(
                    url=self.http_url,
                    verbose=False
                )
            except ImportError:
                logger.error("[TRITON] tritonclient not installed. Run: pip install tritonclient[http]")
                raise RuntimeError("tritonclient not installed")
        return self._http_client

    def _get_grpc_client(self):
        """Lazy-load gRPC client"""
        if self._grpc_client is None:
            try:
                import tritonclient.grpc as grpcclient
                self._grpc_client = grpcclient.InferenceServerClient(
                    url=self.grpc_url,
                    verbose=False
                )
            except ImportError:
                logger.error("[TRITON] tritonclient not installed. Run: pip install tritonclient[grpc]")
                raise RuntimeError("tritonclient not installed")
        return self._grpc_client

    async def health_check(self) -> bool:
        """
        Check if Triton server is healthy and ready

        Returns:
            True if server is ready, False otherwise
        """
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.http_url}/v2/health/ready",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    is_ready = response.status == 200
                    if is_ready:
                        logger.debug("[TRITON] Health check passed")
                    else:
                        logger.warning(f"[TRITON] Health check failed: HTTP {response.status}")
                    return is_ready

        except Exception as e:
            logger.debug(f"[TRITON] Health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """
        List available models on Triton server

        Returns:
            List of model names
        """
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.http_url}/v2/models",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m["name"] for m in data.get("models", [])]
                        logger.info(f"[TRITON] Available models: {models}")
                        return models
                    else:
                        logger.warning(f"[TRITON] Failed to list models: HTTP {response.status}")
                        return []

        except Exception as e:
            logger.error(f"[TRITON] Error listing models: {e}")
            return []

    async def generate_image(
        self,
        prompt: str,
        model_name: str = "stable_diffusion_pipeline",
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 25,
        cfg_scale: float = 5.5,
        seed: int = -1,
        **kwargs
    ) -> Optional[bytes]:
        """
        Generate image using Triton-hosted SD pipeline

        Args:
            prompt: Positive prompt text
            model_name: Triton model name (default: stable_diffusion_pipeline)
            negative_prompt: Negative prompt text
            width: Image width
            height: Image height
            steps: Number of sampling steps
            cfg_scale: Classifier-free guidance scale
            seed: Random seed (-1 for random)
            **kwargs: Additional parameters

        Returns:
            PNG image bytes, or None on failure
        """
        try:
            import numpy as np
            import tritonclient.http as httpclient

            # Generate random seed if needed
            if seed == -1:
                import random
                seed = random.randint(0, 2**32 - 1)
                logger.info(f"[TRITON] Generated random seed: {seed}")

            client = self._get_http_client()

            # Prepare inputs
            # Note: Exact input names depend on Triton model configuration
            inputs = []

            # Prompt input (string → bytes for Triton)
            prompt_input = httpclient.InferInput("prompt", [1], "BYTES")
            prompt_input.set_data_from_numpy(np.array([prompt.encode()], dtype=np.object_))
            inputs.append(prompt_input)

            # Negative prompt
            neg_prompt_input = httpclient.InferInput("negative_prompt", [1], "BYTES")
            neg_prompt_input.set_data_from_numpy(np.array([negative_prompt.encode()], dtype=np.object_))
            inputs.append(neg_prompt_input)

            # Generation parameters
            seed_input = httpclient.InferInput("seed", [1], "INT64")
            seed_input.set_data_from_numpy(np.array([seed], dtype=np.int64))
            inputs.append(seed_input)

            steps_input = httpclient.InferInput("steps", [1], "INT32")
            steps_input.set_data_from_numpy(np.array([steps], dtype=np.int32))
            inputs.append(steps_input)

            cfg_input = httpclient.InferInput("cfg_scale", [1], "FP32")
            cfg_input.set_data_from_numpy(np.array([cfg_scale], dtype=np.float32))
            inputs.append(cfg_input)

            width_input = httpclient.InferInput("width", [1], "INT32")
            width_input.set_data_from_numpy(np.array([width], dtype=np.int32))
            inputs.append(width_input)

            height_input = httpclient.InferInput("height", [1], "INT32")
            height_input.set_data_from_numpy(np.array([height], dtype=np.int32))
            inputs.append(height_input)

            # Request output
            outputs = [httpclient.InferRequestedOutput("image")]

            # Run inference
            logger.info(f"[TRITON] Generating image: model={model_name}, steps={steps}, size={width}x{height}")

            # Note: Triton HTTP client is synchronous, wrap in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.infer(
                    model_name=model_name,
                    inputs=inputs,
                    outputs=outputs,
                    timeout=self.timeout
                )
            )

            # Extract image bytes from response
            image_data = response.as_numpy("image")

            if image_data is not None and len(image_data) > 0:
                # Assuming model returns PNG bytes directly
                # If model returns raw pixels, encoding would be needed here
                image_bytes = image_data.tobytes()
                logger.info(f"[TRITON] Generated image: {len(image_bytes)} bytes")
                return image_bytes
            else:
                logger.error("[TRITON] No image data in response")
                return None

        except ImportError:
            logger.error("[TRITON] tritonclient not installed")
            return None
        except Exception as e:
            logger.error(f"[TRITON] Error generating image: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_model_metadata(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific model

        Args:
            model_name: Name of the model

        Returns:
            Model metadata dict, or None on failure
        """
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.http_url}/v2/models/{model_name}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"[TRITON] Model {model_name} metadata: {data}")
                        return data
                    else:
                        logger.warning(f"[TRITON] Failed to get model metadata: HTTP {response.status}")
                        return None

        except Exception as e:
            logger.error(f"[TRITON] Error getting model metadata: {e}")
            return None

    async def get_server_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get server statistics from Triton metrics endpoint

        Returns:
            Dict with server stats, or None on failure
        """
        try:
            import aiohttp
            from config import TRITON_METRICS_URL

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{TRITON_METRICS_URL}/metrics",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        # Prometheus format - parse basic stats
                        text = await response.text()
                        # Basic parsing - could be enhanced with prometheus_client
                        stats = {
                            "raw_metrics": text[:1000],  # First 1000 chars
                            "status": "available"
                        }
                        return stats
                    else:
                        return None

        except Exception as e:
            logger.debug(f"[TRITON] Error getting stats: {e}")
            return None


# Singleton instance
_client: Optional[TritonSDClient] = None


def get_triton_client(http_url: Optional[str] = None, grpc_url: Optional[str] = None) -> TritonSDClient:
    """
    Get Triton client singleton

    Args:
        http_url: Optional HTTP endpoint override
        grpc_url: Optional gRPC endpoint override

    Returns:
        TritonSDClient instance
    """
    global _client
    if _client is None:
        _client = TritonSDClient(http_url, grpc_url)
    return _client


def reset_triton_client():
    """Reset the singleton client (for testing)"""
    global _client
    _client = None

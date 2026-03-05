"""
Blender Service — Headless Mesh Rendering via Subprocess

Renders 3D meshes (GLB) to preview PNGs using Blender's Eevee engine.
Blender is called as a subprocess with --background --python,
using its own embedded Python (NOT the venv Python).

Features:
- Async subprocess execution via asyncio.to_thread
- Configurable camera, lighting, and resolution
- 30s timeout (Eevee renders in 1-5s typically)
- Fail-safe: rendering failure never blocks generation
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BlenderService:
    """Headless Blender rendering service for 3D mesh previews."""

    def __init__(self):
        from config import BLENDER_PATH, BLENDER_SCRIPTS_PATH
        self.blender_path = BLENDER_PATH
        self.scripts_path = Path(BLENDER_SCRIPTS_PATH)
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if Blender binary is accessible."""
        if self._available is not None:
            return self._available

        try:
            result = subprocess.run(
                [self.blender_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._available = result.returncode == 0
            if self._available:
                version = result.stdout.strip().split('\n')[0]
                logger.info(f"[BLENDER] Found: {version}")
            else:
                logger.warning(f"[BLENDER] Binary found but returned error: {result.stderr}")
        except FileNotFoundError:
            logger.warning(f"[BLENDER] Binary not found at: {self.blender_path}")
            self._available = False
        except Exception as e:
            logger.warning(f"[BLENDER] Availability check failed: {e}")
            self._available = False

        return self._available

    async def render_mesh(
        self,
        glb_path: str,
        output_path: str,
        camera_distance: float = 2.5,
        camera_elevation: float = 30.0,
        camera_azimuth: float = 45.0,
        light_type: str = "three_point",
        resolution: int = 1024,
        background_color: str = "#0a0a0a",
    ) -> bool:
        """
        Render a GLB mesh to a PNG preview image using Blender Eevee.

        Args:
            glb_path: Path to the input GLB file
            output_path: Path for the output PNG file
            camera_distance: Distance from camera to object center
            camera_elevation: Camera elevation angle in degrees
            camera_azimuth: Camera azimuth angle in degrees
            light_type: Lighting setup ('three_point', 'studio', 'ambient')
            resolution: Output image resolution (square)
            background_color: Background hex color

        Returns:
            True if rendering succeeded, False otherwise
        """
        import asyncio
        return await asyncio.to_thread(
            self._render_sync,
            glb_path=glb_path,
            output_path=output_path,
            camera_distance=camera_distance,
            camera_elevation=camera_elevation,
            camera_azimuth=camera_azimuth,
            light_type=light_type,
            resolution=resolution,
            background_color=background_color,
        )

    def _render_sync(
        self,
        glb_path: str,
        output_path: str,
        camera_distance: float,
        camera_elevation: float,
        camera_azimuth: float,
        light_type: str,
        resolution: int,
        background_color: str,
    ) -> bool:
        """Synchronous Blender render call."""
        if not self.is_available():
            logger.warning("[BLENDER] Not available, skipping render")
            return False

        render_script = self.scripts_path / "render_mesh.py"
        if not render_script.exists():
            logger.error(f"[BLENDER] Render script not found: {render_script}")
            return False

        # Write config to temp JSON file (Blender reads via sys.argv after --)
        config = {
            "glb_path": str(glb_path),
            "output_path": str(output_path),
            "camera_distance": camera_distance,
            "camera_elevation": camera_elevation,
            "camera_azimuth": camera_azimuth,
            "light_type": light_type,
            "resolution": resolution,
            "background_color": background_color,
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            config_path = f.name

        try:
            logger.info(f"[BLENDER] Rendering: {glb_path} → {output_path} ({resolution}x{resolution})")

            result = subprocess.run(
                [
                    self.blender_path,
                    '--background',
                    '--python', str(render_script),
                    '--', config_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error(f"[BLENDER] Render failed (exit {result.returncode}): {result.stderr[-500:]}")
                return False

            # Verify output file exists
            if not Path(output_path).exists():
                logger.error(f"[BLENDER] Output file not created: {output_path}")
                return False

            logger.info(f"[BLENDER] Render successful: {output_path}")
            return True

        except subprocess.TimeoutExpired:
            logger.error("[BLENDER] Render timed out (30s)")
            return False
        except Exception as e:
            logger.error(f"[BLENDER] Render error: {e}")
            return False
        finally:
            # Clean up config file
            try:
                Path(config_path).unlink(missing_ok=True)
            except Exception:
                pass


# Singleton
_service: Optional[BlenderService] = None


def get_blender_service() -> BlenderService:
    global _service
    if _service is None:
        _service = BlenderService()
    return _service

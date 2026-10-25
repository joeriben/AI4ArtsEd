"""
CanvasRecorder - Recording system for Canvas workflows

Based on LivePipelineRecorder but adapted for Canvas:
- No fixed expected_outputs (workflow defines structure)
- Saves workflow.json at init
- save_entity() includes node_id for traceability
- No stage-based state (Canvas is a graph, not a pipeline)
"""

import json
import logging
import os
import requests
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

# Held while a metadata.json is written and moved into place, so a save of one
# run cannot overtake a later one (pipeline_recorder._metadata_save_lock, same
# reason).
_metadata_save_lock = threading.Lock()


class CanvasRecorder:
    """
    Recorder for Canvas workflow executions.

    Key features:
    1. Writes files immediately (same pattern as LivePipelineRecorder)
    2. Stores workflow.json at initialization
    3. Tracks node_id for each entity (graph traceability)
    4. No fixed expected_outputs - workflow defines what's produced
    5. Single metadata.json with complete state
    """

    def __init__(
        self,
        run_id: str,
        workflow: Dict[str, Any],
        device_id: Optional[str] = None,
        user_id: str = 'anonymous',
        batch_id: Optional[str] = None,
        batch_index: Optional[int] = None,
        base_path: Optional[Path] = None
    ):
        """
        Initialize recorder and save workflow.

        Args:
            run_id: Unique identifier for this canvas run
            workflow: Canvas workflow definition (nodes, connections)
            device_id: Device/browser identifier (auto-generated if None)
            user_id: User identifier
            batch_id: Optional batch identifier (for batch runs)
            batch_index: Optional index within batch (0, 1, 2, ...)
            base_path: Base directory for exports/json/
        """
        import uuid as uuid_module

        self.run_id = run_id
        self.workflow = workflow
        self.user_id = user_id
        self.batch_id = batch_id
        self.batch_index = batch_index
        self.device_id = device_id or f"canvas_{uuid_module.uuid4().hex[:12]}"

        # Setup folder structure
        if base_path is None:
            from config import JSON_STORAGE_DIR
            base_path = JSON_STORAGE_DIR
        self.base_path = Path(base_path)

        # Date + Device based folder structure
        # exports/json/YYYY-MM-DD/device_id/run_xxx_canvas/
        date_folder = datetime.now().strftime('%Y-%m-%d')
        self.run_folder = self.base_path / date_folder / self.device_id / run_id
        self.run_folder.mkdir(parents=True, exist_ok=True)

        # final/ subfolder for outputs
        self.final_folder = self.run_folder / "final"
        self.final_folder.mkdir(parents=True, exist_ok=True)

        # Initialize state
        self.sequence_number = 0

        # Initialize metadata
        self.metadata = {
            "run_id": run_id,
            "type": "canvas_workflow",
            "timestamp": datetime.now().isoformat(),
            "device_id": self.device_id,
            "user_id": user_id,
            "workflow_file": "workflow.json",
            "entities": []
        }

        # Add batch info if present
        if batch_id:
            self.metadata["batch_id"] = batch_id
        if batch_index is not None:
            self.metadata["batch_index"] = batch_index

        # Save workflow.json
        self._save_workflow(workflow)

        # Write initial metadata
        self._save_metadata()

        logger.info(f"[CANVAS_RECORDER] Initialized run {run_id} in {self.run_folder}")

    def save_entity(
        self,
        node_id: str,
        node_type: str,
        content: Union[str, bytes, dict],
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Save a node output to disk immediately.

        Args:
            node_id: Canvas node ID that produced this output
            node_type: Node type (input, interception, generation, etc.)
            content: Entity content (text, bytes, or dict)
            metadata: Optional additional metadata

        Returns:
            Sequence number of saved entity
        """
        self.sequence_number += 1

        # Determine file extension based on content type
        if isinstance(content, bytes):
            ext = self._detect_format_from_data(content, node_type)
        elif isinstance(content, dict):
            ext = "json"
        else:
            ext = "txt"

        # Filename: {sequence:02d}_{node_type}.{ext}
        filename = f"{self.sequence_number:02d}_{node_type}.{ext}"
        filepath = self.final_folder / filename

        # AI-Origin Disclosure (EU AI Act Art. 50). The canvas is a second,
        # complete production path: what it hands out is as much a generated
        # medium as anything from the schema pipeline. It left unmarked for as
        # long as this recorder wrote past the watermark service.
        if isinstance(content, bytes):
            from my_app.services.media_marking import mark_or_pass
            content = mark_or_pass(content, node_type, metadata or {}, "[CANVAS_RECORDER]")

        # Write file
        self._write_file(filepath, content)

        # Build entity record
        entity_record = {
            "sequence": self.sequence_number,
            "node_id": node_id,
            "node_type": node_type,
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.metadata["entities"].append(entity_record)

        self._save_metadata()

        logger.info(f"[CANVAS_RECORDER] Saved entity {self.sequence_number}: {node_type} (node {node_id}) -> {filename}")
        return self.sequence_number

    def save_image_from_url(
        self,
        node_id: str,
        url: str,
        config_id: str,
        seed: Optional[int] = None
    ) -> Optional[int]:
        """
        Download image from URL and save as entity.

        Args:
            node_id: Canvas node ID
            url: Image URL to download
            config_id: Generation config used
            seed: Optional seed value

        Returns:
            Sequence number of saved entity, or None if failed
        """
        try:
            # Canvas media URLs return RELATIVE (e.g. /api/media/image/<run>/<idx>) --
            # fine for the browser, but requests.get() needs a scheme for this
            # server-side re-fetch. Resolve against the local server.
            fetch_url = url
            if fetch_url.startswith('/'):
                from config import PORT
                fetch_url = f"http://127.0.0.1:{PORT}{fetch_url}"
            response = requests.get(fetch_url, timeout=60)
            response.raise_for_status()
            image_data = response.content

            metadata = {
                "config_id": config_id,
                "source_url": url,
                "format": self._detect_format_from_data(image_data, "generation")
            }
            if seed is not None:
                metadata["seed"] = seed

            # Get image dimensions
            try:
                img = Image.open(BytesIO(image_data))
                metadata["width"] = img.width
                metadata["height"] = img.height
            except Exception:
                pass

            return self.save_entity(
                node_id=node_id,
                node_type="generation",
                content=image_data,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"[CANVAS_RECORDER] Failed to download image from {url}: {e}")
            return None


    def get_entity_by_sequence(self, sequence: int) -> Optional[Dict[str, Any]]:
        """
        Get entity record by sequence number.

        Args:
            sequence: Sequence number

        Returns:
            Entity record dict, or None if not found
        """
        for entity in self.metadata["entities"]:
            if entity["sequence"] == sequence:
                return entity
        return None

    def get_entity_path(self, sequence: int) -> Optional[Path]:
        """
        Get filesystem path for entity by sequence number.

        Args:
            sequence: Sequence number

        Returns:
            Path to entity file, or None if not found
        """
        entity = self.get_entity_by_sequence(sequence)
        if entity:
            return self.final_folder / entity["filename"]
        return None


    def mark_complete(self):
        """Mark the run as complete."""
        self.metadata["completed_at"] = datetime.now().isoformat()
        self.metadata["total_entities"] = len(self.metadata["entities"])
        self._save_metadata()
        logger.info(f"[CANVAS_RECORDER] Run {self.run_id} marked complete with {self.sequence_number} entities")

    def _save_workflow(self, workflow: Dict[str, Any]):
        """Save workflow.json to run folder."""
        workflow_path = self.run_folder / "workflow.json"
        workflow_path.write_text(
            json.dumps(workflow, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        logger.info(f"[CANVAS_RECORDER] Saved workflow.json with {len(workflow.get('nodes', []))} nodes")

    def _save_metadata(self):
        """Save metadata.json to disk.

        Written beside it and moved over it, so a reader never finds part of a
        record (pipeline_recorder._save_metadata, same pattern).
        """
        metadata_path = self.run_folder / "metadata.json"
        tmp = metadata_path.with_name(f"{metadata_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with _metadata_save_lock:
                tmp.write_text(
                    json.dumps(self.metadata, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
                os.replace(str(tmp), str(metadata_path))
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise

    def _write_file(self, filepath: Path, content: Union[str, bytes, dict]):
        """Write content to file with appropriate encoding."""
        if isinstance(content, bytes):
            filepath.write_bytes(content)
        elif isinstance(content, dict):
            filepath.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding='utf-8')
        else:
            filepath.write_text(str(content), encoding='utf-8')

    def _detect_format_from_data(self, data: bytes, node_type: str) -> str:
        """Detect file format from binary data."""
        if node_type == "generation":
            try:
                img = Image.open(BytesIO(data))
                return img.format.lower() if img.format else 'png'
            except Exception:
                return 'png'
        elif node_type in ['audio', 'music']:
            if data[:4] == b'RIFF':
                return 'wav'
            elif data[:3] == b'ID3' or data[:2] == b'\xff\xfb':
                return 'mp3'
            return 'wav'
        elif node_type == 'video':
            if len(data) >= 8 and data[4:8] == b'ftyp':
                return 'mp4'
            return 'mp4'
        return 'bin'


# Active recorders registry
_active_canvas_recorders: Dict[str, CanvasRecorder] = {}


def get_canvas_recorder(
    run_id: str,
    workflow: Optional[Dict[str, Any]] = None,
    device_id: Optional[str] = None,
    user_id: str = 'anonymous',
    batch_id: Optional[str] = None,
    batch_index: Optional[int] = None,
    base_path: Optional[Path] = None
) -> CanvasRecorder:
    """
    Get or create a canvas recorder for a specific run.

    Args:
        run_id: Unique run identifier
        workflow: Canvas workflow (required for new recorders)
        device_id: Device identifier
        user_id: User identifier
        batch_id: Optional batch identifier
        batch_index: Optional batch index
        base_path: Base directory

    Returns:
        CanvasRecorder instance
    """
    if run_id in _active_canvas_recorders:
        return _active_canvas_recorders[run_id]

    if workflow is None:
        raise ValueError("workflow required for new canvas recorder")

    recorder = CanvasRecorder(
        run_id=run_id,
        workflow=workflow,
        device_id=device_id,
        user_id=user_id,
        batch_id=batch_id,
        batch_index=batch_index,
        base_path=base_path
    )
    _active_canvas_recorders[run_id] = recorder
    return recorder


def cleanup_canvas_recorder(run_id: str):
    """Remove recorder from active registry."""
    if run_id in _active_canvas_recorders:
        del _active_canvas_recorders[run_id]
        logger.info(f"[CANVAS_RECORDER] Cleaned up recorder for {run_id}")

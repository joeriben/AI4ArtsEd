"""
Execution History Data Models

Defines all data structures for tracking pipeline execution history:
- MediaType enum: Categories of media (text, image, audio, music, video, 3d, metadata)
- ItemType enum: Specific event types (20+ types across all stages)
- ExecutionItem: Single event in pipeline execution
- ExecutionRecord: Complete execution history with all items

Created: 2025-11-03 (Session 20 - Phase 1)
Based on: docs/ITEM_TYPE_TAXONOMY.md v1.0
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional


# ============================================================================
# ENUMS
# ============================================================================

class MediaType(str, Enum):
    """Media type classification for execution items"""
    TEXT = "text"           # Text content (prompts, translations, transformations)
    IMAGE = "image"         # Generated or uploaded images
    AUDIO = "audio"         # Speech, sound effects
    MUSIC = "music"         # Musical compositions (specialized audio)
    VIDEO = "video"         # Video generations
    THREE_D = "3d"          # 3D models
    METADATA = "metadata"   # System events, safety checks (no content/file)


class ItemType(str, Enum):
    """
    Semantic item type taxonomy (v1.0)

    Based on: docs/ITEM_TYPE_TAXONOMY.md
    Version: 1.0 (2025-11-03)
    """

    # Stage 1: Translation + Safety
    USER_INPUT_TEXT = "user_input_text"
    USER_INPUT_IMAGE = "user_input_image"
    TRANSLATION_RESULT = "translation_result"
    STAGE1_SAFETY_CHECK = "stage1_safety_check"
    STAGE1_SAFETY_CHECK_IMAGE = "stage1_safety_check_image"
    STAGE1_BLOCKED = "stage1_blocked"

    # Stage 2: Interception (can be recursive)
    INTERCEPTION_ITERATION = "interception_iteration"
    INTERCEPTION_FINAL = "interception_final"

    # Stage 3: Pre-Output Safety
    STAGE3_SAFETY_CHECK = "stage3_safety_check"
    STAGE3_BLOCKED = "stage3_blocked"

    # Stage 4: Output Generation
    OUTPUT_IMAGE = "output_image"
    OUTPUT_AUDIO = "output_audio"
    OUTPUT_MUSIC = "output_music"
    OUTPUT_VIDEO = "output_video"
    OUTPUT_3D = "output_3d"

    # System Events
    PIPELINE_START = "pipeline_start"
    PIPELINE_COMPLETE = "pipeline_complete"
    PIPELINE_ERROR = "pipeline_error"
    STAGE_TRANSITION = "stage_transition"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ExecutionItem:
    """
    Single event/item in pipeline execution

    Represents one tracked event during the 4-stage pipeline flow.
    Examples: user input, translation result, safety check, generated image

    Performance: Lightweight dataclass, fast to create (~0.1ms)
    """

    # Chronological ordering
    sequence_number: int              # Global sequence (1, 2, 3, ...)
    timestamp: datetime               # When this event occurred

    # Stage context
    stage: int                        # Which stage (0=start, 1-4=stages, 5=complete)
    stage_iteration: Optional[int] = None    # For Stage 2 recursive (1-8 for Stille Post)
    loop_iteration: Optional[int] = None     # For Stage 3-4 multi-output (1, 2, 3, ...)

    # Classification
    media_type: MediaType = MediaType.METADATA     # Media category
    item_type: ItemType = ItemType.PIPELINE_START  # Semantic type

    # Content
    content: Optional[str] = None          # Text content (prompts, translations, errors)
    file_path: Optional[str] = None        # Media file path (images, audio, etc.)

    # Technical metadata
    config_used: Optional[str] = None      # Which config generated this (dada, sd35_large)
    model_used: Optional[str] = None       # Which model (qwen3:4b, sd35_large)
    backend_type: Optional[str] = None     # local_llm | comfyui | openrouter
    execution_time: Optional[float] = None # Duration in seconds

    # Flexible metadata (for reproducibility)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        result = asdict(self)

        # Convert enums to strings
        result['media_type'] = self.media_type.value
        result['item_type'] = self.item_type.value

        # Convert timestamp to ISO format
        result['timestamp'] = self.timestamp.isoformat()

        return result

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ExecutionItem':
        """Create ExecutionItem from dict"""
        # Convert string timestamp back to datetime
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])

        # Convert string enums back to enum types
        if isinstance(data.get('media_type'), str):
            data['media_type'] = MediaType(data['media_type'])
        if isinstance(data.get('item_type'), str):
            data['item_type'] = ItemType(data['item_type'])

        return ExecutionItem(**data)


@dataclass
class ExecutionRecord:
    """
    Complete execution history for one pipeline run

    Contains all tracked items from pipeline start to completion.
    Represents the full pedagogical journey through the 4 stages.

    Storage: Persisted as JSON file in exports/executions/
    """

    # Identifiers
    execution_id: str                      # Unique ID (exec_YYYYMMDD_HHMMSS_abc123)
    config_name: str                       # Schema/config used (dada, stillepost, etc.)
    timestamp: datetime                    # When pipeline started

    # User context
    user_id: str = "anonymous"             # User identifier
    session_id: str = "default"            # Session identifier

    # Execution parameters
    safety_level: str = "kids"             # kids | teens | adults
    used_seed: Optional[int] = None        # Random seed (if applicable)

    # Performance
    total_execution_time: float = 0.0      # Total duration in seconds

    # All tracked items (chronological order)
    items: List[ExecutionItem] = field(default_factory=list)

    # Taxonomy version (for future compatibility)
    taxonomy_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            'execution_id': self.execution_id,
            'config_name': self.config_name,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'session_id': self.session_id,
            'safety_level': self.safety_level,
            'used_seed': self.used_seed,
            'total_execution_time': self.total_execution_time,
            'items': [item.to_dict() for item in self.items],
            'taxonomy_version': self.taxonomy_version
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ExecutionRecord':
        """Create ExecutionRecord from dict"""
        # Convert timestamp
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])

        # Convert items list
        if 'items' in data:
            data['items'] = [
                ExecutionItem.from_dict(item_dict)
                for item_dict in data['items']
            ]

        return ExecutionRecord(**data)

    def get_items_by_stage(self, stage: int) -> List[ExecutionItem]:
        """Get all items for a specific stage"""
        return [item for item in self.items if item.stage == stage]

    def get_items_by_type(self, item_type: ItemType) -> List[ExecutionItem]:
        """Get all items of a specific type"""
        return [item for item in self.items if item.item_type == item_type]

    def get_items_by_media_type(self, media_type: MediaType) -> List[ExecutionItem]:
        """Get all items of a specific media type"""
        return [item for item in self.items if item.media_type == media_type]

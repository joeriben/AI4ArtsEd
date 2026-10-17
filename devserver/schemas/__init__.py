"""
Schema-basierte Pipeline-Architektur für AI4ArtsEd
Clean 3-Layer Architecture: Chunks → Pipelines → Configs
"""
from .engine.chunk_builder import ChunkBuilder
from .engine.backend_router import BackendRouter
from .engine.pipeline_executor import PipelineExecutor
from .engine.config_loader import config_loader

__all__ = [
    'ChunkBuilder',
    'BackendRouter',
    'PipelineExecutor',
    'config_loader'
]

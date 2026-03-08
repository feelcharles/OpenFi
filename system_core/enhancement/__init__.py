"""
Enhancement Module

Provides vector database integration and external tool management.
"""

from system_core.enhancement.vector_db import VectorDB, PineconeDB, SearchResult
from system_core.enhancement.embedding_service import EmbeddingService
from system_core.enhancement.enhancement_module import EnhancementModule
from system_core.enhancement.external_tools import ExternalToolRegistry, ExternalTool

__all__ = [
    'VectorDB',
    'PineconeDB',
    'SearchResult',
    'EmbeddingService',
    'EnhancementModule',
    'ExternalToolRegistry',
    'ExternalTool'
]

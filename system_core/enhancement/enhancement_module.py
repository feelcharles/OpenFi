"""
Enhancement Module - Vector database integration and external tool support.

This module provides:
- Vector storage pipeline (subscribe to ai.analyzed events)
- Semantic search for AI context
- Automatic cleanup of old vectors
- Metrics tracking
"""

import asyncio
from typing import Any, Optional
from datetime import datetime, timedelta
import yaml
from pathlib import Path

from system_core.config import get_logger
from system_core.enhancement.vector_db import VectorDB, PineconeDB
from system_core.enhancement.embedding_service import EmbeddingService

logger = get_logger(__name__)

class EnhancementModule:
    """Enhancement module for vector database and external tools."""
    
    def __init__(
        self,
        config_path: str = "config/vector_db.yaml",
        event_bus=None,
        redis_client=None
    ):
        """
        Initialize Enhancement Module.
        
        Args:
            config_path: Path to vector DB configuration
            event_bus: Event bus instance for subscribing to events
            redis_client: Redis client for caching
        """
        self.config_path = Path(config_path)
        self.event_bus = event_bus
        self.redis_client = redis_client
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize components
        self.vector_db = self._initialize_vector_db()
        self.embedding_service = EmbeddingService(
            self.config.get('embedding', {}),
            redis_client=redis_client
        )
        
        # Metrics
        self.metrics = {
            'total_vectors_stored': 0,
            'search_queries_per_day': 0,
            'total_search_queries': 0,
            'avg_search_latency_ms': 0.0,
            'storage_size_mb': 0.0
        }
        
        logger.info("enhancement_module_initialized",
                   config_path=str(self.config_path),
                   provider=self.config.get('provider'))
    
    def _load_config(self) -> dict[str, Any]:
        """Load vector database configuration."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            logger.info("vector_db_config_loaded", config_path=str(self.config_path))
            return config
            
        except Exception as e:
            logger.error("config_load_failed", error=str(e))
            raise
    
    def _initialize_vector_db(self) -> VectorDB:
        """Initialize vector database based on provider."""
        provider = self.config.get('provider', 'pinecone')
        
        if provider == 'pinecone':
            return PineconeDB(self.config)
        else:
            raise ValueError(f"Unsupported vector DB provider: {provider}")
    
    async def start(self):
        """Start the enhancement module and subscribe to events."""
        if self.event_bus:
            # Subscribe to ai.analyzed events
            await self.event_bus.subscribe("ai.analyzed", self._handle_analyzed_event)
            logger.info("subscribed_to_ai_analyzed_events")
        
        # Start cleanup job if enabled
        if self.config.get('cleanup', {}).get('enabled', True):
            asyncio.create_task(self._run_cleanup_job())
            logger.info("cleanup_job_scheduled")
    
    async def _handle_analyzed_event(self, event: dict[str, Any]):
        """
        Handle ai.analyzed events and store vectors.
        
        Args:
            event: Event data from event bus
        """
        try:
            payload = event.get('payload', {})
            
            # Extract text content for embedding
            text_content = self._extract_text_content(payload)
            if not text_content:
                logger.warning("no_text_content_in_event", event_id=event.get('event_id'))
                return
            
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(text_content)
            
            # Prepare metadata
            metadata = {
                'source': payload.get('source', 'unknown'),
                'timestamp': payload.get('timestamp', datetime.now().isoformat()),
                'data_type': payload.get('data_type', 'unknown'),
                'summary': payload.get('summary', '')[:500],  # Limit to 500 chars
                'relevance_score': payload.get('relevance_score', 0),
                'original_text': text_content[:1000]  # Limit to 1000 chars
            }
            
            # Store in vector database
            ids = await self.vector_db.insert(
                vectors=[embedding],
                metadata=[metadata]
            )
            
            # Update metrics
            self.metrics['total_vectors_stored'] += 1
            
            logger.info("vector_stored",
                       vector_id=ids[0],
                       source=metadata['source'],
                       relevance_score=metadata['relevance_score'])
            
        except Exception as e:
            logger.error("vector_storage_failed",
                        event_id=event.get('event_id'),
                        error=str(e))
    
    def _extract_text_content(self, payload: dict[str, Any]) -> str:
        """
        Extract text content from event payload.
        
        Args:
            payload: Event payload
            
        Returns:
            Extracted text content
        """
        # Try different fields for text content
        content = payload.get('content', '')
        summary = payload.get('summary', '')
        
        if isinstance(content, dict):
            # If content is a dict, try to extract text fields
            text_parts = []
            for key in ['text', 'title', 'description', 'body']:
                if key in content:
                    text_parts.append(str(content[key]))
            content = ' '.join(text_parts)
        
        # Combine content and summary
        text = f"{content} {summary}".strip()
        
        return text
    
    async def semantic_search(
        self,
        query_text: str,
        top_k: int = 5,
        filter: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search for similar historical items.
        
        Args:
            query_text: Query text
            top_k: Number of results to return (default: 5)
            filter: Optional metadata filter
            
        Returns:
            List of similar items with metadata
        """
        try:
            start_time = datetime.now()
            
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query_text)
            
            # Search vector database
            results = await self.vector_db.search(
                query_vector=query_embedding,
                top_k=top_k,
                filter=filter
            )
            
            # Calculate latency
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Update metrics
            self.metrics['total_search_queries'] += 1
            self.metrics['search_queries_per_day'] += 1
            
            # Update average latency
            prev_avg = self.metrics['avg_search_latency_ms']
            total_queries = self.metrics['total_search_queries']
            self.metrics['avg_search_latency_ms'] = (
                (prev_avg * (total_queries - 1) + latency_ms) / total_queries
            )
            
            logger.info("semantic_search_completed",
                       query_length=len(query_text),
                       results_count=len(results),
                       latency_ms=latency_ms,
                       top_k=top_k)
            
            # Convert SearchResult objects to dicts
            return [
                {
                    'id': result.id,
                    'score': result.score,
                    'metadata': result.metadata
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error("semantic_search_failed",
                        query_length=len(query_text),
                        error=str(e))
            return []
    
    async def _run_cleanup_job(self):
        """Run periodic cleanup job to delete old vectors."""
        cleanup_config = self.config.get('cleanup', {})
        retention_days = cleanup_config.get('retention_days', 90)
        
        # Parse schedule (cron format)
        # For simplicity, we'll run daily at 3 AM UTC
        while True:
            try:
                # Calculate next run time (3 AM UTC)
                now = datetime.utcnow()
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                # Wait until next run
                wait_seconds = (next_run - now).total_seconds()
                logger.info("cleanup_job_scheduled_next_run",
                           next_run=next_run.isoformat(),
                           wait_seconds=wait_seconds)
                
                await asyncio.sleep(wait_seconds)
                
                # Run cleanup
                await self._cleanup_old_vectors(retention_days)
                
            except Exception as e:
                logger.error("cleanup_job_failed", error=str(e))
                # Wait 1 hour before retrying
                await asyncio.sleep(3600)
    
    async def _cleanup_old_vectors(self, retention_days: int):
        """
        Delete vectors older than retention period.
        
        Args:
            retention_days: Number of days to retain vectors
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            cutoff_timestamp = cutoff_date.isoformat()
            
            # Delete vectors with timestamp < cutoff
            filter = {
                'timestamp': {'$lt': cutoff_timestamp}
            }
            
            deleted_count = await self.vector_db.delete(filter=filter)
            
            logger.info("cleanup_completed",
                       retention_days=retention_days,
                       cutoff_date=cutoff_timestamp,
                       deleted_count=deleted_count)
            
        except Exception as e:
            logger.error("cleanup_failed", error=str(e))
    
    async def get_metrics(self) -> dict[str, Any]:
        """
        Get vector database metrics.
        
        Returns:
            Dictionary with metrics
        """
        try:
            # Get stats from vector DB
            db_stats = await self.vector_db.get_stats()
            
            # Combine with local metrics
            metrics = {
                **self.metrics,
                'db_stats': db_stats
            }
            
            return metrics
            
        except Exception as e:
            logger.error("metrics_retrieval_failed", error=str(e))
            return self.metrics

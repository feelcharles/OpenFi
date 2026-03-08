"""
Vector Database Module - Abstract interface and implementations for vector storage.

This module provides:
- Abstract VectorDB interface
- Pinecone adapter implementation
- Vector search and storage capabilities
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel
from system_core.config import get_logger

logger = get_logger(__name__)

class SearchResult(BaseModel):
    """Vector search result."""
    id: str
    score: float
    metadata: dict[str, Any]

class VectorDB(ABC):
    """Abstract vector database interface."""
    
    @abstractmethod
    async def insert(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
        ids: Optional[list[str]] = None
    ) -> list[str]:
        """
        Insert vectors with metadata.
        
        Args:
            vectors: List of embedding vectors
            metadata: List of metadata dictionaries (one per vector)
            ids: Optional list of IDs (auto-generated if not provided)
            
        Returns:
            List of inserted vector IDs
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter: Optional[dict[str, Any]] = None
    ) -> list[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filter: Optional metadata filter
            
        Returns:
            List of search results ordered by similarity
        """
        pass
    
    @abstractmethod
    async def batch_search(
        self,
        query_vectors: list[list[float]],
        top_k: int = 5,
        filter: Optional[dict[str, Any]] = None
    ) -> list[list[SearchResult]]:
        """
        Search for similar vectors in batch.
        
        Args:
            query_vectors: List of query embedding vectors
            top_k: Number of results to return per query
            filter: Optional metadata filter
            
        Returns:
            List of search result lists (one per query)
        """
        pass
    
    @abstractmethod
    async def delete(
        self,
        filter: dict[str, Any]
    ) -> int:
        """
        Delete vectors matching filter.
        
        Args:
            filter: Metadata filter for deletion
            
        Returns:
            Number of vectors deleted
        """
        pass
    
    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with stats (total_vectors, index_size, etc.)
        """
        pass

class PineconeDB(VectorDB):
    """Pinecone vector database adapter."""
    
    def __init__(self, config: dict[str, Any]):
        """
        Initialize Pinecone adapter.
        
        Args:
            config: Pinecone configuration dictionary
        """
        self.config = config
        self.api_key = config.get('api_key')
        self.environment = config.get('environment')
        self.index_name = config.get('index_name')
        self.dimension = config.get('dimension', 1536)
        self.metric = config.get('metric', 'cosine')
        
        self._index = None
        self._client = None
        
        logger.info("pinecone_adapter_initialized",
                   index_name=self.index_name,
                   dimension=self.dimension,
                   metric=self.metric)
    
    async def _ensure_connection(self):
        """Ensure Pinecone connection is established."""
        if self._client is None:
            try:
                import pinecone
                
                # Initialize Pinecone
                pinecone.init(
                    api_key=self.api_key,
                    environment=self.environment
                )
                
                self._client = pinecone
                
                # Check if index exists, create if not
                if self.index_name not in pinecone.list_indexes():
                    logger.info("creating_pinecone_index", index_name=self.index_name)
                    pinecone.create_index(
                        name=self.index_name,
                        dimension=self.dimension,
                        metric=self.metric,
                        pod_type=self.config.get('pinecone', {}).get('pod_type', 'p1.x1'),
                        replicas=self.config.get('pinecone', {}).get('replicas', 1),
                        shards=self.config.get('pinecone', {}).get('shards', 1)
                    )
                
                # Get index
                self._index = pinecone.Index(self.index_name)
                
                logger.info("pinecone_connection_established", index_name=self.index_name)
                
            except ImportError:
                logger.error("pinecone_not_installed",
                           message="Please install pinecone-client: pip install pinecone-client")
                raise
            except Exception as e:
                logger.error("pinecone_connection_failed", error=str(e))
                raise
    
    async def insert(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
        ids: Optional[list[str]] = None
    ) -> list[str]:
        """
        Insert vectors with metadata into Pinecone.
        
        Batch inserts up to 100 vectors at a time for optimal performance.
        
        Validates: Requirement 40.8
        """
        await self._ensure_connection()
        
        try:
            import uuid
            
            # Generate IDs if not provided
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # Prepare upsert data
            upsert_data = [
                (id_, vector, meta)
                for id_, vector, meta in zip(ids, vectors, metadata)
            ]
            
            # Batch upsert (100 vectors per batch as per requirement)
            batch_size = 100
            for i in range(0, len(upsert_data), batch_size):
                batch = upsert_data[i:i + batch_size]
                self._index.upsert(vectors=batch)
                logger.debug("batch_inserted",
                           batch_number=i // batch_size + 1,
                           batch_size=len(batch))
            
            logger.info("vectors_inserted",
                       count=len(ids),
                       batches=len(range(0, len(upsert_data), batch_size)),
                       index_name=self.index_name)
            
            return ids
            
        except Exception as e:
            logger.error("vector_insertion_failed", error=str(e))
            raise
    
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter: Optional[dict[str, Any]] = None
    ) -> list[SearchResult]:
        """Search for similar vectors in Pinecone."""
        await self._ensure_connection()
        
        try:
            # Perform search
            results = self._index.query(
                vector=query_vector,
                top_k=top_k,
                filter=filter,
                include_metadata=True
            )
            
            # Convert to SearchResult objects
            search_results = [
                SearchResult(
                    id=match['id'],
                    score=match['score'],
                    metadata=match.get('metadata', {})
                )
                for match in results.get('matches', [])
            ]
            
            logger.info("vector_search_completed",
                       query_top_k=top_k,
                       results_count=len(search_results),
                       index_name=self.index_name)
            
            return search_results
            
        except Exception as e:
            logger.error("vector_search_failed", error=str(e))
            raise
    
    async def batch_search(
        self,
        query_vectors: list[list[float]],
        top_k: int = 5,
        filter: Optional[dict[str, Any]] = None
    ) -> list[list[SearchResult]]:
        """
        Search for similar vectors in batch (up to 10 queries at once).
        
        Args:
            query_vectors: List of query embedding vectors (max 10)
            top_k: Number of results to return per query
            filter: Optional metadata filter
            
        Returns:
            List of search result lists (one per query)
            
        Validates: Requirement 40.8
        """
        await self._ensure_connection()
        
        try:
            # Limit batch size to 10 as per requirement
            if len(query_vectors) > 10:
                logger.warning("batch_search_size_exceeded",
                             requested=len(query_vectors),
                             max_allowed=10)
                query_vectors = query_vectors[:10]
            
            # Perform batch search using asyncio.gather for parallel execution
            import asyncio
            
            search_tasks = [
                self.search(query_vector, top_k, filter)
                for query_vector in query_vectors
            ]
            
            results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Handle any exceptions in individual searches
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error("batch_search_query_failed",
                               query_index=i,
                               error=str(result))
                    final_results.append([])  # Empty result for failed query
                else:
                    final_results.append(result)
            
            logger.info("batch_search_completed",
                       query_count=len(query_vectors),
                       top_k=top_k,
                       index_name=self.index_name)
            
            return final_results
            
        except Exception as e:
            logger.error("batch_search_failed", error=str(e))
            raise
    
    async def delete(
        self,
        filter: dict[str, Any]
    ) -> int:
        """Delete vectors matching filter from Pinecone."""
        await self._ensure_connection()
        
        try:
            # Pinecone delete by filter
            response = self._index.delete(filter=filter)
            
            # Note: Pinecone doesn't return count, so we estimate
            deleted_count = response.get('deleted_count', 0) if isinstance(response, dict) else 0
            
            logger.info("vectors_deleted",
                       filter=filter,
                       estimated_count=deleted_count,
                       index_name=self.index_name)
            
            return deleted_count
            
        except Exception as e:
            logger.error("vector_deletion_failed", error=str(e))
            raise
    
    async def get_stats(self) -> dict[str, Any]:
        """Get Pinecone index statistics."""
        await self._ensure_connection()
        
        try:
            stats = self._index.describe_index_stats()
            
            return {
                'total_vectors': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', self.dimension),
                'index_fullness': stats.get('index_fullness', 0.0),
                'namespaces': stats.get('namespaces', {}),
                'index_name': self.index_name
            }
            
        except Exception as e:
            logger.error("stats_retrieval_failed", error=str(e))
            return {
                'total_vectors': 0,
                'dimension': self.dimension,
                'index_name': self.index_name,
                'error': str(e)
            }

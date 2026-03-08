"""
Embedding Service Module - Generate text embeddings for vector storage.

This module provides:
- OpenAI embedding generation
- Batch embedding support
- Caching for efficiency
"""

from typing import Any
import hashlib
from system_core.config import get_logger

logger = get_logger(__name__)

class EmbeddingService:
    """Service for generating text embeddings using OpenAI."""
    
    def __init__(self, config: dict[str, Any], redis_client=None):
        """
        Initialize Embedding Service.
        
        Args:
            config: Embedding configuration dictionary
            redis_client: Optional Redis client for caching
        """
        self.config = config
        self.provider = config.get('provider', 'openai')
        self.model = config.get('model', 'text-embedding-3-small')
        self.batch_size = config.get('batch_size', 100)
        self.timeout = config.get('timeout', 30)
        self.redis_client = redis_client
        
        self._client = None
        
        logger.info("embedding_service_initialized",
                   provider=self.provider,
                   model=self.model,
                   batch_size=self.batch_size)
    
    def _ensure_client(self):
        """Ensure OpenAI client is initialized."""
        if self._client is None:
            try:
                import openai
                import os
                
                # Get API key from environment
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable not set")
                
                openai.api_key = api_key
                self._client = openai
                
                logger.info("openai_client_initialized")
                
            except ImportError:
                logger.error("openai_not_installed",
                           message="Please install openai: pip install openai")
                raise
            except Exception as e:
                logger.error("openai_client_initialization_failed", error=str(e))
                raise
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        return f"embedding:{self.model}:{text_hash}"
    
    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
        """
        # Check cache first
        if self.redis_client:
            cache_key = self._get_cache_key(text)
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    import json
                    logger.debug("embedding_cache_hit", text_length=len(text))
                    return json.loads(cached)
            except Exception as e:
                logger.warning("cache_read_failed", error=str(e))
        
        # Generate embedding
        self._ensure_client()
        
        try:
            response = self._client.Embedding.create(
                model=self.model,
                input=text
            )
            
            embedding = response['data'][0]['embedding']
            
            # Cache the result
            if self.redis_client:
                try:
                    import json
                    self.redis_client.setex(
                        cache_key,
                        3600,  # 1 hour TTL
                        json.dumps(embedding)
                    )
                except Exception as e:
                    logger.warning("cache_write_failed", error=str(e))
            
            logger.info("embedding_generated",
                       text_length=len(text),
                       embedding_dimension=len(embedding),
                       model=self.model)
            
            return embedding
            
        except Exception as e:
            logger.error("embedding_generation_failed",
                        text_length=len(text),
                        error=str(e))
            raise
    
    async def batch_generate(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        self._ensure_client()
        
        embeddings = []
        
        try:
            # Process in batches
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                
                # Check cache for each text
                batch_embeddings = []
                texts_to_generate = []
                text_indices = []
                
                for idx, text in enumerate(batch):
                    if self.redis_client:
                        cache_key = self._get_cache_key(text)
                        try:
                            cached = self.redis_client.get(cache_key)
                            if cached:
                                import json
                                batch_embeddings.append((idx, json.loads(cached)))
                                continue
                        except Exception as e:
                            logger.warning("cache_read_failed", error=str(e))
                    
                    texts_to_generate.append(text)
                    text_indices.append(idx)
                
                # Generate embeddings for uncached texts
                if texts_to_generate:
                    response = self._client.Embedding.create(
                        model=self.model,
                        input=texts_to_generate
                    )
                    
                    for idx, data in enumerate(response['data']):
                        embedding = data['embedding']
                        original_idx = text_indices[idx]
                        batch_embeddings.append((original_idx, embedding))
                        
                        # Cache the result
                        if self.redis_client:
                            try:
                                import json
                                cache_key = self._get_cache_key(texts_to_generate[idx])
                                self.redis_client.setex(
                                    cache_key,
                                    3600,
                                    json.dumps(embedding)
                                )
                            except Exception as e:
                                logger.warning("cache_write_failed", error=str(e))
                
                # Sort by original index and extract embeddings
                batch_embeddings.sort(key=lambda x: x[0])
                embeddings.extend([emb for _, emb in batch_embeddings])
                
                logger.info("batch_embeddings_generated",
                           batch_size=len(batch),
                           cached_count=len(batch) - len(texts_to_generate),
                           generated_count=len(texts_to_generate))
            
            logger.info("all_embeddings_generated",
                       total_texts=len(texts),
                       total_embeddings=len(embeddings))
            
            return embeddings
            
        except Exception as e:
            logger.error("batch_embedding_generation_failed",
                        total_texts=len(texts),
                        error=str(e))
            raise

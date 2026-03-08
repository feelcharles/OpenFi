"""
LLM Client with Multi-Provider Support

Provides unified interface for calling multiple LLM providers with:
- Automatic fallback chain
- Rate limiting with token bucket algorithm
- Response caching in Redis
- Cross-validation mode
- Per-provider metrics tracking

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8
"""

import asyncio
import hashlib
import time
from typing import Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
import redis.asyncio as redis
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from system_core.config import get_logger
from system_core.config.llm_manager import get_llm_manager
from system_core.config.llm_statistics import get_usage_statistics

logger = get_logger(__name__)

class LLMResponse(BaseModel):
    """LLM response format."""
    
    provider: str = Field(description="Provider name")
    model: str = Field(description="Model name")
    content: str = Field(description="Response content")
    prompt_tokens: int = Field(default=0, description="Prompt tokens used")
    completion_tokens: int = Field(default=0, description="Completion tokens used")
    total_tokens: int = Field(default=0, description="Total tokens used")
    latency_ms: int = Field(description="Response latency in milliseconds")
    cached: bool = Field(default=False, description="Whether response was cached")

class TokenBucket:
    """
    Token bucket algorithm for rate limiting.
    
    Validates: Requirement 5.5
    """
    
    def __init__(self, rate: int, capacity: int):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens added per minute
            capacity: Maximum bucket capacity
        """
        self.rate = rate  # tokens per minute
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False if rate limit exceeded
        """
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(
                self.capacity,
                self.tokens + (elapsed / 60.0) * self.rate
            )
            self.last_update = now
            
            # Check if enough tokens available
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

class LLMClient:
    """
    Multi-provider LLM client with fallback and caching.
    
    Features:
    - Support for OpenAI, Anthropic, and local models
    - Automatic fallback chain on provider failure
    - Rate limiting per provider
    - Response caching in Redis
    - Optional cross-validation mode
    - Per-provider metrics tracking
    
    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8
    """
    
    def __init__(
        self,
        config_path: str = "config/llm_config.yaml",
        redis_url: str = "redis://localhost:6379"
    ):
        """
        Initialize LLM client.
        
        Args:
            config_path: Path to LLM configuration file
            redis_url: Redis connection URL for caching
            
        Validates: Requirement 5.1, 9.1
        """
        self.config_path = Path(config_path)
        self.redis_url = redis_url
        self.logger = logger
        
        # Get LLM Manager instance for model selection
        self.llm_manager = get_llm_manager()
        self.statistics = get_usage_statistics()
        
        # Provider clients
        self.providers: dict[str, Any] = {}
        self.rate_limiters: dict[str, TokenBucket] = {}
        
        # Configuration
        self.config: dict[str, Any] = {}
        self.primary_provider: str = ""
        self.fallback_chain: list[str] = []
        
        # Metrics
        self.metrics: dict[str, dict[str, Any]] = {}
        
        # Redis client for caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Load configuration
        self.load_config()
        self._initialize_providers()
    
    def load_config(self) -> None:
        """
        Load LLM configuration from file.
        
        Validates: Requirement 5.1
        """
        try:
            if not self.config_path.exists():
                self.logger.error(f"LLM config not found: {self.config_path}")
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            self.primary_provider = self.config.get('primary_provider', 'openai')
            self.fallback_chain = self.config.get('fallback_chain', [])
            
            self.logger.info(
                f"Loaded LLM config: primary={self.primary_provider}, "
                f"fallback={self.fallback_chain}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load LLM config: {e}", exc_info=True)
    
    def _initialize_providers(self) -> None:
        """
        Initialize LLM provider clients and rate limiters.
        
        Validates: Requirements 5.2, 5.3, 5.5
        """
        providers_config = self.config.get('providers', {})
        
        # Initialize OpenAI
        if 'openai' in providers_config:
            openai_config = providers_config['openai']
            api_key = openai_config.get('api_key', '').replace('${OPENAI_API_KEY}', '')
            if api_key:
                self.providers['openai'] = AsyncOpenAI(api_key=api_key)
                
                # Initialize rate limiter
                rate_limit = openai_config.get('rate_limit', {})
                self.rate_limiters['openai'] = TokenBucket(
                    rate=rate_limit.get('requests_per_minute', 60),
                    capacity=rate_limit.get('requests_per_minute', 60)
                )
                
                # Initialize metrics
                self.metrics['openai'] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0,
                    'total_latency_ms': 0,
                    'total_tokens': 0
                }
                
                self.logger.info("Initialized OpenAI provider")
        
        # Initialize Anthropic
        if 'anthropic' in providers_config:
            anthropic_config = providers_config['anthropic']
            api_key = anthropic_config.get('api_key', '').replace('${ANTHROPIC_API_KEY}', '')
            if api_key:
                self.providers['anthropic'] = AsyncAnthropic(api_key=api_key)
                
                # Initialize rate limiter
                rate_limit = anthropic_config.get('rate_limit', {})
                self.rate_limiters['anthropic'] = TokenBucket(
                    rate=rate_limit.get('requests_per_minute', 50),
                    capacity=rate_limit.get('requests_per_minute', 50)
                )
                
                # Initialize metrics
                self.metrics['anthropic'] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0,
                    'total_latency_ms': 0,
                    'total_tokens': 0
                }
                
                self.logger.info("Initialized Anthropic provider")
        
        # Initialize local provider (Ollama)
        if 'local' in providers_config:
            local_config = providers_config['local']
            base_url = local_config.get('base_url', '').replace('${LOCAL_LLM_URL}', '')
            if base_url:
                # Use OpenAI client with custom base URL for Ollama compatibility
                self.providers['local'] = AsyncOpenAI(
                    base_url=base_url,
                    api_key='ollama'  # Ollama doesn't require real API key
                )
                
                # Initialize rate limiter
                rate_limit = local_config.get('rate_limit', {})
                self.rate_limiters['local'] = TokenBucket(
                    rate=rate_limit.get('requests_per_minute', 100),
                    capacity=rate_limit.get('requests_per_minute', 100)
                )
                
                # Initialize metrics
                self.metrics['local'] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0,
                    'total_latency_ms': 0,
                    'total_tokens': 0
                }
                
                self.logger.info("Initialized local LLM provider")
    
    async def _get_redis_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(self.redis_url)
        return self.redis_client
    
    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        task_type: Optional[str] = None
    ) -> LLMResponse:
        """
        Call LLM with automatic fallback chain and model selection.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            model: Specific model to use (optional, uses LLM Manager selection if not specified)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            task_type: Task type for auto-selection (optional)
            
        Returns:
            LLMResponse with content and metadata
            
        Validates: Requirements 5.4, 5.7, 9.1, 9.2, 9.3, 9.4
        """
        # Get model from LLM Manager if not specified
        if not model:
            # Use LLM Manager to select model
            if self.llm_manager.is_auto_mode_enabled():
                # Auto-select based on task type and input length
                selected_model_config = self.llm_manager.select_model_for_task(
                    task_type=task_type,
                    input_length=len(prompt)
                )
                self.logger.info(
                    f"Auto-selected model: {selected_model_config.display_name} "
                    f"(task: {task_type}, length: {len(prompt)})"
                )
            else:
                # Use current model
                selected_model_config = self.llm_manager.current_model
                self.logger.debug(f"Using current model: {selected_model_config.display_name}")
            
            # Extract model name and provider
            model = selected_model_config.name
            provider_name = selected_model_config.provider
            
            # Use model's configured parameters if not overridden
            if temperature == 0.7:  # Default value
                temperature = selected_model_config.temperature
            if max_tokens == 4096:  # Default value
                max_tokens = selected_model_config.max_tokens
        else:
            # Model specified explicitly, find its provider
            provider_name = self._find_provider_for_model(model)
        
        # Check cache first
        cache_key = self._get_cache_key(prompt, system_prompt, temperature)
        cached_response = await self._get_cached_response(cache_key)
        if cached_response:
            return cached_response
        
        # Try to call the selected provider
        try:
            response = await self._call_provider(
                provider_name,
                prompt,
                system_prompt,
                model,
                temperature,
                max_tokens
            )
            
            # Cache successful response
            await self._cache_response(cache_key, response)
            
            # Record usage statistics
            self._record_usage(model, response)
            
            return response
            
        except Exception as e:
            self.logger.error(
                f"Failed to call provider {provider_name} with model {model}: {e}",
                exc_info=True
            )
            # Don't auto-switch models on failure (Validates: Requirement 9.5)
            raise
    
    def _find_provider_for_model(self, model_name: str) -> str:
        """
        Find the provider for a given model name.
        
        Args:
            model_name: Model name to search for
            
        Returns:
            Provider name
            
        Raises:
            ValueError: If model not found in any provider
        """
        for provider_name, provider_config in self.config.get('providers', {}).items():
            models = provider_config.get('models', [])
            for model_data in models:
                if model_data.get('name') == model_name:
                    return provider_name
        
        # Fallback to primary provider
        self.logger.warning(f"Model {model_name} not found, using primary provider")
        return self.primary_provider
    
    def _record_usage(self, model_name: str, response: LLMResponse):
        """
        Record usage statistics for the model.
        
        Args:
            model_name: Model name
            response: LLM response with token usage
            
        Validates: Requirement 10.4
        """
        try:
            # Calculate cost based on model configuration
            model_config = None
            for model in self.llm_manager.get_all_models():
                if model.name == model_name:
                    model_config = model
                    break
            
            if model_config:
                cost = (response.total_tokens / 1000.0) * model_config.cost_per_1k_tokens
                self.statistics.record_request(
                    model_name=model_name,
                    tokens_used=response.total_tokens,
                    cost=cost
                )
                self.logger.debug(
                    f"Recorded usage: {model_name}, {response.total_tokens} tokens, ${cost:.4f}"
                )
        except Exception as e:
            self.logger.warning(f"Failed to record usage statistics: {e}")
    
    async def _call_provider(
        self,
        provider_name: str,
        prompt: str,
        system_prompt: Optional[str],
        model: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """
        Call specific LLM provider.
        
        Validates: Requirements 5.2, 5.3, 5.5, 5.8
        """
        # Check rate limit
        rate_limiter = self.rate_limiters.get(provider_name)
        if rate_limiter:
            if not await rate_limiter.acquire():
                raise Exception(f"Rate limit exceeded for {provider_name}")
        
        # Get provider client
        client = self.providers[provider_name]
        provider_config = self.config['providers'][provider_name]
        
        # Get model name
        if not model:
            models = provider_config.get('models', [])
            if models:
                model = models[0]['name']
            else:
                raise Exception(f"No models configured for {provider_name}")
        
        # Get timeout
        timeout = provider_config.get('timeout', 30)
        
        # Track metrics
        start_time = time.time()
        self.metrics[provider_name]['total_calls'] += 1
        
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Call provider
            if provider_name == 'anthropic':
                # Anthropic uses different API
                response = await asyncio.wait_for(
                    client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        messages=messages
                    ),
                    timeout=timeout
                )
                
                content = response.content[0].text
                prompt_tokens = response.usage.input_tokens
                completion_tokens = response.usage.output_tokens
                
            else:
                # OpenAI and Ollama use same API
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    ),
                    timeout=timeout
                )
                
                content = response.choices[0].message.content
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
            
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Update metrics
            self.metrics[provider_name]['successful_calls'] += 1
            self.metrics[provider_name]['total_latency_ms'] += latency_ms
            self.metrics[provider_name]['total_tokens'] += prompt_tokens + completion_tokens
            
            return LLMResponse(
                provider=provider_name,
                model=model,
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
                cached=False
            )
            
        except Exception as e:
            self.metrics[provider_name]['failed_calls'] += 1
            raise e
    
    def _get_cache_key(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float
    ) -> str:
        """
        Generate cache key from prompt parameters.
        
        Validates: Requirement 5.7
        """
        # Combine prompt components
        cache_input = f"{system_prompt or ''}|{prompt}|{temperature}"
        
        # Generate hash
        return f"llm_cache:{hashlib.sha256(cache_input.encode()).hexdigest()}"
    
    async def _get_cached_response(self, cache_key: str) -> Optional[LLMResponse]:
        """
        Get cached LLM response from Redis.
        
        Validates: Requirement 5.7
        """
        try:
            redis_client = await self._get_redis_client()
            cached_data = await redis_client.get(cache_key)
            
            if cached_data:
                import json
                data = json.loads(cached_data)
                response = LLMResponse(**data)
                response.cached = True
                
                self.logger.debug(f"Cache hit for key: {cache_key}")
                return response
                
        except Exception as e:
            self.logger.warning(f"Failed to get cached response: {e}")
        
        return None
    
    async def _cache_response(self, cache_key: str, response: LLMResponse) -> None:
        """
        Cache LLM response in Redis.
        
        Validates: Requirement 5.7
        """
        try:
            redis_client = await self._get_redis_client()
            
            # Serialize response
            import json
            data = response.model_dump()
            
            # Cache with TTL of 3600 seconds (1 hour)
            await redis_client.setex(
                cache_key,
                3600,
                json.dumps(data)
            )
            
            self.logger.debug(f"Cached response for key: {cache_key}")
            
        except Exception as e:
            self.logger.warning(f"Failed to cache response: {e}")
    
    def get_metrics(self, provider: Optional[str] = None) -> dict[str, Any]:
        """
        Get metrics for provider(s).
        
        Args:
            provider: Specific provider name, or None for all providers
            
        Returns:
            Metrics dictionary
            
        Validates: Requirement 5.8
        """
        if provider:
            metrics = self.metrics.get(provider, {})
            # Calculate average latency
            if metrics.get('successful_calls', 0) > 0:
                metrics['avg_latency_ms'] = (
                    metrics['total_latency_ms'] / metrics['successful_calls']
                )
            return metrics
        else:
            # Return all metrics
            all_metrics = {}
            for provider_name, metrics in self.metrics.items():
                provider_metrics = metrics.copy()
                if provider_metrics.get('successful_calls', 0) > 0:
                    provider_metrics['avg_latency_ms'] = (
                        provider_metrics['total_latency_ms'] / 
                        provider_metrics['successful_calls']
                    )
                all_metrics[provider_name] = provider_metrics
            return all_metrics
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()

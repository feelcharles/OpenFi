"""
Config Manager - Agent配置管理器

负责Agent配置的持久化、缓存、验证、版本控制和导入导出。

Features:
- Database persistence with versioning
- Redis caching (TTL 5 minutes)
- Configuration validation with detailed error messages
- Version control and rollback
- Import/Export (JSON/YAML)
- Hot reload support

Validates: Requirements 8.1-8.10, 17.1-17.12, 22.1-22.12, 28.1-28.11
"""

import json
import logging
import yaml
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import text

from system_core.database.client import DatabaseClient, get_db_client
from system_core.agent_system.models import AgentConfig
from system_core.config.file_watcher import FileWatcher

logger = logging.getLogger(__name__)

class ValidationResult:
    """Configuration validation result"""
    
    def __init__(self, valid: bool, errors: Optional[list[dict[str, str]]] = None):
        self.valid = valid
        self.errors = errors or []
    
    def __bool__(self) -> bool:
        return self.valid
    
    def __repr__(self) -> str:
        if self.valid:
            return "ValidationResult(valid=True)"
        return f"ValidationResult(valid=False, errors={self.errors})"

class ConfigManager:
    """
    Agent配置管理器
    
    负责Agent配置的完整生命周期管理：
    - 持久化到数据库（带版本控制）
    - Redis缓存（TTL 5分钟）
    - 配置验证（详细错误信息）
    - 版本控制和回滚
    - 导入导出（JSON/YAML）
    
    Validates: Requirements 8.1-8.10, 17.1-17.12, 22.1-22.12, 28.1-28.11
    """
    
    def __init__(
        self,
        db_client: Optional[DatabaseClient] = None,
        cache_ttl: int = 300,  # 5 minutes
        cache_enabled: bool = True,
    ):
        """
        Initialize ConfigManager
        
        Args:
            db_client: Database client instance (uses global if None)
            cache_ttl: Cache TTL in seconds (default: 300)
            cache_enabled: Enable Redis caching (default: True)
            
        Validates: Requirement 8.1
        """
        self.db_client = db_client or get_db_client()
        self.cache_ttl = cache_ttl
        self.cache_enabled = cache_enabled and self.db_client.cache_enabled
        self.cache_key_prefix = "agent_config:"
        
        logger.info(
            f"ConfigManager initialized with cache_enabled={self.cache_enabled}, "
            f"cache_ttl={cache_ttl}s"
        )
    
    def _get_cache_key(self, agent_id: UUID) -> str:
        """Generate cache key for agent configuration"""
        return f"{self.cache_key_prefix}{str(agent_id)}"
    
    async def _invalidate_cache(self, agent_id: UUID) -> None:
        """
        Invalidate cache for agent configuration
        
        Args:
            agent_id: Agent ID
            
        Validates: Requirement 8.2
        """
        if not self.cache_enabled or not self.db_client.redis_client:
            return
        
        try:
            cache_key = self._get_cache_key(agent_id)
            await self.db_client.redis_client.delete(cache_key)
            logger.debug(f"Cache invalidated for agent {agent_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
    
    async def _get_from_cache(self, agent_id: UUID) -> Optional[AgentConfig]:
        """
        Get configuration from cache
        
        Args:
            agent_id: Agent ID
            
        Returns:
            AgentConfig or None if not cached
        """
        if not self.cache_enabled or not self.db_client.redis_client:
            return None
        
        try:
            cache_key = self._get_cache_key(agent_id)
            cached_data = await self.db_client.redis_client.get(cache_key)
            
            if cached_data:
                config_dict = json.loads(cached_data)
                config = AgentConfig(**config_dict)
                logger.debug(f"Cache hit for agent {agent_id}")
                return config
            
            logger.debug(f"Cache miss for agent {agent_id}")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to read from cache: {e}")
            return None
    
    async def _set_in_cache(self, agent_id: UUID, config: AgentConfig) -> None:
        """
        Store configuration in cache
        
        Args:
            agent_id: Agent ID
            config: Agent configuration
        """
        if not self.cache_enabled or not self.db_client.redis_client:
            return
        
        try:
            cache_key = self._get_cache_key(agent_id)
            config_json = config.model_dump_json()
            await self.db_client.redis_client.setex(
                cache_key,
                self.cache_ttl,
                config_json
            )
            logger.debug(f"Configuration cached for agent {agent_id}")
        except Exception as e:
            logger.warning(f"Failed to write to cache: {e}")
    
    async def save_config(
        self,
        agent_id: UUID,
        config: AgentConfig,
        created_by: str,
        change_description: Optional[str] = None,
    ) -> bool:
        """
        Save agent configuration with versioning
        
        Args:
            agent_id: Agent ID
            config: Agent configuration
            created_by: User who created this version
            change_description: Description of changes
            
        Returns:
            True if saved successfully
            
        Validates: Requirements 8.1, 8.2, 8.3, 28.1, 28.2, 28.3
        """
        try:
            # Validate configuration first
            validation_result = await self.validate_config(config)
            if not validation_result.valid:
                logger.error(f"Configuration validation failed: {validation_result.errors}")
                return False
            
            # Get next version number
            query = """
                SELECT COALESCE(MAX(version), 0) + 1 as next_version
                FROM agent_configs
                WHERE agent_id = :agent_id
            """
            result = await self.db_client.execute_with_retry(
                query,
                {"agent_id": str(agent_id)},
                fetch_one=True,
                use_cache=False,
            )
            next_version = result["next_version"] if result else 1
            
            # Save configuration to database
            config_json = config.model_dump_json()
            insert_query = """
                INSERT INTO agent_configs (
                    agent_id, version, config_json, created_by, change_description
                )
                VALUES (
                    :agent_id, :version, :config_json, :created_by, :change_description
                )
            """
            await self.db_client.execute_with_retry(
                insert_query,
                {
                    "agent_id": str(agent_id),
                    "version": next_version,
                    "config_json": config_json,
                    "created_by": created_by,
                    "change_description": change_description or f"Version {next_version}",
                },
                use_cache=False,
            )
            
            # Update cache
            await self._set_in_cache(agent_id, config)
            
            logger.info(
                f"Configuration saved for agent {agent_id}, version {next_version}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}", exc_info=True)
            return False
    
    async def load_config(self, agent_id: UUID) -> Optional[AgentConfig]:
        """
        Load agent configuration (cache-first)
        
        Args:
            agent_id: Agent ID
            
        Returns:
            AgentConfig or None if not found
            
        Validates: Requirements 8.1, 8.2
        """
        try:
            # Try cache first
            cached_config = await self._get_from_cache(agent_id)
            if cached_config:
                return cached_config
            
            # Load from database
            query = """
                SELECT config_json
                FROM agent_configs
                WHERE agent_id = :agent_id
                ORDER BY version DESC
                LIMIT 1
            """
            result = await self.db_client.execute_with_retry(
                query,
                {"agent_id": str(agent_id)},
                fetch_one=True,
                use_cache=False,
            )
            
            if not result:
                logger.warning(f"No configuration found for agent {agent_id}")
                return None
            
            # Parse and cache
            config = AgentConfig(**json.loads(result["config_json"]))
            await self._set_in_cache(agent_id, config)
            
            logger.debug(f"Configuration loaded for agent {agent_id}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}", exc_info=True)
            return None
    
    async def validate_config(self, config: AgentConfig) -> ValidationResult:
        """
        Validate agent configuration
        
        Args:
            config: Agent configuration to validate
            
        Returns:
            ValidationResult with detailed errors
            
        Validates: Requirements 17.1-17.12
        """
        errors = []
        
        try:
            # Pydantic validation (automatic)
            config.model_validate(config.model_dump())
            
            # Additional business logic validation
            
            # Validate asset portfolio
            if config.asset_portfolio.assets:
                total_weight = sum(asset.weight for asset in config.asset_portfolio.assets)
                if total_weight > 1.0:
                    errors.append({
                        "field": "asset_portfolio.assets",
                        "error": f"Total asset weight {total_weight:.4f} exceeds 1.0",
                        "code": "WEIGHT_EXCEEDS_LIMIT"
                    })
                
                # Check for duplicate symbols
                symbols = [asset.symbol for asset in config.asset_portfolio.assets]
                duplicates = [s for s in symbols if symbols.count(s) > 1]
                if duplicates:
                    errors.append({
                        "field": "asset_portfolio.assets",
                        "error": f"Duplicate symbols found: {', '.join(set(duplicates))}",
                        "code": "DUPLICATE_SYMBOLS"
                    })
            
            # Validate bot connections limit
            if len(config.bot_connections) > 5:
                errors.append({
                    "field": "bot_connections",
                    "error": f"Too many bot connections: {len(config.bot_connections)} (max: 5)",
                    "code": "TOO_MANY_BOT_CONNECTIONS"
                })
            
            # Validate quotas
            if config.quotas.max_api_calls_per_hour < 0:
                errors.append({
                    "field": "quotas.max_api_calls_per_hour",
                    "error": "Must be non-negative",
                    "code": "INVALID_QUOTA"
                })
            
            if config.quotas.max_concurrent_operations < 1:
                errors.append({
                    "field": "quotas.max_concurrent_operations",
                    "error": "Must be at least 1",
                    "code": "INVALID_QUOTA"
                })
            
            # Validate push frequency limits
            if config.push_config.frequency_limits.max_pushes_per_hour < 0:
                errors.append({
                    "field": "push_config.frequency_limits.max_pushes_per_hour",
                    "error": "Must be non-negative",
                    "code": "INVALID_FREQUENCY_LIMIT"
                })
            
            if errors:
                logger.warning(f"Configuration validation failed with {len(errors)} errors")
                return ValidationResult(valid=False, errors=errors)
            
            logger.debug("Configuration validation passed")
            return ValidationResult(valid=True)
            
        except ValidationError as e:
            # Convert Pydantic validation errors to our format
            for error in e.errors():
                field_path = ".".join(str(loc) for loc in error["loc"])
                errors.append({
                    "field": field_path,
                    "error": error["msg"],
                    "code": error["type"].upper()
                })
            
            logger.warning(f"Configuration validation failed: {errors}")
            return ValidationResult(valid=False, errors=errors)
        
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            errors.append({
                "field": "unknown",
                "error": str(e),
                "code": "VALIDATION_ERROR"
            })
            return ValidationResult(valid=False, errors=errors)
    
    async def get_config_version(
        self,
        agent_id: UUID,
        version: int
    ) -> Optional[AgentConfig]:
        """
        Get specific configuration version
        
        Args:
            agent_id: Agent ID
            version: Version number
            
        Returns:
            AgentConfig or None if not found
            
        Validates: Requirements 28.4, 28.5
        """
        try:
            query = """
                SELECT config_json
                FROM agent_configs
                WHERE agent_id = :agent_id AND version = :version
            """
            result = await self.db_client.execute_with_retry(
                query,
                {"agent_id": str(agent_id), "version": version},
                fetch_one=True,
                use_cache=True,
            )
            
            if not result:
                logger.warning(
                    f"Configuration version {version} not found for agent {agent_id}"
                )
                return None
            
            config = AgentConfig(**json.loads(result["config_json"]))
            logger.debug(f"Loaded configuration version {version} for agent {agent_id}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to get configuration version: {e}", exc_info=True)
            return None
    
    async def rollback_config(
        self,
        agent_id: UUID,
        version: int,
        created_by: str,
    ) -> bool:
        """
        Rollback configuration to a previous version
        
        Args:
            agent_id: Agent ID
            version: Version number to rollback to
            created_by: User performing the rollback
            
        Returns:
            True if rollback successful
            
        Validates: Requirements 8.9, 28.6, 28.7
        """
        try:
            # Get the target version
            target_config = await self.get_config_version(agent_id, version)
            if not target_config:
                logger.error(f"Cannot rollback: version {version} not found")
                return False
            
            # Save as new version (rollback creates a new version)
            success = await self.save_config(
                agent_id=agent_id,
                config=target_config,
                created_by=created_by,
                change_description=f"Rollback to version {version}",
            )
            
            if success:
                logger.info(
                    f"Configuration rolled back to version {version} for agent {agent_id}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to rollback configuration: {e}", exc_info=True)
            return False
    
    async def export_config(
        self,
        agent_id: UUID,
        format: str = "yaml",
        include_metadata: bool = True,
        sanitize_credentials: bool = True,
    ) -> Optional[str]:
        """
        Export agent configuration
        
        Args:
            agent_id: Agent ID
            format: Export format ("json" or "yaml")
            include_metadata: Include metadata (timestamps, version)
            sanitize_credentials: Remove sensitive credentials
            
        Returns:
            Exported configuration string or None
            
        Validates: Requirements 22.1, 22.2, 22.10
        """
        try:
            # Load current configuration
            config = await self.load_config(agent_id)
            if not config:
                logger.error(f"Cannot export: configuration not found for agent {agent_id}")
                return None
            
            # Convert to dict
            config_dict = config.model_dump(mode='json')  # Use mode='json' to convert Enums to strings
            
            # Sanitize credentials if requested
            if sanitize_credentials:
                for bot_conn in config_dict.get("bot_connections", []):
                    bot_conn["credentials_encrypted"] = "***REDACTED***"
            
            # Add metadata if requested
            if include_metadata:
                query = """
                    SELECT version, created_at, created_by, change_description
                    FROM agent_configs
                    WHERE agent_id = :agent_id
                    ORDER BY version DESC
                    LIMIT 1
                """
                result = await self.db_client.execute_with_retry(
                    query,
                    {"agent_id": str(agent_id)},
                    fetch_one=True,
                    use_cache=False,
                )
                
                if result:
                    export_data = {
                        "metadata": {
                            "agent_id": str(agent_id),
                            "version": result["version"],
                            "exported_at": datetime.utcnow().isoformat(),
                            "created_at": result["created_at"].isoformat() if result["created_at"] else None,
                            "created_by": result["created_by"],
                            "change_description": result["change_description"],
                        },
                        "config": config_dict,
                    }
                else:
                    export_data = {"config": config_dict}
            else:
                export_data = config_dict
            
            # Format output
            if format.lower() == "json":
                output = json.dumps(export_data, indent=2, default=str)
            elif format.lower() == "yaml":
                # Use safe_dump to avoid Python-specific tags
                output = yaml.safe_dump(export_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
            else:
                logger.error(f"Unsupported export format: {format}")
                return None
            
            logger.info(f"Configuration exported for agent {agent_id} in {format} format")
            return output
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}", exc_info=True)
            return None
    
    async def import_config(
        self,
        config_data: str,
        format: str = "yaml",
        agent_id: Optional[UUID] = None,
        conflict_resolution: str = "skip",
        created_by: str = "system",
    ) -> tuple[bool, Optional[UUID], Optional[str]]:
        """
        Import agent configuration
        
        Args:
            config_data: Configuration data string
            format: Import format ("json" or "yaml")
            agent_id: Target agent ID (if None, uses ID from data or creates new)
            conflict_resolution: How to handle conflicts ("skip", "overwrite", "create_new")
            created_by: User performing the import
            
        Returns:
            Tuple of (success, agent_id, error_message)
            
        Validates: Requirements 22.6, 22.7, 22.8, 22.9
        """
        try:
            # Parse input data
            if format.lower() == "json":
                data = json.loads(config_data)
            elif format.lower() == "yaml":
                data = yaml.safe_load(config_data)
            else:
                return False, None, f"Unsupported import format: {format}"
            
            # Extract configuration
            if "config" in data:
                # Has metadata wrapper
                config_dict = data["config"]
                metadata = data.get("metadata", {})
                source_agent_id = metadata.get("agent_id")
            else:
                # Direct configuration
                config_dict = data
                source_agent_id = None
            
            # Validate configuration
            try:
                config = AgentConfig(**config_dict)
            except ValidationError as e:
                error_msg = f"Invalid configuration: {e}"
                logger.error(error_msg)
                return False, None, error_msg
            
            validation_result = await self.validate_config(config)
            if not validation_result.valid:
                error_msg = f"Configuration validation failed: {validation_result.errors}"
                logger.error(error_msg)
                return False, None, error_msg
            
            # Determine target agent ID
            target_agent_id = agent_id or (UUID(source_agent_id) if source_agent_id else None)
            
            if not target_agent_id:
                return False, None, "No agent ID specified and none found in import data"
            
            # Check if configuration exists
            existing_config = await self.load_config(target_agent_id)
            
            if existing_config:
                # Handle conflict
                if conflict_resolution == "skip":
                    logger.info(f"Skipping import: configuration exists for agent {target_agent_id}")
                    return False, target_agent_id, "Configuration already exists (skipped)"
                
                elif conflict_resolution == "overwrite":
                    logger.info(f"Overwriting configuration for agent {target_agent_id}")
                    # Continue to save
                
                elif conflict_resolution == "create_new":
                    # This would require creating a new agent, which is beyond config manager scope
                    return False, None, "create_new conflict resolution requires agent creation"
                
                else:
                    return False, None, f"Unknown conflict resolution: {conflict_resolution}"
            
            # Save configuration
            success = await self.save_config(
                agent_id=target_agent_id,
                config=config,
                created_by=created_by,
                change_description="Imported configuration",
            )
            
            if success:
                logger.info(f"Configuration imported for agent {target_agent_id}")
                return True, target_agent_id, None
            else:
                return False, target_agent_id, "Failed to save imported configuration"
            
        except Exception as e:
            error_msg = f"Failed to import configuration: {e}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg
    
    async def list_config_versions(
        self,
        agent_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        List configuration versions for an agent
        
        Args:
            agent_id: Agent ID
            limit: Maximum number of versions to return
            
        Returns:
            List of version metadata
            
        Validates: Requirement 28.4
        """
        try:
            query = """
                SELECT version, created_at, created_by, change_description
                FROM agent_configs
                WHERE agent_id = :agent_id
                ORDER BY version DESC
                LIMIT :limit
            """
            results = await self.db_client.execute_with_retry(
                query,
                {"agent_id": str(agent_id), "limit": limit},
                fetch_all=True,
                use_cache=True,
            )
            
            versions = []
            for row in results or []:
                versions.append({
                    "version": row["version"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "created_by": row["created_by"],
                    "change_description": row["change_description"],
                })
            
            logger.debug(f"Listed {len(versions)} configuration versions for agent {agent_id}")
            return versions
            
        except Exception as e:
            logger.error(f"Failed to list configuration versions: {e}", exc_info=True)
            return []

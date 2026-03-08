"""
Keyword and Asset Configuration Management

This module handles loading and managing keyword and asset configurations
from YAML files.
"""

from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field, validator
import yaml

class Asset(BaseModel):
    """Single asset configuration"""
    symbol: str
    name_zh: str
    name_en: str
    enabled: bool = True
    priority_level: int = 3  # 1=重点关注, 2=定期关注, 3=周报关注
    
    @validator('priority_level')
    def validate_priority_level(cls, v):
        if v not in [1, 2, 3]:
            raise ValueError('priority_level must be 1, 2, or 3')
        return v

class Keyword(BaseModel):
    """Single keyword configuration"""
    keyword_zh: str
    keyword_en: str
    priority: str  # critical, high, medium
    enabled: bool = True
    auto_translate: bool = True
    
    @validator('priority')
    def validate_priority(cls, v):
        valid_priorities = ['critical', 'high', 'medium']
        if v not in valid_priorities:
            raise ValueError(f'Priority must be one of {valid_priorities}')
        return v

class PriorityLevelConfig(BaseModel):
    """Asset priority level configuration"""
    name_zh: str
    name_en: str
    max_count: int
    description: str
    features: list[str] = Field(default_factory=list)

class PriorityConfig(BaseModel):
    """Priority level configuration"""
    name_zh: str
    name_en: str
    weight: int
    description: str
    push_immediately: bool

class TranslationConfig(BaseModel):
    """Translation service configuration"""
    enabled: bool = True
    provider: str = "openai"
    api_config: dict[str, Any] = Field(default_factory=dict)
    cache_enabled: bool = True
    cache_ttl: int = 86400

class AssetsConfig(BaseModel):
    """Assets configuration model"""
    forex: list[Asset] = Field(default_factory=list)
    metals: list[Asset] = Field(default_factory=list)
    energy: list[Asset] = Field(default_factory=list)
    indices: list[Asset] = Field(default_factory=list)
    crypto: list[Asset] = Field(default_factory=list)
    stocks: list[Asset] = Field(default_factory=list)
    priority_levels: dict[str, PriorityLevelConfig] = Field(default_factory=dict)

class KeywordsConfig(BaseModel):
    """Keywords configuration model"""
    policy_data: list[Keyword] = Field(default_factory=list)
    news: list[Keyword] = Field(default_factory=list)
    sentiment_verification: list[Keyword] = Field(default_factory=list)
    opportunity_monitoring: list[Keyword] = Field(default_factory=list)
    priorities: dict[str, PriorityConfig] = Field(default_factory=dict)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)

class ConfigManager:
    """
    Manages both assets and keywords configurations.
    
    Loads from two separate YAML files:
    - config/assets.yaml: Trading instruments (forex, metals, energy, indices, crypto, stocks)
    - config/keywords.yaml: Keyword topics (policy_data, news, sentiment_verification, opportunity_monitoring)
    """
    
    def __init__(
        self,
        assets_path: str = "config/assets.yaml",
        keywords_path: str = "config/keywords.yaml"
    ):
        self.assets_path = Path(assets_path)
        self.keywords_path = Path(keywords_path)
        self.assets_config: Optional[AssetsConfig] = None
        self.keywords_config: Optional[KeywordsConfig] = None
        
    def load_assets(self) -> AssetsConfig:
        """Load assets configuration from YAML file"""
        if not self.assets_path.exists():
            raise FileNotFoundError(f"Assets config file not found: {self.assets_path}")
        
        with open(self.assets_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self.assets_config = AssetsConfig(**data)
        return self.assets_config
    
    def load_keywords(self) -> KeywordsConfig:
        """Load keywords configuration from YAML file"""
        if not self.keywords_path.exists():
            raise FileNotFoundError(f"Keywords config file not found: {self.keywords_path}")
        
        with open(self.keywords_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self.keywords_config = KeywordsConfig(**data)
        return self.keywords_config
    
    def load_all(self) -> tuple[AssetsConfig, KeywordsConfig]:
        """Load both assets and keywords configurations"""
        assets = self.load_assets()
        keywords = self.load_keywords()
        return assets, keywords
    
    def get_enabled_assets(self, category: Optional[str] = None) -> list[Asset]:
        """
        Get all enabled assets, optionally filtered by category.
        
        Args:
            category: Optional category filter (forex, metals, energy, indices, crypto, stocks)
        
        Returns:
            List of enabled assets
        """
        if self.assets_config is None:
            self.load_assets()
        
        all_assets = []
        
        if category:
            category_assets = getattr(self.assets_config, category, [])
            all_assets = [asset for asset in category_assets if asset.enabled]
        else:
            # Get all enabled assets from all categories
            for cat in ['forex', 'metals', 'energy', 'indices', 'crypto', 'stocks']:
                category_assets = getattr(self.assets_config, cat, [])
                all_assets.extend([asset for asset in category_assets if asset.enabled])
        
        return all_assets
    
    def get_assets_by_priority_level(self, priority_level: int) -> list[Asset]:
        """
        Get all enabled assets filtered by priority level.
        
        Args:
            priority_level: Priority level (1=重点关注, 2=定期关注, 3=周报关注)
        
        Returns:
            List of assets with the specified priority level
        """
        all_assets = self.get_enabled_assets()
        return [asset for asset in all_assets if asset.priority_level == priority_level]
    
    def get_priority_level_config(self, level: int) -> Optional[PriorityLevelConfig]:
        """
        Get priority level configuration.
        
        Args:
            level: Priority level (1, 2, or 3)
        
        Returns:
            PriorityLevelConfig if found, None otherwise
        """
        if self.assets_config is None:
            self.load_assets()
        
        level_key = f"level_{level}"
        return self.assets_config.priority_levels.get(level_key)
    
    def get_enabled_keywords(self, category: Optional[str] = None) -> list[Keyword]:
        """
        Get all enabled keywords, optionally filtered by category.
        
        Args:
            category: Optional category filter (policy_data, news, sentiment_verification, opportunity_monitoring)
        
        Returns:
            List of enabled keywords
        """
        if self.keywords_config is None:
            self.load_keywords()
        
        all_keywords = []
        
        if category:
            category_keywords = getattr(self.keywords_config, category, [])
            all_keywords = [kw for kw in category_keywords if kw.enabled]
        else:
            # Get all enabled keywords from all categories
            for cat in ['policy_data', 'news', 'sentiment_verification', 'opportunity_monitoring']:
                category_keywords = getattr(self.keywords_config, cat, [])
                all_keywords.extend([kw for kw in category_keywords if kw.enabled])
        
        return all_keywords
    
    def get_keywords_by_priority(self, priority: str) -> list[Keyword]:
        """
        Get all enabled keywords filtered by priority level.
        
        Args:
            priority: Priority level (critical, high, medium)
        
        Returns:
            List of keywords with the specified priority
        """
        all_keywords = self.get_enabled_keywords()
        return [kw for kw in all_keywords if kw.priority == priority]
    
    def get_asset_by_symbol(self, symbol: str) -> Optional[Asset]:
        """
        Find an asset by its symbol.
        
        Args:
            symbol: Asset symbol (e.g., "EURUSD", "XAUUSD")
        
        Returns:
            Asset if found, None otherwise
        """
        if self.assets_config is None:
            self.load_assets()
        
        for category in ['forex', 'metals', 'energy', 'indices', 'crypto', 'stocks']:
            category_assets = getattr(self.assets_config, category, [])
            for asset in category_assets:
                if asset.symbol == symbol:
                    return asset
        
        return None
    
    def get_search_terms(
        self,
        language: str = "both",
        include_assets: bool = True,
        include_keywords: bool = True
    ) -> list[str]:
        """
        Get all search terms for data fetching.
        
        Args:
            language: Language filter ("zh", "en", "both")
            include_assets: Whether to include asset names
            include_keywords: Whether to include keywords
        
        Returns:
            List of search terms
        """
        terms = []
        
        if include_assets:
            assets = self.get_enabled_assets()
            for asset in assets:
                if language in ["zh", "both"]:
                    terms.append(asset.name_zh)
                if language in ["en", "both"]:
                    terms.append(asset.name_en)
                # Always include symbol
                terms.append(asset.symbol)
        
        if include_keywords:
            keywords = self.get_enabled_keywords()
            for keyword in keywords:
                if language in ["zh", "both"]:
                    terms.append(keyword.keyword_zh)
                if language in ["en", "both"]:
                    terms.append(keyword.keyword_en)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
        
        return unique_terms
    
    def get_priority_config(self, priority: str) -> Optional[PriorityConfig]:
        """
        Get priority configuration.
        
        Args:
            priority: Priority level (critical, high, medium)
        
        Returns:
            PriorityConfig if found, None otherwise
        """
        if self.keywords_config is None:
            self.load_keywords()
        
        return self.keywords_config.priorities.get(priority)
    
    def should_push_immediately(self, priority: str) -> bool:
        """
        Check if a priority level should trigger immediate push.
        
        Args:
            priority: Priority level (critical, high, medium)
        
        Returns:
            True if should push immediately, False otherwise
        """
        priority_config = self.get_priority_config(priority)
        if priority_config:
            return priority_config.push_immediately
        return False
    
    def get_translation_config(self) -> TranslationConfig:
        """Get translation configuration"""
        if self.keywords_config is None:
            self.load_keywords()
        
        return self.keywords_config.translation
    
    def get_all_categories(self) -> list[str]:
        """
        Get all keyword categories.
        
        Returns:
            List of category names
        """
        return ['policy_data', 'news', 'sentiment_verification', 'opportunity_monitoring']
    
    def get_keywords_by_category(self, category: str) -> list[Keyword]:
        """
        Get keywords for a specific category.
        
        Args:
            category: Category name
        
        Returns:
            List of keywords in the category
        """
        return self.get_enabled_keywords(category)

    def get_all_categories(self) -> list[str]:
        """
        Get all keyword categories.

        Returns:
            List of category names
        """
        return ['policy_data', 'news', 'sentiment_verification', 'opportunity_monitoring']

    def get_keywords_by_category(self, category: str) -> list[Keyword]:
        """
        Get keywords for a specific category.

        Args:
            category: Category name

        Returns:
            List of keywords in the category
        """
        return self.get_enabled_keywords(category)

# Global instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager(
    assets_path: str = "config/assets.yaml",
    keywords_path: str = "config/keywords.yaml"
) -> ConfigManager:
    """
    Get or create the global ConfigManager instance.

    Args:
        assets_path: Path to assets configuration file
        keywords_path: Path to keywords configuration file

    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(assets_path, keywords_path)
    return _config_manager

def get_keywords_manager(
    assets_path: str = "config/assets.yaml",
    keywords_path: str = "config/keywords.yaml"
) -> ConfigManager:
    """
    Get or create the global keywords manager instance (alias for get_config_manager).

    Args:
        assets_path: Path to assets configuration file
        keywords_path: Path to keywords configuration file

    Returns:
        ConfigManager instance
    """
    return get_config_manager(assets_path, keywords_path)


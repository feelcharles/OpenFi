"""
Prompt Template Manager

Manages LLM prompt templates with placeholder replacement and conditional sections.
Supports hot reload from config/prompt_templates.yaml.

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

import re
from typing import Any, Optional
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from system_core.config import get_logger

logger = get_logger(__name__)

class PromptTemplate(BaseModel):
    """Prompt template model."""
    
    data_type: str = Field(description="Data type this template applies to")
    template_name: str = Field(description="Template identifier")
    system_prompt: str = Field(description="System prompt for LLM")
    user_prompt_template: str = Field(description="User prompt template with placeholders")
    required_context: list[str] = Field(default_factory=list, description="Required context variables")
    conditional_sections: dict[str, list[str]] = Field(default_factory=dict, description="Conditional section definitions")

class PromptTemplateManager:
    """
    Manages prompt templates with placeholder replacement and conditional sections.
    
    Features:
    - Load templates from YAML configuration
    - Replace {{variable_name}} placeholders
    - Support {{#if condition}}...{{/if}} conditional sections
    - Validate required placeholders
    - Hot reload on configuration changes
    
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
    """
    
    def __init__(self, config_path: str = "config/prompt_templates.yaml"):
        """
        Initialize prompt template manager.
        
        Args:
            config_path: Path to prompt templates configuration file
            
        Validates: Requirement 6.1
        """
        self.config_path = Path(config_path)
        self.templates: dict[str, PromptTemplate] = {}
        self.context_variables: dict[str, dict[str, Any]] = {}
        self.logger = logger
        
        self.load_templates()
    
    def load_templates(self) -> None:
        """
        Load prompt templates from configuration file.
        
        Validates: Requirement 6.1
        """
        try:
            if not self.config_path.exists():
                self.logger.error(f"Template config not found: {self.config_path}")
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Load templates
            templates_data = config.get('templates', [])
            self.templates = {}
            
            for template_data in templates_data:
                template = PromptTemplate(**template_data)
                self.templates[template.data_type] = template
            
            # Load context variable definitions
            self.context_variables = {
                var['name']: var
                for var in config.get('context_variables', [])
            }
            
            self.logger.info(
                f"Loaded {len(self.templates)} prompt templates",
                extra={"data_types": list(self.templates.keys())}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load prompt templates: {e}", exc_info=True)
    
    def reload(self) -> None:
        """
        Reload templates from configuration file.
        
        Validates: Requirement 6.7
        """
        self.logger.info("Reloading prompt templates")
        self.load_templates()
    
    def get_template(self, data_type: str) -> Optional[PromptTemplate]:
        """
        Get template for specific data type.
        
        Args:
            data_type: Data type identifier
            
        Returns:
            PromptTemplate if found, None otherwise
            
        Validates: Requirement 6.1
        """
        template = self.templates.get(data_type)
        if not template:
            self.logger.warning(f"No template found for data_type: {data_type}")
        return template
    
    def render(
        self,
        data_type: str,
        context: dict[str, Any]
    ) -> Optional[dict[str, str]]:
        """
        Render prompt template with context variables.
        
        Args:
            data_type: Data type identifier
            context: Context variables for placeholder replacement
            
        Returns:
            Dict with 'system_prompt' and 'user_prompt' keys, or None if template not found
            
        Validates: Requirements 6.2, 6.4, 6.5, 6.6
        """
        template = self.get_template(data_type)
        if not template:
            return None
        
        # Validate required context variables
        missing = self._validate_required_context(template, context)
        if missing:
            self.logger.error(
                f"Missing required context variables for {data_type}: {missing}",
                extra={"data_type": data_type, "missing": missing}
            )
            return None
        
        try:
            # Process conditional sections first
            user_prompt = self._process_conditional_sections(
                template.user_prompt_template,
                template.conditional_sections,
                context
            )
            
            # Replace placeholders
            system_prompt = self._replace_placeholders(template.system_prompt, context)
            user_prompt = self._replace_placeholders(user_prompt, context)
            
            return {
                'system_prompt': system_prompt,
                'user_prompt': user_prompt
            }
            
        except Exception as e:
            self.logger.error(
                f"Failed to render template for {data_type}: {e}",
                exc_info=True,
                extra={"data_type": data_type}
            )
            return None
    
    def _validate_required_context(
        self,
        template: PromptTemplate,
        context: dict[str, Any]
    ) -> list[str]:
        """
        Validate that all required context variables are provided.
        
        Args:
            template: Prompt template
            context: Provided context variables
            
        Returns:
            List of missing required variables
            
        Validates: Requirement 6.6
        """
        missing = []
        for var_name in template.required_context:
            if var_name not in context or context[var_name] is None:
                missing.append(var_name)
        return missing
    
    def _process_conditional_sections(
        self,
        template: str,
        conditional_sections: dict[str, list[str]],
        context: dict[str, Any]
    ) -> str:
        """
        Process conditional sections in template.
        
        Supports {{#if condition}}...{{/if}} syntax.
        Section is included if condition variable is truthy.
        
        Args:
            template: Template text with conditional sections
            conditional_sections: Conditional section definitions
            context: Context variables
            
        Returns:
            Template with conditional sections processed
            
        Validates: Requirement 6.5
        """
        # Pattern to match {{#if condition}}...{{/if}}
        pattern = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}'
        
        def replace_conditional(match):
            condition = match.group(1)
            content = match.group(2)
            
            # Check if condition is truthy in context
            condition_value = context.get(condition, False)
            
            # For conditional sections defined in config, check if all required vars exist
            if condition in conditional_sections:
                required_vars = conditional_sections[condition]
                condition_value = all(
                    context.get(var) is not None
                    for var in required_vars
                )
            
            # Include content if condition is truthy
            if condition_value:
                return content
            else:
                return ''
        
        # Process all conditional sections
        result = re.sub(pattern, replace_conditional, template, flags=re.DOTALL)
        return result
    
    def _replace_placeholders(
        self,
        template: str,
        context: dict[str, Any]
    ) -> str:
        """
        Replace {{variable_name}} placeholders with context values.
        
        Args:
            template: Template text with placeholders
            context: Context variables
            
        Returns:
            Template with placeholders replaced
            
        Validates: Requirement 6.2, 6.4
        """
        # Pattern to match {{variable_name}}
        pattern = r'\{\{(\w+)\}\}'
        
        def replace_placeholder(match):
            var_name = match.group(1)
            value = context.get(var_name, '')
            
            # Convert value to string
            if value is None:
                return ''
            elif isinstance(value, (list, dict)):
                # Format lists and dicts nicely
                if isinstance(value, list):
                    return ', '.join(str(v) for v in value)
                else:
                    return str(value)
            else:
                return str(value)
        
        # Replace all placeholders
        result = re.sub(pattern, replace_placeholder, template)
        return result
    
    def get_available_data_types(self) -> list[str]:
        """
        Get list of available data types with templates.
        
        Returns:
            List of data type identifiers
        """
        return list(self.templates.keys())
    
    def get_context_variable_info(self, var_name: str) -> Optional[dict[str, Any]]:
        """
        Get information about a context variable.
        
        Args:
            var_name: Variable name
            
        Returns:
            Variable info dict or None
            
        Validates: Requirement 6.3
        """
        return self.context_variables.get(var_name)

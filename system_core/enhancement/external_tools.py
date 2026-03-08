"""
External Tools Module - Dynamic registration and execution of third-party tools.

This module provides:
- Tool registration from config
- Tool download and validation
- Tool execution (import and command_line methods)
- Risk warnings and error handling
"""

import os
import re
import subprocess
import importlib.util
import yaml
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel

from system_core.config import get_logger

logger = get_logger(__name__)

class ExternalTool(BaseModel):
    """External tool configuration."""
    name: str
    source_type: str  # github, local
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    integration_method: str  # import, command_line
    entry_point: Optional[str] = None
    command_template: Optional[str] = None
    risk_warning: str
    timeout: int = 60
    enabled: bool = True
    parameters: dict[str, Any] = {}

class ExternalToolRegistry:
    """Registry for managing external tools."""
    
    def __init__(self, config_path: str = "config/external_tools.yaml"):
        """
        Initialize External Tool Registry.
        
        Args:
            config_path: Path to external tools configuration
        """
        self.config_path = Path(config_path)
        self.tools: dict[str, ExternalTool] = {}
        self.security_config: dict[str, Any] = {}
        self.tools_dir = Path("external_tools")
        
        # Ensure tools directory exists
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self._load_config()
        
        logger.info("external_tool_registry_initialized",
                   config_path=str(self.config_path),
                   tools_count=len(self.tools))
    
    def _load_config(self):
        """Load external tools configuration."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Load security settings
            self.security_config = config.get('security', {})
            
            # Load tools
            tools_config = config.get('tools', [])
            for tool_config in tools_config:
                try:
                    tool = ExternalTool(**tool_config)
                    self.tools[tool.name] = tool
                    logger.info("tool_registered",
                               tool_name=tool.name,
                               source_type=tool.source_type,
                               integration_method=tool.integration_method,
                               enabled=tool.enabled)
                except Exception as e:
                    logger.error("tool_registration_failed",
                                tool_name=tool_config.get('name', 'unknown'),
                                error=str(e))
            
            logger.info("external_tools_config_loaded",
                       total_tools=len(self.tools),
                       enabled_tools=sum(1 for t in self.tools.values() if t.enabled))
            
        except Exception as e:
            logger.error("config_load_failed", error=str(e))
            raise
    
    def _validate_file_extension(self, file_path: Path) -> bool:
        """
        Validate file extension against whitelist.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if extension is allowed
        """
        allowed_extensions = self.security_config.get('allowed_file_extensions', ['.py', '.sh', '.js'])
        return file_path.suffix in allowed_extensions
    
    def _scan_for_suspicious_patterns(self, content: str) -> list[str]:
        """
        Scan content for suspicious patterns.
        
        Args:
            content: File content to scan
            
        Returns:
            List of detected suspicious patterns
        """
        blocked_patterns = self.security_config.get('blocked_patterns', [])
        detected = []
        
        for pattern in blocked_patterns:
            if re.search(re.escape(pattern), content, re.IGNORECASE):
                detected.append(pattern)
        
        return detected
    
    def download_and_validate_tool(self, tool_name: str) -> bool:
        """
        Download and validate external tool.
        
        Args:
            tool_name: Name of tool to download
            
        Returns:
            True if download and validation successful
        """
        if tool_name not in self.tools:
            logger.error("tool_not_found", tool_name=tool_name)
            return False
        
        tool = self.tools[tool_name]
        
        try:
            if tool.source_type == 'github':
                return self._download_from_github(tool)
            elif tool.source_type == 'local':
                return self._validate_local_path(tool)
            else:
                logger.error("unsupported_source_type",
                            tool_name=tool_name,
                            source_type=tool.source_type)
                return False
                
        except Exception as e:
            logger.error("tool_download_validation_failed",
                        tool_name=tool_name,
                        error=str(e))
            return False
    
    def _download_from_github(self, tool: ExternalTool) -> bool:
        """
        Download tool from GitHub repository.
        
        Args:
            tool: Tool configuration
            
        Returns:
            True if download successful
        """
        try:
            tool_path = self.tools_dir / tool.name
            
            # Check if already downloaded
            if tool_path.exists():
                logger.info("tool_already_downloaded",
                           tool_name=tool.name,
                           path=str(tool_path))
                return self._validate_tool_files(tool_path)
            
            # Clone repository
            logger.info("cloning_github_repo",
                       tool_name=tool.name,
                       url=tool.source_url)
            
            result = subprocess.run(
                ['git', 'clone', tool.source_url, str(tool_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                logger.error("git_clone_failed",
                            tool_name=tool.name,
                            error=result.stderr)
                return False
            
            logger.info("github_repo_cloned",
                       tool_name=tool.name,
                       path=str(tool_path))
            
            # Validate downloaded files
            return self._validate_tool_files(tool_path)
            
        except subprocess.TimeoutExpired:
            logger.error("git_clone_timeout", tool_name=tool.name)
            return False
        except Exception as e:
            logger.error("github_download_failed",
                        tool_name=tool.name,
                        error=str(e))
            return False
    
    def _validate_local_path(self, tool: ExternalTool) -> bool:
        """
        Validate local tool path exists.
        
        Args:
            tool: Tool configuration
            
        Returns:
            True if path exists and is valid
        """
        if not tool.source_path:
            logger.error("no_source_path", tool_name=tool.name)
            return False
        
        tool_path = Path(tool.source_path)
        
        if not tool_path.exists():
            logger.error("local_path_not_found",
                        tool_name=tool.name,
                        path=str(tool_path))
            return False
        
        logger.info("local_path_validated",
                   tool_name=tool.name,
                   path=str(tool_path))
        
        return self._validate_tool_files(tool_path)
    
    def _validate_tool_files(self, tool_path: Path) -> bool:
        """
        Validate tool files for security.
        
        Args:
            tool_path: Path to tool directory
            
        Returns:
            True if validation passes
        """
        try:
            suspicious_files = []
            
            # Scan all files in tool directory
            for file_path in tool_path.rglob('*'):
                if not file_path.is_file():
                    continue
                
                # Check file extension
                if not self._validate_file_extension(file_path):
                    logger.warning("suspicious_file_extension",
                                 file=str(file_path),
                                 extension=file_path.suffix)
                    continue
                
                # Scan file content for suspicious patterns
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    detected_patterns = self._scan_for_suspicious_patterns(content)
                    if detected_patterns:
                        suspicious_files.append({
                            'file': str(file_path),
                            'patterns': detected_patterns
                        })
                        logger.warning("suspicious_patterns_detected",
                                     file=str(file_path),
                                     patterns=detected_patterns)
                
                except Exception as e:
                    logger.warning("file_scan_failed",
                                 file=str(file_path),
                                 error=str(e))
            
            if suspicious_files:
                logger.warning("tool_validation_completed_with_warnings",
                             tool_path=str(tool_path),
                             suspicious_files_count=len(suspicious_files))
                return False
            
            logger.info("tool_validation_passed", tool_path=str(tool_path))
            return True
            
        except Exception as e:
            logger.error("tool_validation_failed",
                        tool_path=str(tool_path),
                        error=str(e))
            return False
    
    def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute external tool.
        
        Args:
            tool_name: Name of tool to execute
            params: Tool parameters
            
        Returns:
            Execution result dictionary
        """
        if tool_name not in self.tools:
            return {
                'success': False,
                'error': f"Tool '{tool_name}' not found"
            }
        
        tool = self.tools[tool_name]
        
        if not tool.enabled:
            return {
                'success': False,
                'error': f"Tool '{tool_name}' is disabled"
            }
        
        # Log risk warning
        logger.warning("executing_external_tool",
                      tool_name=tool_name,
                      risk_warning=tool.risk_warning)
        
        try:
            if tool.integration_method == 'import':
                return self._execute_import_tool(tool, params)
            elif tool.integration_method == 'command_line':
                return self._execute_command_line_tool(tool, params)
            else:
                return {
                    'success': False,
                    'error': f"Unsupported integration method: {tool.integration_method}"
                }
                
        except Exception as e:
            logger.error("tool_execution_failed",
                        tool_name=tool_name,
                        error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_import_tool(
        self,
        tool: ExternalTool,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute tool via Python import.
        
        Args:
            tool: Tool configuration
            params: Tool parameters
            
        Returns:
            Execution result
        """
        try:
            # Determine tool path
            if tool.source_type == 'github':
                tool_path = self.tools_dir / tool.name
            else:
                tool_path = Path(tool.source_path)
            
            if not tool_path.exists():
                return {
                    'success': False,
                    'error': f"Tool path not found: {tool_path}"
                }
            
            # Parse entry point (module.function)
            if not tool.entry_point:
                return {
                    'success': False,
                    'error': "No entry point specified"
                }
            
            module_name, function_name = tool.entry_point.rsplit('.', 1)
            module_file = tool_path / f"{module_name.replace('.', '/')}.py"
            
            if not module_file.exists():
                return {
                    'success': False,
                    'error': f"Module file not found: {module_file}"
                }
            
            # Load module
            spec = importlib.util.spec_from_file_location(module_name, module_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get function
            if not hasattr(module, function_name):
                return {
                    'success': False,
                    'error': f"Function '{function_name}' not found in module"
                }
            
            func = getattr(module, function_name)
            
            # Execute function
            result = func(**params)
            
            logger.info("import_tool_executed",
                       tool_name=tool.name,
                       entry_point=tool.entry_point)
            
            return {
                'success': True,
                'result': result
            }
            
        except Exception as e:
            logger.error("import_tool_execution_failed",
                        tool_name=tool.name,
                        error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_command_line_tool(
        self,
        tool: ExternalTool,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute tool via command line.
        
        Args:
            tool: Tool configuration
            params: Tool parameters
            
        Returns:
            Execution result
        """
        try:
            if not tool.command_template:
                return {
                    'success': False,
                    'error': "No command template specified"
                }
            
            # Format command with parameters
            command = tool.command_template.format(**params)
            
            # Execute command
            max_timeout = self.security_config.get('max_tool_execution_time', 120)
            timeout = min(tool.timeout, max_timeout)
            
            logger.info("executing_command_line_tool",
                       tool_name=tool.name,
                       command=command,
                       timeout=timeout)
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            logger.info("command_line_tool_executed",
                       tool_name=tool.name,
                       return_code=result.returncode)
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            logger.error("command_line_tool_timeout",
                        tool_name=tool.name,
                        timeout=timeout)
            return {
                'success': False,
                'error': f"Tool execution timed out after {timeout} seconds"
            }
        except Exception as e:
            logger.error("command_line_tool_execution_failed",
                        tool_name=tool.name,
                        error=str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_tool(self, tool_name: str) -> Optional[ExternalTool]:
        """
        Get tool configuration by name.
        
        Args:
            tool_name: Tool name
            
        Returns:
            Tool configuration or None
        """
        return self.tools.get(tool_name)
    
    def list_tools(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """
        List all registered tools.
        
        Args:
            enabled_only: Only return enabled tools
            
        Returns:
            List of tool information dictionaries
        """
        tools_list = []
        
        for tool in self.tools.values():
            if enabled_only and not tool.enabled:
                continue
            
            tools_list.append({
                'name': tool.name,
                'source_type': tool.source_type,
                'integration_method': tool.integration_method,
                'risk_warning': tool.risk_warning,
                'enabled': tool.enabled
            })
        
        return tools_list

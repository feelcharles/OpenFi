"""
Factor Manager

Manages factor loading, registration, validation, and hot reload.
Implements security checks to prevent malicious code execution.
"""

import ast
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Optional
import time

from system_core.factor_system.base_factor import BaseFactor
from system_core.core.exceptions import ConfigurationError
from system_core.config.global_config import get_factor_config, register_config_callback

logger = logging.getLogger(__name__)

class FactorValidationError(Exception):
    """Raised when factor validation fails"""
    pass

class FactorSecurityError(Exception):
    """Raised when factor code contains security violations"""
    pass

class FactorManager:
    """
    Factor Manager
    
    Manages the lifecycle of factors including:
    - Loading factor code from the factor library
    - Validating factor code for security and correctness
    - Registering factors for use
    - Hot reloading factors when code changes
    """
    
    # Forbidden operations in factor code (security)
    FORBIDDEN_IMPORTS = {
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests',
        'pickle', 'shelve', 'marshal', 'eval', 'exec', 'compile',
        '__import__', 'open', 'file', 'input', 'raw_input'
    }
    
    FORBIDDEN_BUILTINS = {
        'eval', 'exec', 'compile', '__import__', 'open', 'file',
        'input', 'raw_input', 'execfile', 'reload'
    }
    
    def __init__(self, factor_library_path: str = "factors/"):
        """
        Initialize Factor Manager.
        
        Args:
            factor_library_path: Path to factor library directory
        """
        self.factor_library_path = Path(factor_library_path)
        self._factors: dict[str, BaseFactor] = {}
        
        # Load factor configuration from global config manager
        self.config = get_factor_config() or {}
        
        # Register callback for config changes
        register_config_callback('factor_config.yaml', self._on_config_changed)
        self._factor_metadata: dict[str, dict] = {}
        self._factor_files: dict[str, Path] = {}  # factor_name -> file_path
        self._file_mtimes: dict[Path, float] = {}  # file_path -> modification_time
        
        if not self.factor_library_path.exists():
            logger.warning(f"Factor library path does not exist: {self.factor_library_path}")
            self.factor_library_path.mkdir(parents=True, exist_ok=True)
    
    def load_factors(self) -> list[str]:
        """
        Load all factors from the factor library.
        
        Returns:
            List of successfully loaded factor names
        """
        loaded_factors = []
        
        # Scan all subdirectories
        for category_dir in self.factor_library_path.iterdir():
            if not category_dir.is_dir():
                continue
            
            if category_dir.name.startswith('_') or category_dir.name.startswith('.'):
                continue
            
            # Load factors from this category
            for factor_file in category_dir.glob('*.py'):
                if factor_file.name.startswith('_') or factor_file.name == '__init__.py':
                    continue
                
                try:
                    factor_name = self._load_factor_from_file(factor_file)
                    if factor_name:
                        loaded_factors.append(factor_name)
                        logger.info(f"Loaded factor: {factor_name} from {factor_file}")
                except Exception as e:
                    logger.error(f"Failed to load factor from {factor_file}: {e}")
        
        logger.info(f"Successfully loaded {len(loaded_factors)} factors")
        return loaded_factors
    
    def _load_factor_from_file(self, file_path: Path) -> Optional[str]:
        """
        Load a factor from a Python file.
        
        Args:
            file_path: Path to factor file
        
        Returns:
            Factor name if successful, None otherwise
        
        Raises:
            FactorValidationError: If factor validation fails
            FactorSecurityError: If factor code contains security violations
        """
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Security check
        self._check_security(code, file_path)
        
        # Load module
        module_name = f"factor_{file_path.stem}_{int(time.time())}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise FactorValidationError(f"Failed to load module spec from {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise FactorValidationError(f"Failed to execute module: {e}")
        
        # Find BaseFactor subclasses
        factor_classes = []
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and 
                issubclass(obj, BaseFactor) and 
                obj is not BaseFactor):
                factor_classes.append(obj)
        
        if not factor_classes:
            raise FactorValidationError(f"No BaseFactor subclass found in {file_path}")
        
        if len(factor_classes) > 1:
            logger.warning(f"Multiple factor classes found in {file_path}, using first one")
        
        # Instantiate factor
        factor_class = factor_classes[0]
        try:
            factor = factor_class()
        except Exception as e:
            raise FactorValidationError(f"Failed to instantiate factor: {e}")
        
        # Validate factor
        self._validate_factor(factor)
        
        # Register factor
        factor_name = factor.name
        self._factors[factor_name] = factor
        self._factor_metadata[factor_name] = factor.get_metadata()
        self._factor_files[factor_name] = file_path
        self._file_mtimes[file_path] = file_path.stat().st_mtime
        
        return factor_name
    
    def _check_security(self, code: str, file_path: Path) -> None:
        """
        Check factor code for security violations.
        
        Args:
            code: Factor code
            file_path: Path to factor file
        
        Raises:
            FactorSecurityError: If security violations found
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise FactorValidationError(f"Syntax error in {file_path}: {e}")
        
        # Check for forbidden imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.FORBIDDEN_IMPORTS:
                        raise FactorSecurityError(
                            f"Forbidden import '{alias.name}' in {file_path}"
                        )
            
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module in self.FORBIDDEN_IMPORTS:
                    raise FactorSecurityError(
                        f"Forbidden import from '{node.module}' in {file_path}"
                    )
            
            # Check for forbidden built-in functions
            elif isinstance(node, ast.Name):
                if node.id in self.FORBIDDEN_BUILTINS:
                    raise FactorSecurityError(
                        f"Forbidden built-in '{node.id}' in {file_path}"
                    )
            
            # Check for file operations
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['open', 'file']:
                        raise FactorSecurityError(
                            f"File operation '{node.func.id}' not allowed in {file_path}"
                        )
    
    def _validate_factor(self, factor: BaseFactor) -> None:
        """
        Validate factor implementation.
        
        Args:
            factor: Factor instance
        
        Raises:
            FactorValidationError: If validation fails
        """
        # Check required attributes
        if not factor.name:
            raise FactorValidationError("Factor name is required")
        
        if not factor.description:
            raise FactorValidationError("Factor description is required")
        
        if not factor.required_data:
            raise FactorValidationError("Factor must specify required data sources")
        
        # Check if calculate method is implemented
        if not hasattr(factor, 'calculate'):
            raise FactorValidationError("Factor must implement calculate() method")
        
        # Check if calculate is callable
        if not callable(getattr(factor, 'calculate')):
            raise FactorValidationError("calculate must be a callable method")
    
    def register_factor(self, factor: BaseFactor) -> None:
        """
        Register a factor instance.
        
        Args:
            factor: Factor instance to register
        
        Raises:
            FactorValidationError: If validation fails
        """
        self._validate_factor(factor)
        
        factor_name = factor.name
        if factor_name in self._factors:
            logger.warning(f"Factor {factor_name} already registered, replacing")
        
        self._factors[factor_name] = factor
        self._factor_metadata[factor_name] = factor.get_metadata()
        
        logger.info(f"Registered factor: {factor_name}")
    
    def get_factor(self, factor_name: str) -> Optional[BaseFactor]:
        """
        Get a registered factor by name.
        
        Args:
            factor_name: Factor name
        
        Returns:
            Factor instance or None if not found
        """
        return self._factors.get(factor_name)
    
    def list_factors(self) -> list[dict]:
        """
        List all registered factors with metadata.
        
        Returns:
            List of factor metadata dictionaries
        """
        return list(self._factor_metadata.values())
    
    def reload_factor(self, factor_name: str) -> bool:
        """
        Reload a factor from its source file.
        
        Args:
            factor_name: Factor name to reload
        
        Returns:
            True if successful, False otherwise
        """
        if factor_name not in self._factor_files:
            logger.error(f"Factor {factor_name} not found in file registry")
            return False
        
        file_path = self._factor_files[factor_name]
        
        if not file_path.exists():
            logger.error(f"Factor file not found: {file_path}")
            return False
        
        try:
            # Unregister old factor
            del self._factors[factor_name]
            del self._factor_metadata[factor_name]
            
            # Load new version
            new_factor_name = self._load_factor_from_file(file_path)
            
            if new_factor_name != factor_name:
                logger.warning(
                    f"Factor name changed from {factor_name} to {new_factor_name} after reload"
                )
            
            logger.info(f"Successfully reloaded factor: {factor_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload factor {factor_name}: {e}")
            return False
    
    def check_for_updates(self) -> list[str]:
        """
        Check for modified factor files and reload them.
        
        Returns:
            List of reloaded factor names
        """
        reloaded = []
        
        for factor_name, file_path in self._factor_files.items():
            if not file_path.exists():
                continue
            
            current_mtime = file_path.stat().st_mtime
            last_mtime = self._file_mtimes.get(file_path, 0)
            
            if current_mtime > last_mtime:
                logger.info(f"Factor file modified: {file_path}")
                if self.reload_factor(factor_name):
                    reloaded.append(factor_name)
        
        return reloaded
    
    def validate_factor_code(self, code: str) -> dict[str, any]:
        """
        Validate factor code without loading it.
        
        Args:
            code: Factor code to validate
        
        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'errors': list[str],
                'warnings': list[str]
            }
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            result['valid'] = False
            result['errors'].append(f"Syntax error: {e}")
            return result
        
        # Check security
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.FORBIDDEN_IMPORTS:
                            result['valid'] = False
                            result['errors'].append(f"Forbidden import: {alias.name}")
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module in self.FORBIDDEN_IMPORTS:
                        result['valid'] = False
                        result['errors'].append(f"Forbidden import from: {node.module}")
                
                elif isinstance(node, ast.Name):
                    if node.id in self.FORBIDDEN_BUILTINS:
                        result['valid'] = False
                        result['errors'].append(f"Forbidden built-in: {node.id}")
        
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Validation error: {e}")
        
        return result
    
    def get_factor_count(self) -> int:
        """
        Get the number of registered factors.
        
        Returns:
            Number of factors
        """
        return len(self._factors)
    

    def _on_config_changed(self, config_name: str, new_config: dict) -> None:
        """
        Handle factor configuration changes.
        
        Args:
            config_name: Name of changed config file
            new_config: New configuration dictionary
        """
        logger.info(f"Factor configuration changed, reloading...")
        self.config = new_config
        # Optionally reload factors
        self.check_for_updates()
    
    def clear_factors(self) -> None:
        """Clear all registered factors."""
        self._factors.clear()
        self._factor_metadata.clear()
        self._factor_files.clear()
        self._file_mtimes.clear()
        logger.info("Cleared all registered factors")

# Global factor manager instance
_factor_manager: Optional[FactorManager] = None

def get_factor_manager(factor_library_path: str = "factors/") -> FactorManager:
    """
    Get global factor manager instance.
    
    Args:
        factor_library_path: Path to factor library
    
    Returns:
        Global factor manager
    """
    global _factor_manager
    if _factor_manager is None:
        _factor_manager = FactorManager(factor_library_path)
    return _factor_manager

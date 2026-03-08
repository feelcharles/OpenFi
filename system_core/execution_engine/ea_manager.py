"""
EA Manager Module - Manages EA file scanning, registration, and testing.

This module provides functionality to:
- Scan the ea/ folder for EA files
- Identify platform types (MT4, MT5, TradingView)
- Extract metadata from EA files
- Update ea_config.yaml with discovered EAs
- Execute simulation tests on EAs
"""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from system_core.config import get_logger

logger = get_logger(__name__)

class EAManager:
    """Manages EA file discovery, registration, and testing."""
    
    # Platform type mapping based on file extensions
    PLATFORM_MAP = {
        '.ex4': 'mt4',
        '.mq4': 'mt4',
        '.ex5': 'mt5',
        '.mq5': 'mt5',
        '.pine': 'tradingview'
    }
    
    SUPPORTED_EXTENSIONS = list(PLATFORM_MAP.keys())
    
    def __init__(self, ea_folder: str = "ea", config_path: str = "config/ea_config.yaml"):
        """
        Initialize EA Manager.
        
        Args:
            ea_folder: Path to EA folder (default: "ea")
            config_path: Path to EA config file (default: "config/ea_config.yaml")
        """
        self.ea_folder = Path(ea_folder)
        self.config_path = Path(config_path)
        self.logs_folder = self.ea_folder / "logs"
        
        # Ensure folders exist
        self._ensure_folders()
    
    def _ensure_folders(self):
        """Create EA and logs folders if they don't exist."""
        try:
            self.ea_folder.mkdir(parents=True, exist_ok=True)
            self.logs_folder.mkdir(parents=True, exist_ok=True)
            logger.info("ea_folders_created", 
                       ea_folder=str(self.ea_folder),
                       logs_folder=str(self.logs_folder))
        except Exception as e:
            logger.error("failed_to_create_ea_folders", error=str(e))
            raise
    
    def scan_ea_folder(self) -> list[dict]:
        """
        Scan EA folder and discover all EA files.
        Excludes 'logs' folder.
        
        Returns:
            List of EA metadata dictionaries
        """
        discovered_eas = []
        
        try:
            # Walk through EA folder and subfolders
            for root, dirs, files in os.walk(self.ea_folder):
                # Exclude logs and __pycache__ folders
                dirs[:] = [d for d in dirs if d not in ['logs', '__pycache__']]
                
                for file in files:
                    file_path = Path(root) / file
                    file_ext = file_path.suffix.lower()
                    
                    # Check if file is a supported EA file
                    if file_ext in self.SUPPORTED_EXTENSIONS:
                        ea_metadata = self._extract_ea_metadata(file_path)
                        if ea_metadata:
                            discovered_eas.append(ea_metadata)
            
            logger.info("ea_scan_completed", 
                       total_eas=len(discovered_eas),
                       mt4_count=sum(1 for ea in discovered_eas if ea['ea_type'] == 'mt4'),
                       mt5_count=sum(1 for ea in discovered_eas if ea['ea_type'] == 'mt5'),
                       tradingview_count=sum(1 for ea in discovered_eas if ea['ea_type'] == 'tradingview'))
            
            return discovered_eas
            
        except Exception as e:
            logger.error("ea_scan_failed", error=str(e))
            return []
    
    def _extract_ea_metadata(self, file_path: Path) -> Optional[dict]:
        """
        Extract metadata from EA file.
        
        Args:
            file_path: Path to EA file
            
        Returns:
            EA metadata dictionary or None if extraction fails
        """
        try:
            file_ext = file_path.suffix.lower()
            platform_type = self.PLATFORM_MAP.get(file_ext)
            
            if not platform_type:
                logger.warning("unsupported_file_extension", 
                             file=str(file_path), 
                             extension=file_ext)
                return None
            
            # Generate EA ID from filename
            ea_id = file_path.stem.lower().replace(' ', '_')
            
            # Get relative path from project root
            try:
                rel_path = file_path.relative_to(Path.cwd())
            except ValueError:
                # If file is not relative to cwd, use absolute path
                rel_path = file_path
            
            # Extract metadata based on platform type
            metadata = {
                'ea_id': ea_id,
                'ea_name': file_path.stem,
                'ea_type': platform_type,
                'file_path': str(rel_path).replace('\\', '/'),
                'enabled': True,
                'description': '',
                'author': 'User',
                'version': '1.0.0',
                'symbols': [],
                'timeframes': [],
                'parameters': {},
                'performance': {
                    'win_rate': 0.0,
                    'profit_factor': 0.0,
                    'max_drawdown': 0.0,
                    'total_trades': 0,
                    'last_backtest': None
                }
            }
            
            # Try to extract additional metadata from source files
            if file_ext in ['.mq4', '.mq5', '.pine']:
                extracted_info = self._parse_source_file(file_path, platform_type)
                metadata.update(extracted_info)
            
            # Add file stats
            stat = file_path.stat()
            metadata['file_size'] = stat.st_size
            metadata['last_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            logger.info("ea_metadata_extracted", 
                       ea_id=ea_id, 
                       platform=platform_type,
                       file=str(file_path))
            
            return metadata
            
        except Exception as e:
            logger.error("metadata_extraction_failed", 
                        file=str(file_path), 
                        error=str(e))
            return None
    
    def _parse_source_file(self, file_path: Path, platform_type: str) -> dict:
        """
        Parse source file to extract metadata from comments and properties.
        
        Args:
            file_path: Path to source file
            platform_type: Platform type (mt4, mt5, tradingview)
            
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10000)  # Read first 10KB for metadata
            
            # Extract version
            version_match = re.search(r'@version\s+([0-9.]+)', content, re.IGNORECASE)
            if version_match:
                metadata['version'] = version_match.group(1)
            
            # Extract author
            author_match = re.search(r'@author\s+(.+)', content, re.IGNORECASE)
            if author_match:
                metadata['author'] = author_match.group(1).strip()
            
            # Extract description
            desc_match = re.search(r'@description\s+(.+)', content, re.IGNORECASE)
            if desc_match:
                metadata['description'] = desc_match.group(1).strip()
            
            # Platform-specific parsing
            if platform_type in ['mt4', 'mt5']:
                # Extract property values
                prop_match = re.search(r'#property\s+description\s+"([^"]+)"', content)
                if prop_match and not metadata.get('description'):
                    metadata['description'] = prop_match.group(1)
                
                prop_version = re.search(r'#property\s+version\s+"([^"]+)"', content)
                if prop_version and not metadata.get('version'):
                    metadata['version'] = prop_version.group(1)
            
            elif platform_type == 'tradingview':
                # Extract Pine Script indicator/strategy name
                indicator_match = re.search(r'indicator\(["\']([^"\']+)["\']', content)
                strategy_match = re.search(r'strategy\(["\']([^"\']+)["\']', content)
                
                if indicator_match:
                    metadata['description'] = f"Indicator: {indicator_match.group(1)}"
                elif strategy_match:
                    metadata['description'] = f"Strategy: {strategy_match.group(1)}"
        
        except Exception as e:
            logger.warning("source_file_parsing_failed", 
                          file=str(file_path), 
                          error=str(e))
        
        return metadata
    
    def update_ea_config(self, discovered_eas: list[dict]) -> tuple[int, int, int]:
        """
        Update ea_config.yaml with discovered EAs.
        
        Args:
            discovered_eas: List of discovered EA metadata
            
        Returns:
            Tuple of (added_count, updated_count, removed_count)
        """
        try:
            # Load existing config
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            # Ensure eas list exists
            if 'eas' not in config:
                config['eas'] = []
            
            existing_eas = {ea['ea_id']: ea for ea in config['eas']}
            discovered_ea_ids = {ea['ea_id'] for ea in discovered_eas}
            
            added_count = 0
            updated_count = 0
            removed_count = 0
            
            # Add or update discovered EAs
            new_eas_list = []
            for ea in discovered_eas:
                ea_id = ea['ea_id']
                
                if ea_id in existing_eas:
                    # Update existing EA (preserve performance data)
                    existing_ea = existing_eas[ea_id]
                    ea['performance'] = existing_ea.get('performance', ea['performance'])
                    ea['enabled'] = existing_ea.get('enabled', True)
                    updated_count += 1
                else:
                    # New EA
                    added_count += 1
                
                new_eas_list.append(ea)
            
            # Count removed EAs
            for ea_id in existing_eas:
                if ea_id not in discovered_ea_ids:
                    removed_count += 1
            
            # Update config
            config['eas'] = new_eas_list
            
            # Write config back
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            logger.info("ea_config_updated", 
                       added=added_count, 
                       updated=updated_count, 
                       removed=removed_count,
                       total=len(new_eas_list))
            
            return added_count, updated_count, removed_count
            
        except Exception as e:
            logger.error("ea_config_update_failed", error=str(e))
            raise
    
    def refresh_ea_list(self) -> dict:
        """
        Scan EA folder and update configuration.
        
        Returns:
            Dictionary with refresh results
        """
        try:
            # Scan folder
            discovered_eas = self.scan_ea_folder()
            
            # Update config
            added, updated, removed = self.update_ea_config(discovered_eas)
            
            # Calculate statistics
            platform_stats = {
                'mt4': sum(1 for ea in discovered_eas if ea['ea_type'] == 'mt4'),
                'mt5': sum(1 for ea in discovered_eas if ea['ea_type'] == 'mt5'),
                'tradingview': sum(1 for ea in discovered_eas if ea['ea_type'] == 'tradingview')
            }
            
            result = {
                'success': True,
                'total_eas': len(discovered_eas),
                'added': added,
                'updated': updated,
                'removed': removed,
                'platform_stats': platform_stats,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info("ea_list_refreshed", **result)
            
            return result
            
        except Exception as e:
            logger.error("ea_list_refresh_failed", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def find_ea_by_name(self, name: str) -> Optional[dict]:
        """
        Find EA by name or ID.
        
        Args:
            name: EA name or ID (case-insensitive)
            
        Returns:
            EA metadata dictionary or None if not found
        """
        try:
            if not self.config_path.exists():
                return None
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            eas = config.get('eas', [])
            name_lower = name.lower()
            
            # Search by ea_id or ea_name
            matches = [
                ea for ea in eas 
                if ea['ea_id'].lower() == name_lower or 
                   ea['ea_name'].lower() == name_lower
            ]
            
            if len(matches) == 0:
                return None
            elif len(matches) == 1:
                return matches[0]
            else:
                # Multiple matches - ambiguous
                logger.warning("ambiguous_ea_name", name=name, matches=len(matches))
                return None
                
        except Exception as e:
            logger.error("ea_lookup_failed", name=name, error=str(e))
            return None

    
    def test_ea(self, name: str) -> dict[str, Any]:
        """
        Test EA in simulation environment.
        
        Args:
            name: EA name or ID
            
        Returns:
            Test result dictionary
        """
        try:
            # Find EA
            ea = self.find_ea_by_name(name)
            if not ea:
                return {
                    'success': False,
                    'error': f"EA '{name}' not found. Use /ea_refresh to update EA list.",
                    'test_status': 'not_found'
                }
            
            logger.info("ea_test_started",
                       ea_id=ea['ea_id'],
                       ea_name=ea['ea_name'],
                       platform=ea['ea_type'])
            
            # Execute platform-specific test
            if ea['ea_type'] in ['mt4', 'mt5']:
                result = self._test_mt_ea(ea)
            elif ea['ea_type'] == 'tradingview':
                result = self._test_tradingview_ea(ea)
            else:
                return {
                    'success': False,
                    'error': f"Unsupported platform: {ea['ea_type']}",
                    'test_status': 'unsupported_platform'
                }
            
            logger.info("ea_test_completed",
                       ea_id=ea['ea_id'],
                       test_status=result.get('test_status'),
                       error_count=result.get('error_count', 0))
            
            return result
            
        except Exception as e:
            logger.error("ea_test_failed", name=name, error=str(e))
            return {
                'success': False,
                'error': str(e),
                'test_status': 'error'
            }
    
    def _test_mt_ea(self, ea: dict) -> dict[str, Any]:
        """
        Test MT4/MT5 EA using Strategy Tester.
        
        Args:
            ea: EA metadata dictionary
            
        Returns:
            Test result dictionary
        """
        start_time = datetime.now()
        
        try:
            # For now, we'll do basic validation since we don't have MT4/MT5 API
            # In production, this would use MetaTrader Strategy Tester API
            
            file_path = Path(ea['file_path'])
            
            # Check if file exists
            if not file_path.exists():
                return {
                    'success': False,
                    'test_status': 'failed',
                    'error_count': 1,
                    'error_types': ['file_not_found'],
                    'execution_time': 0,
                    'log_file_path': None,
                    'errors': [f"EA file not found: {file_path}"]
                }
            
            # For source files (.mq4, .mq5), we can do syntax validation
            errors = []
            warnings = []
            
            if file_path.suffix in ['.mq4', '.mq5']:
                # Read and validate source file
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Basic syntax checks
                    if 'OnInit()' not in content and 'OnStart()' not in content:
                        warnings.append("No OnInit() or OnStart() function found")
                    
                    if 'OnTick()' not in content and ea['ea_type'] == 'mt5':
                        warnings.append("No OnTick() function found (MT5 EA)")
                    
                    # Check for common errors
                    if content.count('{') != content.count('}'):
                        errors.append("Mismatched braces")
                    
                    if content.count('(') != content.count(')'):
                        errors.append("Mismatched parentheses")
                
                except Exception as e:
                    errors.append(f"Failed to read source file: {str(e)}")
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Save test log
            log_file_path = self._save_test_log(
                ea=ea,
                start_time=start_time,
                end_time=datetime.now(),
                errors=errors,
                warnings=warnings,
                test_status='passed' if not errors else 'failed'
            )
            
            # Determine test status
            test_status = 'passed' if not errors else 'failed'
            
            return {
                'success': test_status == 'passed',
                'test_status': test_status,
                'error_count': len(errors),
                'error_types': ['syntax_error'] if errors else [],
                'execution_time': execution_time,
                'log_file_path': str(log_file_path),
                'errors': errors,
                'warnings': warnings,
                'platform': ea['ea_type'],
                'file_path': str(file_path)
            }
            
        except Exception as e:
            logger.error("mt_ea_test_failed",
                        ea_id=ea['ea_id'],
                        error=str(e))
            return {
                'success': False,
                'test_status': 'error',
                'error_count': 1,
                'error_types': ['test_error'],
                'execution_time': (datetime.now() - start_time).total_seconds(),
                'log_file_path': None,
                'errors': [str(e)]
            }
    
    def _test_tradingview_ea(self, ea: dict) -> dict[str, Any]:
        """
        Test TradingView Pine Script.
        
        Args:
            ea: EA metadata dictionary
            
        Returns:
            Test result dictionary
        """
        start_time = datetime.now()
        
        try:
            file_path = Path(ea['file_path'])
            
            # Check if file exists
            if not file_path.exists():
                return {
                    'success': False,
                    'test_status': 'failed',
                    'error_count': 1,
                    'error_types': ['file_not_found'],
                    'execution_time': 0,
                    'log_file_path': None,
                    'errors': [f"EA file not found: {file_path}"]
                }
            
            # Read and validate Pine Script
            errors = []
            warnings = []
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Basic Pine Script validation
                if '//@version=' not in content:
                    warnings.append("No Pine Script version declaration found")
                
                if 'indicator(' not in content and 'strategy(' not in content:
                    errors.append("No indicator() or strategy() declaration found")
                
                # Check for common syntax issues
                if content.count('(') != content.count(')'):
                    errors.append("Mismatched parentheses")
                
                if content.count('[') != content.count(']'):
                    errors.append("Mismatched brackets")
                
                # Check for required functions in strategies
                if 'strategy(' in content:
                    if 'strategy.entry' not in content and 'strategy.order' not in content:
                        warnings.append("No strategy.entry or strategy.order calls found")
            
            except Exception as e:
                errors.append(f"Failed to read Pine Script file: {str(e)}")
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Save test log
            log_file_path = self._save_test_log(
                ea=ea,
                start_time=start_time,
                end_time=datetime.now(),
                errors=errors,
                warnings=warnings,
                test_status='passed' if not errors else 'failed'
            )
            
            # Determine test status
            test_status = 'passed' if not errors else 'failed'
            
            return {
                'success': test_status == 'passed',
                'test_status': test_status,
                'error_count': len(errors),
                'error_types': ['syntax_error'] if errors else [],
                'execution_time': execution_time,
                'log_file_path': str(log_file_path),
                'errors': errors,
                'warnings': warnings,
                'platform': 'tradingview',
                'file_path': str(file_path)
            }
            
        except Exception as e:
            logger.error("tradingview_ea_test_failed",
                        ea_id=ea['ea_id'],
                        error=str(e))
            return {
                'success': False,
                'test_status': 'error',
                'error_count': 1,
                'error_types': ['test_error'],
                'execution_time': (datetime.now() - start_time).total_seconds(),
                'log_file_path': None,
                'errors': [str(e)]
            }
    
    def _save_test_log(
        self,
        ea: dict,
        start_time: datetime,
        end_time: datetime,
        errors: list[str],
        warnings: list[str],
        test_status: str
    ) -> Path:
        """
        Save test results to log file.
        
        Args:
            ea: EA metadata
            start_time: Test start time
            end_time: Test end time
            errors: List of errors
            warnings: List of warnings
            test_status: Test status (passed/failed)
            
        Returns:
            Path to log file
        """
        try:
            # Generate log filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"ea_log_{ea['ea_id']}_{timestamp}.txt"
            log_path = self.logs_folder / log_filename
            
            # Prepare log content
            duration = (end_time - start_time).total_seconds()
            
            log_content = f"""EA Test Log
================================================================================
EA Name:        {ea['ea_name']}
EA ID:          {ea['ea_id']}
Platform:       {ea['ea_type']}
File Path:      {ea['file_path']}
Test Status:    {test_status.upper()}

Timing
--------------------------------------------------------------------------------
Start Time:     {start_time.isoformat()}
End Time:       {end_time.isoformat()}
Duration:       {duration:.2f} seconds

Results
--------------------------------------------------------------------------------
Errors:         {len(errors)}
Warnings:       {len(warnings)}

"""
            
            if errors:
                log_content += "\nErrors:\n"
                for i, error in enumerate(errors, 1):
                    log_content += f"  {i}. {error}\n"
            
            if warnings:
                log_content += "\nWarnings:\n"
                for i, warning in enumerate(warnings, 1):
                    log_content += f"  {i}. {warning}\n"
            
            log_content += "\n" + "=" * 80 + "\n"
            
            # Write log file
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            logger.info("test_log_saved",
                       ea_id=ea['ea_id'],
                       log_path=str(log_path))
            
            return log_path
            
        except Exception as e:
            logger.error("test_log_save_failed",
                        ea_id=ea['ea_id'],
                        error=str(e))
            return Path("log_save_failed.txt")

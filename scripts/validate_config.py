#!/usr/bin/env python3
"""
Configuration validation script.

Validates all configuration files for syntax and schema correctness.
"""

import sys
from pathlib import Path
import yaml
from typing import Any

def validate_yaml_syntax(file_path: Path) -> tuple[bool, str]:
    """
    Validate YAML file syntax.
    
    Returns:
        (is_valid, error_message)
    """
    try:
        with open(file_path, 'r') as f:
            yaml.safe_load(f)
        return True, ""
    except yaml.YAMLError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {e}"

def validate_config_files() -> dict[str, Any]:
    """
    Validate all configuration files.
    
    Returns:
        Validation results
    """
    config_dir = Path('config')
    
    if not config_dir.exists():
        return {
            'status': 'error',
            'message': 'Config directory not found',
        }
    
    config_files = [
        'accounts.yaml',
        'assets.yaml',
        'audit_config.yaml',
        'bot_commands.yaml',
        'ea_config.yaml',
        'event_bus.yaml',
        'external_tools.yaml',
        'fetch_sources.yaml',
        'keywords.yaml',
        'llm_config.yaml',
        'profiles.yaml',
        'prompt_templates.yaml',
        'push_config.yaml',
        'retention_policy.yaml',
        'vector_db.yaml',
    ]
    
    results = {
        'status': 'success',
        'total_files': len(config_files),
        'valid_files': 0,
        'invalid_files': 0,
        'files': {},
    }
    
    for config_file in config_files:
        file_path = config_dir / config_file
        
        if not file_path.exists():
            results['files'][config_file] = {
                'status': 'missing',
                'error': 'File not found',
            }
            results['invalid_files'] += 1
            continue
        
        is_valid, error = validate_yaml_syntax(file_path)
        
        if is_valid:
            results['files'][config_file] = {
                'status': 'valid',
            }
            results['valid_files'] += 1
        else:
            results['files'][config_file] = {
                'status': 'invalid',
                'error': error,
            }
            results['invalid_files'] += 1
    
    if results['invalid_files'] > 0:
        results['status'] = 'failed'
    
    return results

def print_results(results: dict[str, Any]):
    """Print validation results."""
    print("\n" + "="*60)
    print("Configuration Validation Results")
    print("="*60 + "\n")
    
    print(f"Total files: {results['total_files']}")
    print(f"Valid files: {results['valid_files']}")
    print(f"Invalid files: {results['invalid_files']}")
    print()
    
    # Print details for each file
    for filename, file_result in results['files'].items():
        status = file_result['status']
        
        if status == 'valid':
            print(f"✓ {filename:<30} VALID")
        elif status == 'missing':
            print(f"✗ {filename:<30} MISSING")
        else:
            print(f"✗ {filename:<30} INVALID")
            print(f"  Error: {file_result.get('error', 'Unknown error')}")
    
    print("\n" + "="*60)
    
    if results['status'] == 'success':
        print("✓ All configuration files are valid")
    else:
        print("✗ Some configuration files have errors")
    
    print("="*60 + "\n")

def main():
    """Main function."""
    print("Validating configuration files...")
    
    results = validate_config_files()
    print_results(results)
    
    # Exit with error code if validation failed
    if results['status'] != 'success':
        sys.exit(1)
    
    sys.exit(0)

if __name__ == '__main__':
    main()

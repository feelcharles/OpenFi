#!/usr/bin/env python3
"""
Backup management CLI tool.

Provides command-line interface for backup operations.
"""

import asyncio
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from system_core.backup.backup_manager import get_backup_manager
from system_core.backup.storage_adapter import LocalStorageAdapter, S3StorageAdapter

def print_backup_list(backups, category):
    """Print formatted backup list."""
    print(f"\n{'='*80}")
    print(f"{category.upper()} Backups")
    print(f"{'='*80}\n")
    
    if not backups:
        print("No backups found.")
        return
    
    print(f"{'#':<4} {'Timestamp':<20} {'Type':<10} {'Filename':<40}")
    print("-" * 80)
    
    for i, backup in enumerate(backups, 1):
        timestamp = backup['timestamp'][:19]  # Trim to seconds
        backup_type = backup['backup_type']
        filename = backup['filename']
        
        print(f"{i:<4} {timestamp:<20} {backup_type:<10} {filename:<40}")
    
    print()

async def list_backups(args):
    """List available backups."""
    manager = get_backup_manager()
    
    if args.category == 'all':
        # List both database and config backups
        db_backups = await manager.list_backups('database')
        print_backup_list(db_backups, 'database')
        
        config_backups = await manager.list_backups('config_ea')
        print_backup_list(config_backups, 'config_ea')
    else:
        backups = await manager.list_backups(args.category)
        print_backup_list(backups, args.category)

async def backup_database(args):
    """Perform database backup."""
    print("Starting database backup...")
    
    manager = get_backup_manager()
    result = await manager.backup_database()
    
    if result['status'] == 'success':
        print(f"\n✓ Database backup completed successfully")
        print(f"  Filename: {result['filename']}")
        print(f"  Type: {result['backup_type']}")
        print(f"  Size: {result['size_bytes'] / 1024 / 1024:.2f} MB")
        print(f"  Remote path: {result['remote_path']}")
    else:
        print(f"\n✗ Database backup failed")
        print(f"  Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)

async def backup_config(args):
    """Perform configuration and EA backup."""
    print("Starting configuration and EA backup...")
    
    manager = get_backup_manager()
    result = await manager.backup_config_and_ea()
    
    if result['status'] == 'success':
        print(f"\n✓ Configuration backup completed successfully")
        print(f"  Filename: {result['filename']}")
        print(f"  Type: {result['backup_type']}")
        print(f"  Size: {result['size_bytes'] / 1024 / 1024:.2f} MB")
        print(f"  Remote path: {result['remote_path']}")
    else:
        print(f"\n✗ Configuration backup failed")
        print(f"  Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)

async def restore_database(args):
    """Restore database from backup."""
    manager = get_backup_manager()
    
    if args.backup_path:
        # Use specified backup path
        backup_path = args.backup_path
    else:
        # List backups and let user choose
        backups = await manager.list_backups('database')
        
        if not backups:
            print("No backups found.")
            sys.exit(1)
        
        print_backup_list(backups, 'database')
        
        try:
            choice = int(input("\nEnter backup number to restore (0 to cancel): "))
            if choice == 0:
                print("Restore cancelled.")
                return
            
            if choice < 1 or choice > len(backups):
                print("Invalid choice.")
                sys.exit(1)
            
            backup_path = backups[choice - 1]['remote_path']
        except (ValueError, KeyboardInterrupt):
            print("\nRestore cancelled.")
            return
    
    # Confirm restore
    if not args.yes:
        confirm = input(f"\nRestore database from {backup_path}? This will overwrite current data. (yes/no): ")
        if confirm.lower() != 'yes':
            print("Restore cancelled.")
            return
    
    print(f"\nRestoring database from {backup_path}...")
    
    result = await manager.restore_database(backup_path, args.target_db)
    
    if result['status'] == 'success':
        print(f"\n✓ Database restored successfully")
        print(f"  Target database: {result['target_db']}")
    else:
        print(f"\n✗ Database restore failed")
        print(f"  Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)

async def verify_backup(args):
    """Verify backup integrity."""
    manager = get_backup_manager()
    
    if args.backup_path:
        backup_path = args.backup_path
    else:
        # Verify latest backup
        print("Verifying latest backup...")
        result = await manager.verify_latest_backup()
        
        if result['status'] == 'passed':
            print(f"\n✓ Backup verification passed")
            print(f"  Checks performed: {len(result['checks'])}")
            
            if args.verbose:
                print("\nCheck details:")
                for check, value in result['checks'].items():
                    print(f"  {check}: {value}")
        else:
            print(f"\n✗ Backup verification failed")
            print(f"  Errors: {result.get('errors', [])}")
            
            if args.verbose and 'checks' in result:
                print("\nCheck details:")
                for check, value in result['checks'].items():
                    print(f"  {check}: {value}")
            
            sys.exit(1)
        
        return
    
    # Verify specific backup
    print(f"Verifying backup: {backup_path}...")
    
    result = await manager.verifier.verify_backup(backup_path)
    
    if result['status'] == 'passed':
        print(f"\n✓ Backup verification passed")
        print(f"  Checks performed: {len(result['checks'])}")
        
        if args.verbose:
            print("\nCheck details:")
            for check, value in result['checks'].items():
                print(f"  {check}: {value}")
    else:
        print(f"\n✗ Backup verification failed")
        print(f"  Errors: {result.get('errors', [])}")
        
        if args.verbose and 'checks' in result:
            print("\nCheck details:")
            for check, value in result['checks'].items():
                print(f"  {check}: {value}")
        
        sys.exit(1)

async def cleanup_backups(args):
    """Clean up old backups."""
    print("Cleaning up old backups...")
    
    manager = get_backup_manager()
    result = await manager.cleanup_old_backups()
    
    if result['status'] == 'success':
        print(f"\n✓ Backup cleanup completed")
        print(f"  Deleted counts:")
        for backup_type, count in result['deleted_counts'].items():
            print(f"    {backup_type}: {count}")
    else:
        print(f"\n✗ Backup cleanup failed")
        print(f"  Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)

def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description='OpenFi Backup Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available backups')
    list_parser.add_argument(
        'category',
        choices=['database', 'config_ea', 'all'],
        default='all',
        nargs='?',
        help='Backup category to list'
    )
    
    # Backup database command
    backup_db_parser = subparsers.add_parser('backup-db', help='Backup database')
    
    # Backup config command
    backup_config_parser = subparsers.add_parser('backup-config', help='Backup configuration and EA files')
    
    # Restore database command
    restore_parser = subparsers.add_parser('restore', help='Restore database from backup')
    restore_parser.add_argument(
        '--backup-path',
        help='Specific backup path to restore (optional)'
    )
    restore_parser.add_argument(
        '--target-db',
        help='Target database name (optional, defaults to main database)'
    )
    restore_parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify backup integrity')
    verify_parser.add_argument(
        '--backup-path',
        help='Specific backup path to verify (optional, defaults to latest)'
    )
    verify_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed check results'
    )
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old backups')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    if args.command == 'list':
        asyncio.run(list_backups(args))
    elif args.command == 'backup-db':
        asyncio.run(backup_database(args))
    elif args.command == 'backup-config':
        asyncio.run(backup_config(args))
    elif args.command == 'restore':
        asyncio.run(restore_database(args))
    elif args.command == 'verify':
        asyncio.run(verify_backup(args))
    elif args.command == 'cleanup':
        asyncio.run(cleanup_backups(args))

if __name__ == '__main__':
    main()

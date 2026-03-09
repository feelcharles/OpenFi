#!/usr/bin/env python3
"""Verify Alembic migration chain integrity"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def verify_migration_chain():
    """Verify that the migration chain is valid"""
    migrations_dir = Path(__file__).parent.parent / "alembic" / "versions"
    
    migrations = {}
    
    # Parse all migration files
    for file in migrations_dir.glob("*.py"):
        if file.name == "__init__.py":
            continue
            
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extract revision and down_revision
        revision = None
        down_revision = None
        
        for line in content.split('\n'):
            if line.startswith('revision'):
                revision = line.split('=')[1].strip().strip("'\"")
            elif line.startswith('down_revision'):
                down_val = line.split('=')[1].strip()
                if down_val != 'None':
                    down_revision = down_val.strip("'\"")
        
        if revision:
            migrations[revision] = {
                'file': file.name,
                'down_revision': down_revision
            }
    
    print("Migration Chain Analysis")
    print("=" * 60)
    
    # Find the root (migration with no down_revision)
    roots = [rev for rev, info in migrations.items() if info['down_revision'] is None]
    
    if len(roots) == 0:
        print("❌ ERROR: No root migration found!")
        return False
    elif len(roots) > 1:
        print(f"❌ ERROR: Multiple root migrations found: {roots}")
        return False
    
    print(f"✓ Root migration: {roots[0]}")
    
    # Build the chain
    current = roots[0]
    chain = [current]
    visited = {current}
    
    while True:
        # Find next migration
        next_migrations = [
            rev for rev, info in migrations.items() 
            if info['down_revision'] == current
        ]
        
        if len(next_migrations) == 0:
            break
        elif len(next_migrations) > 1:
            print(f"\n❌ ERROR: Multiple migrations depend on '{current}': {next_migrations}")
            print("This creates a branch in the migration chain!")
            return False
        
        current = next_migrations[0]
        if current in visited:
            print(f"\n❌ ERROR: Circular dependency detected at '{current}'!")
            return False
            
        chain.append(current)
        visited.add(current)
    
    # Check for orphaned migrations
    orphaned = set(migrations.keys()) - visited
    if orphaned:
        print(f"\n❌ ERROR: Orphaned migrations found: {orphaned}")
        for orphan in orphaned:
            info = migrations[orphan]
            print(f"  - {orphan} (depends on: {info['down_revision']})")
        return False
    
    # Print the chain
    print(f"\n✓ Valid linear migration chain with {len(chain)} migrations:")
    print()
    for i, rev in enumerate(chain, 1):
        info = migrations[rev]
        print(f"  {i}. {rev}")
        print(f"     File: {info['file']}")
        if i < len(chain):
            print("     ↓")
    
    print("\n" + "=" * 60)
    print("✓ Migration chain is valid!")
    return True

if __name__ == "__main__":
    success = verify_migration_chain()
    sys.exit(0 if success else 1)

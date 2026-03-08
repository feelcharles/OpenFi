#!/usr/bin/env python3
"""
Standalone script for restoring WAL files.
Called by PostgreSQL restore_command during recovery.

Usage: python restore_wal.py <wal_filename> <restore_path>
"""

import sys
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    if len(sys.argv) != 3:
        print("Usage: python restore_wal.py <wal_filename> <restore_path>")
        sys.exit(1)
    
    wal_filename = sys.argv[1]
    restore_path = sys.argv[2]
    
    from system_core.backup.wal_archiver import restore_wal_standalone
    
    exit_code = await restore_wal_standalone(wal_filename, restore_path)
    sys.exit(exit_code)

if __name__ == '__main__':
    asyncio.run(main())

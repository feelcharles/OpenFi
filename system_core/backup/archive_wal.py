#!/usr/bin/env python3
"""
Standalone script for archiving WAL files.
Called by PostgreSQL archive_command.

Usage: python archive_wal.py <wal_path> <wal_filename>
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
        print("Usage: python archive_wal.py <wal_path> <wal_filename>")
        sys.exit(1)
    
    wal_path = sys.argv[1]
    wal_filename = sys.argv[2]
    
    from system_core.backup.wal_archiver import archive_wal_standalone
    
    exit_code = await archive_wal_standalone(wal_path, wal_filename)
    sys.exit(exit_code)

if __name__ == '__main__':
    asyncio.run(main())

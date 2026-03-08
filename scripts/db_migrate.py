#!/usr/bin/env python
"""
Database migration helper script.

This script provides convenient commands for managing database migrations.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from system_core.database.client import get_db_client
from system_core.config.settings import get_settings

async def check_connection():
    """Check database connection."""
    print("Checking database connection...")
    
    db_client = get_db_client()
    
    try:
        is_healthy = await db_client.health_check()
        
        if is_healthy:
            print("✓ Database connection successful")
            return True
        else:
            print("✗ Database connection failed")
            return False
    finally:
        await db_client.close()

async def init_database():
    """Initialize database and run migrations."""
    print("Initializing database...")
    
    # Check connection first
    if not await check_connection():
        print("\nError: Cannot connect to database. Please check your configuration.")
        print("\nRequired environment variables:")
        print("  DB_USER")
        print("  DB_PASSWORD")
        print("  DB_HOST")
        print("  DB_PORT")
        print("  DB_NAME")
        return False
    
    # Run migrations
    print("\nRunning migrations...")
    os.system("python -m alembic upgrade head")
    
    print("\n✓ Database initialized successfully")
    return True

async def show_info():
    """Show database configuration info."""
    settings = get_settings()
    
    print("Database Configuration:")
    print(f"  Host: {settings.db_host}")
    print(f"  Port: {settings.db_port}")
    print(f"  Database: {settings.db_name}")
    print(f"  User: {settings.db_user}")
    print(f"  URL: {settings.database_url.replace(settings.db_password, '***')}")

def show_help():
    """Show help message."""
    print("""
Database Migration Helper

Usage:
    python scripts/db_migrate.py [command]

Commands:
    check       Check database connection
    init        Initialize database and run migrations
    info        Show database configuration
    upgrade     Apply all pending migrations
    downgrade   Rollback one migration
    current     Show current migration version
    history     Show migration history
    help        Show this help message

Examples:
    python scripts/db_migrate.py check
    python scripts/db_migrate.py init
    python scripts/db_migrate.py upgrade
""")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "check":
        asyncio.run(check_connection())
    elif command == "init":
        asyncio.run(init_database())
    elif command == "info":
        asyncio.run(show_info())
    elif command == "upgrade":
        os.system("python -m alembic upgrade head")
    elif command == "downgrade":
        os.system("python -m alembic downgrade -1")
    elif command == "current":
        os.system("python -m alembic current")
    elif command == "history":
        os.system("python -m alembic history")
    elif command == "help":
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()

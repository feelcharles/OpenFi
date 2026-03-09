#!/usr/bin/env python3
"""Test database connection and migration readiness"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import psycopg2

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

def test_connection():
    """Test PostgreSQL connection"""
    db_config = {
        'user': os.getenv('DB_USER', 'openfi'),
        'password': os.getenv('DB_PASSWORD', 'openfi_password'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'openfi')
    }
    
    print("Database Connection Test")
    print("=" * 60)
    print(f"Host: {db_config['host']}:{db_config['port']}")
    print(f"Database: {db_config['database']}")
    print(f"User: {db_config['user']}")
    print()
    
    try:
        # Try to connect
        print("Attempting to connect...")
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✓ Connected successfully!")
        print(f"✓ PostgreSQL version: {version.split(',')[0]}")
        
        # Check if alembic_version table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            );
        """)
        has_alembic = cursor.fetchone()[0]
        
        if has_alembic:
            cursor.execute("SELECT version_num FROM alembic_version;")
            result = cursor.fetchone()
            if result:
                print(f"✓ Current migration version: {result[0]}")
            else:
                print("⚠ alembic_version table exists but is empty")
        else:
            print("ℹ No migrations applied yet (alembic_version table not found)")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ Database is ready for migrations!")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"✗ Connection failed: {e}")
        print("\nPossible issues:")
        print("  1. PostgreSQL is not running")
        print("  2. Database does not exist (create it first)")
        print("  3. Wrong credentials in .env file")
        print("  4. Firewall blocking connection")
        print("\nTo create the database, run:")
        print(f"  psql -U postgres -c \"CREATE DATABASE {db_config['database']};\"")
        print(f"  psql -U postgres -c \"CREATE USER {db_config['user']} WITH PASSWORD '{db_config['password']}';\"")
        print(f"  psql -U postgres -c \"GRANT ALL PRIVILEGES ON DATABASE {db_config['database']} TO {db_config['user']};\"")
        return False
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

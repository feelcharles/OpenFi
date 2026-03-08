#!/usr/bin/env python3
"""
Deployment Check Script

This script validates the environment configuration and dependencies
before deploying to VPS.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_python_version():
    """Check Python version >= 3.10"""
    print("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"❌ Python 3.10+ required, found {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_env_file():
    """Check if .env file exists"""
    print("\nChecking .env file...")
    env_file = project_root / ".env"
    if not env_file.exists():
        print("❌ .env file not found")
        print("   Please copy .env.example to .env and configure it")
        return False
    print("✅ .env file exists")
    return True

def check_required_env_vars():
    """Check required environment variables"""
    print("\nChecking required environment variables...")
    
    # Load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv not installed, skipping .env loading")
    
    required_vars = {
        'DB_USER': 'Database user',
        'DB_PASSWORD': 'Database password',
        'DB_HOST': 'Database host',
        'DB_PORT': 'Database port',
        'DB_NAME': 'Database name',
        'SECRET_KEY': 'JWT secret key (min 32 chars)',
        'ENCRYPTION_KEY': 'Encryption key (min 32 chars)',
    }
    
    missing = []
    weak_keys = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing.append(f"{var} ({description})")
        elif var in ['SECRET_KEY', 'ENCRYPTION_KEY']:
            if len(value) < 32:
                weak_keys.append(f"{var} (current: {len(value)} chars, required: 32+ chars)")
            elif value.startswith('dev-') or value.startswith('your-'):
                weak_keys.append(f"{var} (using default/example value)")
    
    if missing:
        print(f"❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        return False
    
    if weak_keys:
        print(f"⚠️  Weak or default keys detected:")
        for key in weak_keys:
            print(f"   - {key}")
        print("   Please generate strong random keys for production")
    
    print("✅ All required environment variables are set")
    return True

def check_dependencies():
    """Check if all required packages are installed"""
    print("\nChecking dependencies...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'pydantic',
        'pydantic_settings',
        'sqlalchemy',
        'alembic',
        'asyncpg',
        'redis',
        'structlog',
        'yaml',
        'cryptography',
        'pyjwt',
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing required packages:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\n   Run: pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_directories():
    """Check if required directories exist"""
    print("\nChecking required directories...")
    
    required_dirs = [
        'logs',
        'ea',
        'ea/logs',
        'config',
        'alembic/versions',
    ]
    
    missing = []
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if not full_path.exists():
            missing.append(dir_path)
            # Try to create it
            try:
                full_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ Created directory: {dir_path}")
            except Exception as e:
                print(f"❌ Failed to create directory {dir_path}: {e}")
    
    if not missing:
        print("✅ All required directories exist")
    
    return True

def check_config_files():
    """Check if required configuration files exist"""
    print("\nChecking configuration files...")
    
    required_files = [
        'config/bot_commands.yaml',
        'config/ea_config.yaml',
        'config/llm_config.yaml',
        'config/push_config.yaml',
        'alembic.ini',
    ]
    
    missing = []
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing.append(file_path)
    
    if missing:
        print(f"⚠️  Missing configuration files:")
        for file in missing:
            print(f"   - {file}")
        print("   These files may be optional or need to be created")
    else:
        print("✅ All configuration files exist")
    
    return True

def check_database_connection():
    """Check database connection"""
    print("\nChecking database connection...")
    
    try:
        from system_core.config.settings import get_settings
        settings = get_settings()
        
        print(f"   Database: {settings.db_host}:{settings.db_port}/{settings.db_name}")
        print(f"   User: {settings.db_user}")
        
        # Try to connect
        from sqlalchemy import create_engine, text
        engine = create_engine(
            f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}",
            pool_pre_ping=True
        )
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        print("✅ Database connection successful")
        return True
        
    except ImportError as e:
        print(f"⚠️  Cannot import settings module: {e}")
        return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Please ensure PostgreSQL is running and credentials are correct")
        return False

def check_redis_connection():
    """Check Redis connection"""
    print("\nChecking Redis connection...")
    
    try:
        from system_core.config.settings import get_settings
        import redis
        
        settings = get_settings()
        print(f"   Redis URL: {settings.redis_url}")
        
        # Parse Redis URL
        r = redis.from_url(settings.redis_url)
        r.ping()
        
        print("✅ Redis connection successful")
        return True
        
    except ImportError as e:
        print(f"⚠️  Cannot import required modules: {e}")
        return False
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Please ensure Redis is running")
        return False

def check_alembic_migrations():
    """Check Alembic migrations"""
    print("\nChecking Alembic migrations...")
    
    migrations_dir = project_root / "alembic" / "versions"
    if not migrations_dir.exists():
        print("❌ Alembic versions directory not found")
        return False
    
    migration_files = list(migrations_dir.glob("*.py"))
    migration_files = [f for f in migration_files if f.name != "__pycache__"]
    
    if not migration_files:
        print("❌ No migration files found")
        return False
    
    print(f"✅ Found {len(migration_files)} migration file(s):")
    for f in migration_files:
        print(f"   - {f.name}")
    
    return True

def main():
    """Run all checks"""
    print("=" * 60)
    print("OpenFi - Deployment Check")
    print("=" * 60)
    
    checks = [
        ("Python Version", check_python_version),
        (".env File", check_env_file),
        ("Environment Variables", check_required_env_vars),
        ("Dependencies", check_dependencies),
        ("Directories", check_directories),
        ("Configuration Files", check_config_files),
        ("Alembic Migrations", check_alembic_migrations),
        ("Database Connection", check_database_connection),
        ("Redis Connection", check_redis_connection),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Error during {name} check: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Ready for deployment.")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

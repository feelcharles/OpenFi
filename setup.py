"""Setup script for OpenFi."""

from setuptools import setup, find_packages
from setuptools.command.install import install
import subprocess
import sys
import os

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        print("\n" + "="*50)
        print("OpenFi Installation Complete!")
        print("="*50)
        print("\nNext steps:")
        print("1. Configure: cp .env.example .env")
        print("2. Edit .env with your settings")
        print("3. Start: python -m system_core.web_backend.app")
        print("\nOr use quick start:")
        print("  Windows: start.bat")
        print("  Linux/Mac: ./start.sh")
        print("\nAccess at: http://localhost:8686/app")
        print("="*50 + "\n")

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openfi",
    version="1.0.0",
    author="OpenFi Team",
    author_email="feelcharles@users.noreply.github.com",
    description="AI-Powered Quantitative Trading System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/feelcharles/OpenFi",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "docs"]),
    python_requires=">=3.8",
    install_requires=[
        # Core Web Framework
        "fastapi>=0.135.1",
        "uvicorn[standard]>=0.41.0",
        "pydantic>=2.10.5",
        "pydantic-settings>=2.7.1",
        "python-multipart>=0.0.18",
        
        # Async Support
        "aiohttp>=3.11.11",
        "aiofiles>=24.1.0",
        "aiodns>=3.2.0",
        
        # Database
        "sqlalchemy>=2.0.36",
        "asyncpg>=0.30.0",
        "aiosqlite>=0.20.0",
        "alembic>=1.14.0",
        "psycopg2-binary>=2.9.10",
        
        # Redis & Caching
        "redis>=5.2.1",
        "hiredis>=3.0.0",
        
        # Configuration
        "python-dotenv>=1.0.1",
        "pyyaml>=6.0.2",
        "watchdog>=6.0.0",
        
        # Logging & Monitoring
        "structlog>=24.4.0",
        "python-json-logger>=3.2.1",
        "prometheus-client>=0.21.0",
        
        # Scheduling
        "apscheduler>=3.10.4",
        "croniter>=5.0.1",
        "celery>=5.4.0",
        
        # LLM Integration
        "openai>=1.59.5",
        "anthropic>=0.42.0",
        "tiktoken>=0.8.0",
        
        # HTTP Clients
        "httpx>=0.28.1",
        "requests>=2.32.3",
        "websockets>=14.1",
        
        # Data Processing
        "pandas>=2.2.3",
        "numpy>=2.2.1",
        "python-dateutil>=2.9.0",
        "pytz>=2024.2",
        
        # Security
        "cryptography>=44.0.0",
        "pyjwt>=2.10.1",
        "passlib[bcrypt]>=1.7.4",
        "python-jose[cryptography]>=3.3.0",
        "bcrypt>=4.2.1",
        
        # Push Notifications
        "python-telegram-bot>=21.9",
        "discord.py>=2.4.0",
        "aiosmtplib>=3.0.2",
        
        # Data Fetching
        "beautifulsoup4>=4.12.3",
        "lxml>=5.3.0",
        "feedparser>=6.0.11",
        
        # Utilities
        "click>=8.1.8",
        "rich>=13.9.4",
        "tqdm>=4.67.1",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.4",
            "pytest-asyncio>=0.24.0",
            "pytest-cov>=6.0.0",
            "pytest-mock>=3.14.0",
            "hypothesis>=6.122.3",
            "faker>=33.1.0",
            "black>=24.10.0",
            "flake8>=7.1.1",
            "mypy>=1.14.0",
            "isort>=5.13.2",
            "pylint>=3.3.2",
            "safety>=3.2.11",
            "bandit>=1.8.0",
        ],
    },
    entry_points={
        'console_scripts': [
            'openfi=system_core.web_backend.app:main',
            'openfi-migrate=scripts.db_migrate:main',
            'openfi-backup=scripts.backup_cli:main',
            'openfi-check=full_system_check:main',
        ],
    },
    cmdclass={
        'install': PostInstallCommand,
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    keywords="trading quantitative-trading ai llm multi-agent fastapi",
    project_urls={
        "Bug Reports": "https://github.com/feelcharles/OpenFi/issues",
        "Source": "https://github.com/feelcharles/OpenFi",
        "Documentation": "https://github.com/feelcharles/OpenFi/blob/main/README.md",
    },
)

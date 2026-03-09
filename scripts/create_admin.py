#!/usr/bin/env python3
"""Create default admin user"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import psycopg2
from datetime import datetime
import bcrypt

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_admin():
    """Create default admin user"""
    db_config = {
        'user': os.getenv('DB_USER', 'openfi'),
        'password': os.getenv('DB_PASSWORD', 'openfi_password'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'openfi')
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Check if admin user already exists
        cursor.execute("SELECT id FROM users WHERE username = 'admin';")
        existing_admin = cursor.fetchone()
        
        if existing_admin:
            print("管理员账户已存在")
            cursor.close()
            conn.close()
            return True
        
        # Create admin user
        admin_password_hash = hash_password('admin123')
        now = datetime.utcnow()
        
        cursor.execute("""
            INSERT INTO users (
                username, email, password_hash, role, 
                must_change_password, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            );
        """, (
            'admin',
            'admin@openfi.local',
            admin_password_hash,
            'admin',
            True,
            now
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("默认管理员账户创建成功")
        return True
        
    except Exception as e:
        print(f"创建管理员账户失败: {e}")
        return False

if __name__ == "__main__":
    success = create_admin()
    sys.exit(0 if success else 1)

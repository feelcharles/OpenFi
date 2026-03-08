# Authentication Module

This module provides comprehensive authentication and authorization for OpenFi Lite.

## Features

- **JWT Authentication**: RS256 algorithm with RSA public/private key pairs
- **Password Hashing**: bcrypt with cost factor 12
- **Rate Limiting**: IP-based rate limiting (5 attempts per 15 minutes)
- **Role-Based Access Control (RBAC)**: Three roles with hierarchical permissions
- **Automatic IP Blocking**: 30-minute block after 5 failed login attempts

## Components

### 1. JWT Handler (`jwt_handler.py`)

Manages JWT token generation, validation, and refresh operations.

```python
from system_core.auth import create_access_token, verify_token

# Create token
token = create_access_token(
    user_id="user-uuid",
    username="john_doe",
    role="trader"
)

# Verify token
payload = verify_token(token)
print(payload["sub"])  # user-uuid
```

**Key Features:**
- RS256 algorithm with RSA key pairs
- Automatic key generation if not exists
- 24-hour token expiration (configurable)
- Token refresh support

**Configuration:**
- `JWT_PRIVATE_KEY_PATH`: Path to RSA private key (default: `config/keys/jwt_private.pem`)
- `JWT_PUBLIC_KEY_PATH`: Path to RSA public key (default: `config/keys/jwt_public.pem`)

### 2. Password Hashing (`password.py`)

Secure password hashing using bcrypt.

```python
from system_core.auth import hash_password, verify_password

# Hash password
hashed = hash_password("SecurePassword123!")

# Verify password
is_valid = verify_password("SecurePassword123!", hashed)
```

**Key Features:**
- bcrypt with cost factor 12
- Automatic salt generation
- Secure password verification

### 3. Role-Based Access Control (`rbac.py`)

Three-tier role hierarchy with permission checking.

```python
from system_core.auth import Role, check_permission

# Check if user has required role
has_access = check_permission("trader", Role.TRADER)  # True
has_admin = check_permission("trader", Role.ADMIN)    # False
```

**Roles:**
- **ADMIN**: Full system access (all operations)
- **TRADER**: Trading operations (view + trade execution)
- **VIEWER**: Read-only access (view data only)

**Hierarchy:** ADMIN > TRADER > VIEWER

### 4. Rate Limiter (`rate_limiter.py`)

IP-based rate limiting to prevent brute force attacks.

```python
from system_core.auth import check_rate_limit

# In FastAPI endpoint
@app.post("/api/auth/login")
async def login(request: Request):
    await check_rate_limit(request)
    # ... login logic
```

**Configuration:**
- Max attempts: 5 per 15 minutes
- Block duration: 30 minutes after exceeding limit
- Automatic cleanup of old attempts

**Features:**
- Sliding window rate limiting
- X-Forwarded-For header support (for proxied requests)
- Per-IP tracking
- Automatic unblocking after timeout

### 5. Middleware (`middleware.py`)

FastAPI dependencies for authentication and authorization.

```python
from fastapi import Depends
from system_core.auth import get_current_user, require_role, Role

# Require authentication
@app.get("/api/profile")
async def get_profile(current_user = Depends(get_current_user)):
    return {"user_id": current_user.user_id}

# Require specific role
@app.get("/api/admin/users", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_users():
    return {"users": [...]}

# Convenience functions
@app.post("/api/trades", dependencies=[Depends(require_trader)])
async def create_trade():
    return {"status": "created"}
```

**Dependencies:**
- `get_current_user`: Extract and validate current user from JWT
- `require_role(role)`: Require minimum role level
- `require_admin`: Require admin role
- `require_trader`: Require trader role or higher

### 6. API Endpoints (`api.py`)

Authentication REST API endpoints.

```python
from fastapi import FastAPI
from system_core.auth import auth_router

app = FastAPI()
app.include_router(auth_router)
```

**Endpoints:**

#### POST /api/auth/login
Login with username and password.

**Request:**
```json
{
  "username": "john_doe",
  "password": "SecurePassword123!"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user_id": "user-uuid",
  "username": "john_doe",
  "role": "trader"
}
```

**Rate Limiting:** 5 attempts per 15 minutes per IP

#### POST /api/auth/refresh
Refresh JWT token with extended expiration.

**Request:**
```json
{
  "token": "eyJhbGc..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user_id": "user-uuid",
  "username": "john_doe",
  "role": "trader"
}
```

#### GET /api/auth/me
Get current user information from token.

**Headers:**
```
Authorization: Bearer eyJhbGc...
```

**Response:**
```json
{
  "user_id": "user-uuid",
  "username": "john_doe",
  "email": "john@example.com",
  "role": "trader",
  "timezone": "Asia/Shanghai",
  "created_at": "2024-01-01T00:00:00Z"
}
```

## Setup

### 1. Generate RSA Key Pair

The system automatically generates RSA keys on first run. Keys are stored in:
- `config/keys/jwt_private.pem` (private key)
- `config/keys/jwt_public.pem` (public key)

**Manual generation (optional):**
```bash
mkdir -p config/keys
openssl genrsa -out config/keys/jwt_private.pem 2048
openssl rsa -in config/keys/jwt_private.pem -pubout -out config/keys/jwt_public.pem
```

### 2. Environment Variables

```bash
# Optional: Override default key paths
JWT_PRIVATE_KEY_PATH=config/keys/jwt_private.pem
JWT_PUBLIC_KEY_PATH=config/keys/jwt_public.pem
```

### 3. Database Setup

Ensure the User model has the following fields:
- `id` (UUID)
- `username` (String)
- `email` (String)
- `password_hash` (String)
- `role` (String: admin, trader, viewer)

## Usage Examples

### Complete Authentication Flow

```python
from fastapi import FastAPI, Depends, HTTPException
from system_core.auth import (
    auth_router,
    get_current_user,
    require_role,
    Role,
    hash_password
)

app = FastAPI()

# Include auth router
app.include_router(auth_router)

# Public endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to OpenFi Lite"}

# Authenticated endpoint
@app.get("/api/profile")
async def get_profile(current_user = Depends(get_current_user)):
    return {
        "user_id": str(current_user.user_id),
        "username": current_user.username,
        "role": current_user.role
    }

# Role-protected endpoint
@app.get("/api/admin/settings", dependencies=[Depends(require_role(Role.ADMIN))])
async def get_admin_settings():
    return {"settings": {...}}

# Trader-only endpoint
@app.post("/api/trades")
async def create_trade(
    trade_data: dict,
    current_user = Depends(require_trader)
):
    return {"trade_id": "...", "user_id": str(current_user.user_id)}
```

### User Registration

```python
from system_core.auth import hash_password
from system_core.database.models import User

@app.post("/api/users")
async def create_user(username: str, password: str, email: str, db: Session):
    # Hash password
    password_hash = hash_password(password)
    
    # Create user
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        role="trader"  # Default role
    )
    
    db.add(user)
    db.commit()
    
    return {"user_id": str(user.id)}
```

### Client-Side Usage

```javascript
// Login
const response = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'john_doe',
    password: 'SecurePassword123!'
  })
});

const { access_token } = await response.json();

// Store token
localStorage.setItem('token', access_token);

// Use token in requests
const profileResponse = await fetch('/api/profile', {
  headers: {
    'Authorization': `Bearer ${access_token}`
  }
});

// Refresh token
const refreshResponse = await fetch('/api/auth/refresh', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ token: access_token })
});
```

## Security Considerations

1. **Key Management**: Keep private keys secure and never commit to version control
2. **HTTPS**: Always use HTTPS in production to protect tokens in transit
3. **Token Storage**: Store tokens securely on client side (HttpOnly cookies recommended)
4. **Rate Limiting**: Monitor rate limit logs for potential attacks
5. **Password Policy**: Enforce strong password requirements in user registration
6. **Token Expiration**: 24-hour expiration balances security and user experience
7. **Audit Logging**: All authentication attempts are logged for security monitoring

## Testing

Run the authentication tests:

```bash
pytest tests/test_auth.py -v
```

Test coverage includes:
- JWT token generation and validation
- Password hashing and verification
- Role-based permission checking
- Rate limiting behavior
- Token refresh functionality
- Integration tests for complete auth flow

## Troubleshooting

### "Private key not found"
- Ensure `config/keys/` directory exists
- System will auto-generate keys on first run
- Check file permissions

### "Invalid or expired token"
- Token may have expired (24-hour lifetime)
- Use refresh endpoint to get new token
- Verify token format: `Bearer <token>`

### "Too many login attempts"
- IP is temporarily blocked (30 minutes)
- Wait for block to expire
- Check rate limiter logs for details

### "Insufficient permissions"
- User role doesn't meet endpoint requirements
- Check user role in database
- Verify role hierarchy: ADMIN > TRADER > VIEWER

## Requirements

- Python 3.11+
- FastAPI 0.109.0+
- PyJWT 2.8.0+
- passlib[bcrypt] 1.7.4+
- cryptography 42.0.0+
- SQLAlchemy 2.0.25+

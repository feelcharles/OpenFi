"""
FastAPI application for OpenFi Lite Web Backend.

This module creates and configures the FastAPI application with all routes,
middleware, and event handlers.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from system_core.web_backend import (
    web_api_router,
    websocket_router,
    RateLimitMiddleware,
    setup_cors,
    event_broadcaster
)
from system_core.web_backend.websocket_manager import ws_manager
from system_core.web_backend.audit_api import router as audit_router
from system_core.web_backend.agent_api import router as agent_router
from system_core.web_backend.monitoring_api import router as monitoring_router
from system_core.web_backend.account_api import router as account_router
from system_core.auth.api import router as auth_router
from system_core.user_center.api import router as user_center_router
from system_core.enhancement.tools_api import router as tools_router
from system_core.config import get_logger, get_settings
from system_core.core.idempotency import IdempotencyMiddleware, idempotency_middleware
from system_core.security import (
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware
)

logger = get_logger(__name__)

# Global idempotency middleware instance
idempotency_handler: IdempotencyMiddleware = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    global idempotency_handler
    
    # Startup
    logger.info("web_backend_starting")
    
    # Initialize idempotency middleware (optional, requires Redis)
    settings = get_settings()
    if settings.redis_url:
        idempotency_handler = IdempotencyMiddleware(
            redis_url=settings.redis_url,
            password=settings.redis_password,
            ttl_seconds=86400  # 24 hours
        )
        await idempotency_handler.connect()
        if idempotency_handler.redis_client:
            logger.info("idempotency_middleware_initialized")
        else:
            logger.warning("idempotency_middleware_disabled_no_redis")
    else:
        logger.info("idempotency_middleware_disabled_no_redis_url")
    
    # Start WebSocket cleanup task
    await ws_manager.start_cleanup_task()
    logger.info("websocket_cleanup_task_started")
    
    # Initialize event broadcaster
    # Note: Event bus should be set via event_broadcaster.set_event_bus(event_bus) in main
    # For now, just start the cleanup task
    logger.info("event_broadcaster_ready")
    
    logger.info("web_backend_started")
    
    yield
    
    # Shutdown
    logger.info("web_backend_shutting_down")
    
    # Stop event broadcaster
    await event_broadcaster.stop()
    
    # Stop WebSocket cleanup task
    await ws_manager.stop_cleanup_task()
    
    # Disconnect idempotency middleware
    if idempotency_handler:
        await idempotency_handler.disconnect()
    
    logger.info("web_backend_shutdown_complete")

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    settings = get_settings()
    
    app = FastAPI(
        title="OpenFi API",
        description="""
# OpenFi API

AI-driven financial information processing and quantitative trading assistance system.

## Features

- **Multi-Source Data Acquisition**: Fetch data from economic calendars, market data APIs, news sources, and social media
- **AI-Powered Analysis**: LLM-based information analysis, fact-checking, and value assessment
- **Intelligent Notifications**: Multi-channel push notifications (Telegram, Discord, Email, etc.)
- **Automated Trading**: Generate and execute trading signals with comprehensive risk management
- **Real-Time Updates**: WebSocket support for live dashboard updates
- **Configuration Management**: Hot-reload configuration system

## Authentication

Most endpoints require JWT authentication. Include the JWT token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

Obtain a token by calling `POST /api/auth/login` with your credentials.

## Rate Limiting

API requests are rate-limited to 100 requests per minute per IP address.

## Versioning

Current API version: v1 (prefix: `/api/v1/`)
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",  # Swagger UI
        redoc_url="/redoc",  # ReDoc
        openapi_url="/openapi.json",  # OpenAPI schema
        openapi_tags=[
            {
                "name": "authentication",
                "description": "User authentication and authorization endpoints"
            },
            {
                "name": "users",
                "description": "User management operations"
            },
            {
                "name": "ea_profiles",
                "description": "Expert Advisor (EA) profile management"
            },
            {
                "name": "web_backend",
                "description": "Dashboard metrics, system status, and configuration management"
            },
            {
                "name": "websocket",
                "description": "WebSocket endpoints for real-time updates"
            },
            {
                "name": "tools",
                "description": "External tool integration and execution"
            },
            {
                "name": "audit",
                "description": "Audit log and security event tracking"
            },
            {
                "name": "monitoring",
                "description": "Prometheus metrics and health checks"
            }
        ],
        contact={
            "name": "OpenFi Lite Support",
            "email": "support@OpenFi-lite.example.com"
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT"
        },
        servers=[
            {
                "url": "http://localhost:8686",
                "description": "Development server"
            },
            {
                "url": "https://api.OpenFi-lite.example.com",
                "description": "Production server"
            }
        ]
    )
    
    # Setup CORS
    setup_cors(app)
    
    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Add request size limit middleware
    app.add_middleware(RequestSizeLimitMiddleware, max_size=10 * 1024 * 1024)  # 10 MB
    
    # Add idempotency middleware
    @app.middleware("http")
    async def idempotency_middleware_handler(request, call_next):
        """Handle idempotency for all requests."""
        if idempotency_handler:
            return await idempotency_middleware(request, call_next, idempotency_handler)
        return await call_next(request)
    
    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
    
    # Include routers (注意：路由本身已经包含了完整的prefix，不要重复添加)
    app.include_router(auth_router)  # 已有 /api/v1/auth prefix
    app.include_router(user_center_router)  # 已有 /api/v1 prefix
    app.include_router(agent_router)  # 已有 /api/v1/agents prefix
    app.include_router(monitoring_router, prefix="/api/v1/monitoring")  # 监控 API
    app.include_router(account_router)  # 已有 /api/v1/accounts prefix
    app.include_router(web_api_router)  # 已有各自的prefix
    app.include_router(websocket_router)  # WebSocket路由
    app.include_router(tools_router)  # 已有 /api/v1/tools prefix
    app.include_router(audit_router)  # 已有 /api/v1/audit prefix
    
    # Mount static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Health check endpoint
    @app.get("/health", tags=["monitoring"])
    async def health_check():
        """
        Health check endpoint.
        
        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "service": "OpenFi-lite-web-backend",
            "version": "1.0.0"
        }
    
    # Main app endpoint
    @app.get("/app", tags=["web_backend"])
    async def app_page():
        """
        Serve main application HTML.
        
        Returns:
            Main application HTML page
        """
        app_path = Path(__file__).parent / "static" / "app.html"
        if app_path.exists():
            return FileResponse(app_path)
        return {"error": "Application not found"}
    
    # Dashboard endpoint (legacy)
    @app.get("/dashboard", tags=["web_backend"])
    async def dashboard():
        """
        Serve dashboard HTML.
        
        Returns:
            Dashboard HTML page
        """
        dashboard_path = Path(__file__).parent / "static" / "dashboard.html"
        if dashboard_path.exists():
            return FileResponse(dashboard_path)
        # Redirect to new app
        app_path = Path(__file__).parent / "static" / "app.html"
        if app_path.exists():
            return FileResponse(app_path)
        return {"error": "Dashboard not found"}
    
    # Root endpoint
    @app.get("/", tags=["web_backend"])
    async def root():
        """
        Root endpoint - Welcome page.
        
        Returns:
            Welcome HTML page
        """
        index_path = Path(__file__).parent / "static" / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        # Fallback to JSON response
        return {
            "service": "OpenFi API",
            "version": "1.0.0",
            "api_version": "v1",
            "app": "/app",
            "docs": "/docs",
            "redoc": "/redoc",
            "dashboard": "/dashboard",
            "health": "/health",
            "endpoints": {
                "authentication": "/api/v1/auth",
                "users": "/api/v1/users",
                "ea_profiles": "/api/v1/ea-profiles",
                "dashboard": "/api/v1/dashboard",
                "trades": "/api/v1/trades",
                "config": "/api/v1/config",
                "tools": "/api/v1/tools",
                "audit": "/api/v1/audit",
                "websocket": "/ws/notifications"
            }
        }
    
    logger.info("fastapi_app_created")
    
    return app

# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "system_core.web_backend.app:app",
        host=settings.web_backend_host,
        port=settings.web_backend_port,
        reload=True,
        log_level="info"
    )

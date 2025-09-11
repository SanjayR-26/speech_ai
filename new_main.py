"""
Main FastAPI application
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi_app.core.config import settings
from fastapi_app.core.database import check_connection, get_db, set_tenant_context
from fastapi_app.core.exceptions import BaseAPIException

# Import API routers
from fastapi_app.api import auth, tenants, organizations, calls, evaluation, users
from fastapi_app.api.evaluation import analysis_router
from fastapi_app.api.users import agent_router
from fastapi_app.api import coaching, command_center, analytics

# Import middleware
from fastapi_app.middleware import (
    auth_middleware, tenant_middleware, 
    rbac_middleware, audit_middleware
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format,
    force=True
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Check database connection
    if not check_connection():
        logger.error("Failed to connect to database")
        raise RuntimeError("Database connection failed")
    
    logger.info("Database connection established")
    
    # Initialize database (in production, use migrations)
    if settings.debug:
        from fastapi_app.core.database import init_db
        init_db()
        logger.info("Database tables initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    debug=settings.debug
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(audit_middleware.AuditMiddleware)
app.add_middleware(rbac_middleware.RBACMiddleware)
app.add_middleware(tenant_middleware.TenantContextMiddleware)
app.add_middleware(auth_middleware.AuthMiddleware)

# Exception handlers
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": {"error": str(exc)} if settings.debug else {}
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": "debug" if settings.debug else "production"
    }

# API version endpoint
@app.get("/api/version")
async def api_version():
    """Get API version information"""
    return {
        "api_version": "v1",
        "app_version": settings.app_version,
        "app_name": settings.app_name
    }

# Include routers
app.include_router(auth.router, prefix=f"{settings.api_prefix}")
app.include_router(tenants.router, prefix=f"{settings.api_prefix}")
app.include_router(organizations.router, prefix=f"{settings.api_prefix}")
app.include_router(users.router, prefix=f"{settings.api_prefix}")
app.include_router(agent_router, prefix=f"{settings.api_prefix}")
app.include_router(calls.router, prefix=f"{settings.api_prefix}")
app.include_router(evaluation.router, prefix=f"{settings.api_prefix}")
app.include_router(analysis_router, prefix=f"{settings.api_prefix}")
app.include_router(coaching.router, prefix=f"{settings.api_prefix}")
app.include_router(command_center.router, prefix=f"{settings.api_prefix}")
app.include_router(analytics.router, prefix=f"{settings.api_prefix}")

# Legacy contact submission endpoint (public)
@app.post("/api/contact")
async def submit_contact(submission: dict):
    """Legacy contact submission endpoint"""
    from fastapi_app.repositories.analytics_repository import ContactSubmissionRepository
    
    # Map to new schema
    data = {
        "first_name": submission.get("firstName", ""),
        "last_name": submission.get("lastName", ""),
        "email": submission.get("email"),
        "company": submission.get("company"),
        "industry": submission.get("industry"),
        "message": submission.get("message", ""),
        "tenant_id": "default"
    }
    
    db: Session = next(get_db())
    try:
        repo = ContactSubmissionRepository(db)
        contact = repo.create(obj_in=data)
        return {"success": True, "id": str(contact.id)}
    except Exception as e:
        logger.error(f"Contact submission error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

# Webhook endpoints
@app.post("/api/webhooks/assemblyai")
async def webhook_assemblyai(payload: dict):
    """Handle AssemblyAI webhook"""
    from fastapi_app.services.transcription_service import TranscriptionService
    
    transcript_id = payload.get("transcript_id")
    if not transcript_id:
        return {"error": "No transcript ID"}
    
    db: Session = next(get_db())
    try:
        service = TranscriptionService(db)
        await service.handle_webhook(transcript_id, payload)
        return {"success": True}
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return {"error": str(e)}
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "new_main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

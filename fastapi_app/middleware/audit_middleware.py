"""
Audit Logging Middleware
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json
from datetime import datetime

from ..core.database import get_db_context
from ..models.analytics import AuditLog

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for audit logging"""
    
    # Actions to audit
    AUDIT_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    
    # Paths to exclude from auditing
    EXCLUDE_PATHS = [
        "/health",
        "/docs",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/webhooks"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Log API actions"""
        # Only audit specific methods
        if request.method not in self.AUDIT_METHODS:
            response = await call_next(request)
            return response
        
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDE_PATHS):
            response = await call_next(request)
            return response
        
        # Get request details
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", "default")
        
        # Note: Request body capture disabled to avoid ASGI message flow issues
        # Body reading in middleware can cause "Unexpected message received" errors
        body = None
        
        # Process request
        response = await call_next(request)
        
        # Log audit entry if user is authenticated
        if user_id and response.status_code < 400:
            try:
                self._create_audit_log(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=f"{request.method} {request.url.path}",
                    entity_type=self._extract_entity_type(request.url.path),
                    entity_id=self._extract_entity_id(request.url.path),
                    changes=body,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent")
                )
            except Exception as e:
                logger.error(f"Failed to create audit log: {e}")
        
        return response
    
    def _extract_entity_type(self, path: str) -> str:
        """Extract entity type from path"""
        parts = path.split("/")
        if len(parts) > 2:
            entity = parts[2]
            # Remove plural 's'
            if entity.endswith("s"):
                return entity[:-1]
            return entity
        return "unknown"
    
    def _extract_entity_id(self, path: str) -> str:
        """Extract entity ID from path"""
        parts = path.split("/")
        if len(parts) > 3:
            # Check if the part looks like a UUID
            potential_id = parts[3]
            if len(potential_id) == 36 and potential_id.count("-") == 4:
                return potential_id
        return None
    
    def _create_audit_log(self, **kwargs):
        """Create audit log entry"""
        # This would normally use the database
        # For now, just log it
        logger.info(f"AUDIT: {kwargs.get('action')} by {kwargs.get('user_id')}")

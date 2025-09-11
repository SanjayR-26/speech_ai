"""
Role-Based Access Control Middleware
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import re

from ..core.security import check_permission

logger = logging.getLogger(__name__)


class RBACMiddleware(BaseHTTPMiddleware):
    """Middleware for role-based access control"""
    
    # Path to permission mapping
    PERMISSION_MAP = {
        # Tenants
        r"^/api/tenants$": {"GET": "tenant:list", "POST": "tenant:create"},
        r"^/api/tenants/[^/]+$": {"GET": "tenant:read", "PUT": "tenant:update"},
        
        # Organizations
        r"^/api/organizations$": {"GET": "organization:read", "POST": "organization:create"},
        r"^/api/organizations/[^/]+$": {"GET": "organization:read", "PUT": "organization:update", "DELETE": "organization:delete"},
        
        # Users
        r"^/api/users$": {"GET": "user:read", "POST": "user:create"},
        r"^/api/users/[^/]+$": {"GET": "user:read", "PUT": "user:update", "DELETE": "user:delete"},
        
        # Calls
        r"^/api/calls$": {"GET": "call:read", "POST": "call:create"},
        r"^/api/calls/[^/]+$": {"GET": "call:read", "DELETE": "call:delete"},
        
        # Evaluation
        r"^/api/evaluation-criteria$": {"GET": "evaluation:read", "POST": "evaluation:create"},
        r"^/api/evaluation-criteria/[^/]+$": {"GET": "evaluation:read", "PUT": "evaluation:update", "DELETE": "evaluation:delete"},
    }
    
    # Paths that don't require permission checks
    EXEMPT_PATHS = [
        "/health",
        "/docs",
        "/api/auth",
        "/api/version",
        "/api/contact",
        "/api/webhooks"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Check permissions based on path and method"""
        path = request.url.path
        method = request.method
        
        # Check if path is exempt
        if self._is_exempt(path):
            response = await call_next(request)
            return response
        
        # Get current user from request state
        current_user = getattr(request.state, "current_user", None)
        if not current_user:
            # Auth middleware should have caught this
            response = await call_next(request)
            return response
        
        # Find required permission
        required_permission = self._get_required_permission(path, method)
        if required_permission:
            # Check permission
            if not check_permission(current_user, required_permission):
                logger.warning(f"Permission denied: user={current_user.get('id')} permission={required_permission}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "FORBIDDEN",
                        "message": f"Permission denied: {required_permission}",
                        "details": {"required": required_permission}
                    }
                )
        
        # Continue processing
        response = await call_next(request)
        return response
    
    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from permission checks"""
        for exempt in self.EXEMPT_PATHS:
            if path.startswith(exempt):
                return True
        return False
    
    def _get_required_permission(self, path: str, method: str) -> str:
        """Get required permission for path and method"""
        for pattern, permissions in self.PERMISSION_MAP.items():
            if re.match(pattern, path):
                return permissions.get(method)
        return None

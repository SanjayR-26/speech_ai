"""
JWT Authentication Middleware
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from ..core.security import verify_token
from ..core.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT validation"""
    
    # Paths that don't require authentication
    EXEMPT_PATHS = [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/auth/login",
        "/api/auth/signup",
        "/api/auth/refresh",
        "/api/role-auth/tenant-admin/signup",
        "/api/role-auth/login",
        "/api/role-auth/forgot-password",
        "/api/contact",
        "/api/webhooks"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request"""
        # Check if path is exempt
        if self._is_exempt(request.url.path):
            response = await call_next(request)
            return response
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "UNAUTHORIZED", "message": "Missing or invalid authorization header"}
            )
        
        token = auth_header.split(" ")[1]
        
        try:
            # Verify token
            payload = await verify_token(token)
            
            # Store token data in request state
            request.state.token_payload = payload
            request.state.user_id = payload.get("sub")
            request.state.tenant_id = payload.get("tenant_id", "default")
            
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "UNAUTHORIZED", "message": "Invalid token"}
            )
        
        # Continue processing
        response = await call_next(request)
        return response
    
    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from authentication"""
        for exempt in self.EXEMPT_PATHS:
            if path.startswith(exempt):
                return True
        return False

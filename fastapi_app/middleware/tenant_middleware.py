"""
Tenant Context Middleware
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from ..core.database import get_db_context, set_tenant_context

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Middleware for setting tenant context"""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and set tenant context"""
        # Get tenant ID from request state (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", "default")
        user_id = getattr(request.state, "user_id", None)
        
        # Store in request for easy access
        request.state.tenant_id = tenant_id
        
        # Log tenant context
        logger.debug(f"Request tenant context: tenant={tenant_id}, user={user_id}")
        
        # Note: Actual tenant context setting happens in get_current_user dependency
        # This middleware just ensures the values are available
        
        response = await call_next(request)
        return response

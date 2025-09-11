"""
Custom exceptions for the application
"""
from typing import Optional, Dict, Any


class BaseAPIException(Exception):
    """Base exception for API errors"""
    def __init__(
        self, 
        message: str, 
        status_code: int = 400,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(BaseAPIException):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict] = None):
        super().__init__(message, 401, "AUTHENTICATION_ERROR", details)


class AuthorizationError(BaseAPIException):
    """Raised when user lacks permissions"""
    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict] = None):
        super().__init__(message, 403, "AUTHORIZATION_ERROR", details)


class NotFoundError(BaseAPIException):
    """Raised when resource is not found"""
    def __init__(self, resource: str, identifier: str):
        message = f"{resource} not found: {identifier}"
        super().__init__(message, 404, "NOT_FOUND", {"resource": resource, "id": identifier})


class ValidationError(BaseAPIException):
    """Raised when validation fails"""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, 422, "VALIDATION_ERROR", details)


class ConflictError(BaseAPIException):
    """Raised when there's a conflict (e.g., duplicate)"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, 409, "CONFLICT", details)


class TenantError(BaseAPIException):
    """Raised for tenant-related errors"""
    def __init__(self, message: str, tenant_id: Optional[str] = None):
        details = {"tenant_id": tenant_id} if tenant_id else {}
        super().__init__(message, 400, "TENANT_ERROR", details)


class QuotaExceededError(BaseAPIException):
    """Raised when tenant exceeds quota"""
    def __init__(self, resource: str, limit: int, current: int):
        message = f"Quota exceeded for {resource}: {current}/{limit}"
        details = {"resource": resource, "limit": limit, "current": current}
        super().__init__(message, 429, "QUOTA_EXCEEDED", details)


class ExternalServiceError(BaseAPIException):
    """Raised when external service fails"""
    def __init__(self, service: str, message: str, details: Optional[Dict] = None):
        details = details or {}
        details["service"] = service
        super().__init__(message, 502, "EXTERNAL_SERVICE_ERROR", details)


class ProcessingError(BaseAPIException):
    """Raised when processing fails"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, 500, "PROCESSING_ERROR", details)

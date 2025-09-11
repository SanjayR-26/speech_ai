"""
Authentication API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..api.deps import get_db
from ..services.auth_service import AuthService
from ..schemas.auth import (
    LoginRequest, SignupRequest, AuthResponse, SignupResponse, RefreshTokenRequest,
    TokenResponse, ChangePasswordRequest, UserInfo
)
from ..core.security import get_current_user
from ..core.exceptions import ConflictError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=SignupResponse)
async def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    """Deprecated: Use role-based endpoints instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "message": "This endpoint is deprecated. Use role-based signup endpoints.",
            "use": [
                "/api/role-auth/tenant-admin/signup",
                "/api/role-auth/manager/signup",
                "/api/role-auth/agent/signup"
            ]
        }
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """Deprecated: Use role-based login endpoint instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "message": "This endpoint is deprecated. Use role-based login endpoint.",
            "use": "/api/role-auth/login"
        }
    )


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout and revoke tokens"""
    auth_service = AuthService(db)
    
    # Get refresh token from request (would typically be in cookie or header)
    refresh_token = current_user.get("refresh_token", "")
    
    result = await auth_service.logout(
        current_user["id"],
        refresh_token
    )
    
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token"""
    auth_service = AuthService(db)
    
    try:
        result = await auth_service.refresh_token(request.refresh_token)
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type="Bearer",
            expires_in=result["expires_in"],
            refresh_expires_in=result.get("refresh_expires_in", 86400)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.get("/profile", response_model=UserInfo)
async def get_profile(
    current_user: dict = Depends(get_current_user)
):
    """Get current user profile"""
    return UserInfo(**current_user)


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    auth_service = AuthService(db)
    
    try:
        await auth_service.change_password(
            current_user["id"],
            request.current_password,
            request.new_password
        )
        return {"message": "Password changed successfully"}
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Password change not yet implemented. Please use Keycloak admin interface."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

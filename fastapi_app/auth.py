from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase_client import get_supabase_client
from typing import Optional, Dict, Any

security = HTTPBearer(auto_error=False)


async def get_current_user(
	credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """
    Verify the JWT token with Supabase and return the user.
    Returns None if no valid auth is provided (for optional auth routes).
    """
    if not credentials:
        return None
    
    try:
        supabase = get_supabase_client()
        # Verify the token with Supabase
        user = supabase.auth.get_user(credentials.credentials)
        if user and user.user:
            user_dict = user.user.dict() if hasattr(user.user, "dict") else dict(user.user)
            # attach access token so DB calls can pass RLS
            user_dict["access_token"] = credentials.credentials
            return user_dict
        return None
    except Exception:
        return None


async def require_auth(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency that requires authentication.
    Raises 401 if user is not authenticated.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

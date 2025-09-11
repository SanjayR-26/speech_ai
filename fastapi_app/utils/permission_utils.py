"""
Permission utility functions
"""
from typing import List, Optional, Dict, Any


def check_permission(user: Dict[str, Any], permission: str) -> bool:
    """Check if user has specific permission"""
    # Define role-permission mapping
    role_permissions = {
        "super_admin": ["*"],  # All permissions
        "tenant_admin": [
            "tenant:read", "tenant:update",
            "organization:*", "user:*", "agent:*",
            "call:*", "evaluation:*", "analytics:*",
            "settings:*"
        ],
        "manager": [
            "organization:read", "user:read", "user:create", "user:update",
            "agent:*", "call:*", "evaluation:*", 
            "analytics:read", "report:*", "coaching:*"
        ],
        "agent": [
            "organization:read", "user:read:self",
            "call:create", "call:read:own", "call:update:own",
            "evaluation:read:own", "analytics:read:own",
            "coaching:read:own", "coaching:update:own"
        ]
    }
    
    user_roles = user.get("roles", [])
    
    # Check each role's permissions
    for role in user_roles:
        if role == "super_admin":
            return True
        
        role_perms = role_permissions.get(role, [])
        for perm in role_perms:
            # Handle wildcard permissions
            if perm.endswith("*"):
                prefix = perm[:-1]
                if permission.startswith(prefix):
                    return True
            elif perm == permission:
                return True
            # Handle :own suffix
            elif perm.endswith(":own") and permission.startswith(perm[:-4]):
                # This would need additional context to check ownership
                # For now, assume it's handled at the service layer
                return True
    
    return False


def has_role(user: Dict[str, Any], required_roles: List[str]) -> bool:
    """Check if user has any of the required roles"""
    user_roles = user.get("roles", [])
    return any(role in user_roles for role in required_roles)


def has_all_roles(user: Dict[str, Any], required_roles: List[str]) -> bool:
    """Check if user has all required roles"""
    user_roles = user.get("roles", [])
    return all(role in user_roles for role in required_roles)


def get_user_permissions(user: Dict[str, Any]) -> List[str]:
    """Get all permissions for a user"""
    permissions = set()
    
    role_permissions = {
        "super_admin": ["*"],
        "tenant_admin": [
            "tenant:read", "tenant:update",
            "organization:*", "user:*", "agent:*",
            "call:*", "evaluation:*", "analytics:*",
            "settings:*"
        ],
        "manager": [
            "organization:read", "user:read", "user:create", "user:update",
            "agent:*", "call:*", "evaluation:*", 
            "analytics:read", "report:*", "coaching:*"
        ],
        "agent": [
            "organization:read", "user:read:self",
            "call:create", "call:read:own", "call:update:own",
            "evaluation:read:own", "analytics:read:own",
            "coaching:read:own", "coaching:update:own"
        ]
    }
    
    user_roles = user.get("roles", [])
    
    for role in user_roles:
        if role == "super_admin":
            return ["*"]
        
        role_perms = role_permissions.get(role, [])
        permissions.update(role_perms)
    
    return sorted(list(permissions))


def filter_by_permissions(
    items: List[Dict[str, Any]],
    user: Dict[str, Any],
    permission_field: str = "required_permission"
) -> List[Dict[str, Any]]:
    """Filter list of items by user permissions"""
    filtered = []
    
    for item in items:
        required_permission = item.get(permission_field)
        if not required_permission or check_permission(user, required_permission):
            filtered.append(item)
    
    return filtered


def check_resource_access(
    user: Dict[str, Any],
    resource_type: str,
    resource_id: str,
    action: str
) -> bool:
    """Check access to specific resource"""
    # Build permission string
    permission = f"{resource_type}:{action}"
    
    # Check general permission
    if check_permission(user, permission):
        return True
    
    # Check ownership-based permission
    own_permission = f"{resource_type}:{action}:own"
    if check_permission(user, own_permission):
        # This would need to check actual ownership
        # For now, return True if user has the :own permission
        # Actual ownership check should be done at service layer
        return True
    
    return False

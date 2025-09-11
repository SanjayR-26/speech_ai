"""
Role-Based Access Control utility functions
"""
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.pricing import RolePermission
from ..schemas.role_auth import UserRole


class RBACManager:
    """Role-Based Access Control Manager"""
    
    # Default permissions for each role
    DEFAULT_PERMISSIONS = {
        UserRole.TENANT_ADMIN: [
            # Organization management
            "organization:create", "organization:read", "organization:update", "organization:delete",
            # User management
            "user:create", "user:read", "user:update", "user:delete",
            # Call analysis (full access)
            "call:create", "call:read", "call:update", "call:delete",
            # Analytics and reports
            "analytics:read", "analytics:create", "report:read", "report:create",
            # Settings and configuration
            "settings:read", "settings:update",
            # Evaluation criteria
            "evaluation:create", "evaluation:read", "evaluation:update", "evaluation:delete",
            # Department and team management
            "department:create", "department:read", "department:update", "department:delete",
            "team:create", "team:read", "team:update", "team:delete",
        ],
        UserRole.MANAGER: [
            # Organization (read only)
            "organization:read",
            # User management (agents only)
            "agent:create", "user:read", "agent:update",
            # Call analysis (full access)
            "call:create", "call:read", "call:update", "call:delete",
            # Analytics and reports
            "analytics:read", "report:read", "report:create",
            # Evaluation criteria (full access)
            "evaluation:create", "evaluation:read", "evaluation:update", "evaluation:delete",
            # Department and team (read + update)
            "department:read", "team:read", "team:update",
        ],
        UserRole.AGENT: [
            # Organization (read only)
            "organization:read",
            # User (read own profile)
            "user:read_own",
            # Call analysis (read only)
            "call:read",
            # Analytics (read only)
            "analytics:read",
            # Department and team (read only)
            "department:read", "team:read",
        ]
    }
    
    @staticmethod
    def check_permission(user: Dict[str, Any], required_permission: str) -> bool:
        """Check if user has required permission"""
        user_role = user.get("role")
        user_permissions = user.get("permissions", [])
        
        if not user_role:
            return False
        
        # Check explicit permissions first
        if required_permission in user_permissions:
            return True
        
        # Check default role permissions
        default_perms = RBACManager.DEFAULT_PERMISSIONS.get(user_role, [])
        if required_permission in default_perms:
            return True
        
        # Special cases for self-access
        if required_permission == "user:read_own":
            return True  # All authenticated users can read own profile
        
        return False
    
    @staticmethod
    def can_create_user_role(creator_role: UserRole, target_role: UserRole) -> bool:
        """Check if creator can create user with target role"""
        if creator_role == UserRole.TENANT_ADMIN:
            return target_role in [UserRole.MANAGER, UserRole.AGENT]
        elif creator_role == UserRole.MANAGER:
            return target_role == UserRole.AGENT
        return False
    
    @staticmethod
    def can_manage_user(manager_user: Dict[str, Any], target_user: Dict[str, Any]) -> bool:
        """Check if manager can manage target user"""
        manager_role = manager_user.get("role")
        target_role = target_user.get("role")
        manager_org = manager_user.get("organization_id")
        target_org = target_user.get("organization_id")
        
        # Must be same organization
        if manager_org != target_org:
            return False
        
        # Tenant admin can manage everyone in org
        if manager_role == UserRole.TENANT_ADMIN:
            return True
        
        # Manager can manage agents
        if manager_role == UserRole.MANAGER and target_role == UserRole.AGENT:
            return True
        
        return False
    
    @staticmethod
    def get_accessible_resources(user: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        """Get resource access constraints for user"""
        user_role = user.get("role")
        organization_id = user.get("organization_id")
        user_id = user.get("id")
        
        constraints = {
            "organization_id": organization_id,  # Always constrained to own org
        }
        
        if resource_type == "calls":
            if user_role == UserRole.AGENT:
                # Agents can only see their own calls
                constraints["agent_id"] = user_id
            # Managers and admins see all calls in org
        
        elif resource_type == "users":
            if user_role == UserRole.AGENT:
                # Agents can only see themselves
                constraints["user_id"] = user_id
            # Managers and admins see all users in org
        
        elif resource_type == "analytics":
            if user_role == UserRole.AGENT:
                # Agents see only their own analytics
                constraints["agent_id"] = user_id
            # Managers and admins see all analytics in org
        
        return constraints


def check_permission(user: Dict[str, Any], required_permission: str) -> bool:
    """Global permission check function"""
    return RBACManager.check_permission(user, required_permission)


def require_permission(required_permission: str):
    """Decorator for requiring specific permission"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be used with FastAPI dependencies
            # Implementation depends on how current_user is passed
            pass
        return wrapper
    return decorator


def setup_default_permissions(db: Session):
    """Setup default permissions in database"""
    
    # Check if permissions already exist
    existing = db.query(RolePermission).first()
    if existing:
        return
    
    permissions_to_create = []
    
    for role, permissions in RBACManager.DEFAULT_PERMISSIONS.items():
        for permission in permissions:
            resource, action = permission.split(":")
            perm = RolePermission(
                role=role,
                resource=resource,
                action=action,
                description=f"Default {action} permission for {resource}",
                is_active=True
            )
            permissions_to_create.append(perm)
    
    db.add_all(permissions_to_create)
    db.commit()


def seed_pricing_plans(db: Session):
    """Seed default pricing plans"""
    from ..models.pricing import PricingPlan
    
    # Check if plans already exist
    existing = db.query(PricingPlan).first()
    if existing:
        return
    
    plans = [
        PricingPlan(
            name="Starter",
            description="Perfect for small teams getting started",
            price_per_month=29.00,
            price_per_year=290.00,
            max_agents=5,
            max_managers=2,
            max_calls_per_month=1000,
            max_storage_gb=10,
            features={
                "basic_analytics": True,
                "email_support": True,
                "basic_reports": True,
                "api_access": False,
                "advanced_analytics": False,
                "custom_integrations": False
            },
            trial_days=14
        ),
        PricingPlan(
            name="Professional", 
            description="Advanced features for growing businesses",
            price_per_month=99.00,
            price_per_year=990.00,
            max_agents=25,
            max_managers=5,
            max_calls_per_month=5000,
            max_storage_gb=100,
            features={
                "basic_analytics": True,
                "advanced_analytics": True,
                "email_support": True,
                "phone_support": True,
                "basic_reports": True,
                "advanced_reports": True,
                "api_access": True,
                "custom_integrations": False,
                "white_labeling": False
            },
            trial_days=14
        ),
        PricingPlan(
            name="Enterprise",
            description="Full-featured solution for large organizations",
            price_per_month=299.00,
            price_per_year=2990.00,
            max_agents=100,
            max_managers=20,
            max_calls_per_month=25000,
            max_storage_gb=1000,
            features={
                "basic_analytics": True,
                "advanced_analytics": True,
                "email_support": True,
                "phone_support": True,
                "priority_support": True,
                "basic_reports": True,
                "advanced_reports": True,
                "custom_reports": True,
                "api_access": True,
                "custom_integrations": True,
                "white_labeling": True,
                "sso_integration": True,
                "dedicated_manager": True
            },
            trial_days=30
        )
    ]
    
    db.add_all(plans)
    db.commit()

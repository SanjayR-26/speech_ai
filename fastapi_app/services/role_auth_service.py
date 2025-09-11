"""
Role-based authentication service
"""
import secrets
import string
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.user import UserProfile
from ..models.tenant import Organization, Tenant
from ..models.pricing import PricingPlan, RolePermission
from ..services.auth_service import AuthService
from ..core.exceptions import ConflictError, AuthorizationError, AuthenticationError
from ..repositories.user_repository import UserRepository, AgentRepository
from ..repositories.tenant_repository import OrganizationRepository
from ..schemas.role_auth import UserRole


class RoleAuthService:
    """Service for role-based authentication and user management"""
    
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.agent_repo = AgentRepository(db)
    
    def _generate_temp_password(self, length: int = 12) -> str:
        """Generate a temporary password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    async def create_tenant_admin(
        self,
        organization_name: str,
        industry: Optional[str],
        organization_size: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """Create a new tenant administrator and organization"""
        
        # Check if organization name already exists in tenant
        existing_org = self.org_repo.get_by_name_and_tenant(organization_name, tenant_id)
        if existing_org:
            raise ConflictError(f"Organization '{organization_name}' already exists")
        
        # Check if user email already exists
        existing_user = self.user_repo.get_by_email(email)
        if existing_user:
            raise ConflictError(f"User with email '{email}' already exists")
        
        try:
            # Create Keycloak user first
            keycloak_user_id = await self.auth_service._create_keycloak_user(
                realm_name="qa-default",  # Using default realm for single tenant
                user_data={
                    "username": email,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "emailVerified": False,
                    "requiredActions": ["VERIFY_EMAIL"],
                    "credentials": [{
                        "type": "password",
                        "value": password,
                        "temporary": False
                    }]
                }
            )
            
            # Get default tenant
            tenant = self.db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
            if not tenant:
                raise Exception("Default tenant not found")
            
            # Create organization
            organization = Organization(
                tenant_id=tenant_id,
                name=organization_name,
                industry=industry,
                size=organization_size,
                current_agent_count=0,
                current_manager_count=1  # This admin counts as manager
            )
            self.db.add(organization)
            self.db.flush()  # Get the ID
            
            # Create user profile
            user_profile = UserProfile(
                keycloak_user_id=keycloak_user_id,
                organization_id=organization.id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=UserRole.TENANT_ADMIN,
                can_create_managers=True,
                can_create_agents=True,
                max_managers_allowed=10,  # Default limits
                max_agents_allowed=50
            )
            self.db.add(user_profile)
            self.db.commit()
            
            # Send verification email
            await self.auth_service._send_verification_email("qa-default", keycloak_user_id)
            
            # Get permissions for tenant admin
            permissions = self._get_role_permissions(UserRole.TENANT_ADMIN)
            
            return {
                "message": "Organization and administrator account created successfully. Please verify your email.",
                "user_id": str(user_profile.id),
                "organization_id": str(organization.id),
                "email": email,
                "role": UserRole.TENANT_ADMIN,
                "verification_required": True,
                "permissions": permissions
            }
            
        except ConflictError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create tenant admin: {str(e)}")
    
    async def create_manager(
        self,
        creator_user_id: str,
        organization_id: str,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        department_id: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new manager (by tenant admin)"""
        
        # Get creator and validate permissions
        creator = self.user_repo.get_by_id(creator_user_id)
        if not creator or creator.role != UserRole.TENANT_ADMIN:
            raise AuthorizationError("Only tenant administrators can create managers")
        
        if not creator.can_create_managers:
            raise AuthorizationError("User not authorized to create managers")
        
        # Check organization limits
        organization = self.org_repo.get_by_id(organization_id)
        if not organization:
            raise Exception("Organization not found")
        
        if creator.organization_id != organization.id:
            raise AuthorizationError("Cannot create users in different organization")
        
        # Check if email already exists
        existing_user = self.user_repo.get_by_email(email)
        if existing_user:
            raise ConflictError(f"User with email '{email}' already exists")
        
        # Generate password if not provided
        if not password:
            password = self._generate_temp_password()
            temp_password = True
        else:
            temp_password = False
        
        try:
            # Create Keycloak user
            keycloak_user_id = await self.auth_service._create_keycloak_user(
                realm_name="qa-default",
                user_data={
                    "username": email,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "emailVerified": False,
                    "requiredActions": ["VERIFY_EMAIL"] + (["UPDATE_PASSWORD"] if temp_password else []),
                    "credentials": [{
                        "type": "password",
                        "value": password,
                        "temporary": temp_password
                    }]
                }
            )
            
            # Create user profile
            user_profile = UserProfile(
                keycloak_user_id=keycloak_user_id,
                organization_id=organization.id,
                department_id=department_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=UserRole.MANAGER,
                created_by_user_id=creator.id,
                can_create_agents=True,
                can_create_managers=False,
                max_agents_allowed=20  # Default for managers
            )
            self.db.add(user_profile)
            
            # Update organization manager count
            organization.current_manager_count += 1
            self.db.commit()
            
            # Send verification email
            await self.auth_service._send_verification_email("qa-default", keycloak_user_id)
            
            return {
                "message": "Manager created successfully",
                "user_id": str(user_profile.id),
                "email": email,
                "role": UserRole.MANAGER,
                "organization_id": organization_id,
                "invitation_sent": True,
                "temporary_password": temp_password
            }
            
        except ConflictError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create manager: {str(e)}")
    
    async def create_agent(
        self,
        creator_user_id: str,
        organization_id: str,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        employee_id: Optional[str] = None,
        department_id: Optional[str] = None,
        team_id: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new agent (by tenant admin or manager)"""
        
        # Get creator and validate permissions
        creator = self.user_repo.get_by_id(creator_user_id)
        if not creator or creator.role not in [UserRole.TENANT_ADMIN, UserRole.MANAGER]:
            raise AuthorizationError("Only tenant administrators and managers can create agents")
        
        if not creator.can_create_agents:
            raise AuthorizationError("User not authorized to create agents")
        
        # Check organization
        organization = self.org_repo.get_by_id(organization_id)
        if not organization:
            raise Exception("Organization not found")
        
        if creator.organization_id != organization.id:
            raise AuthorizationError("Cannot create users in different organization")
        
        # Check if email already exists
        existing_user = self.user_repo.get_by_email(email)
        if existing_user:
            raise ConflictError(f"User with email '{email}' already exists")
        
        # Generate password if not provided
        if not password:
            password = self._generate_temp_password()
            temp_password = True
        else:
            temp_password = False
        
        try:
            # Create Keycloak user
            keycloak_user_id = await self.auth_service._create_keycloak_user(
                realm_name="qa-default",
                user_data={
                    "username": email,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "emailVerified": False,
                    "requiredActions": ["VERIFY_EMAIL"] + (["UPDATE_PASSWORD"] if temp_password else []),
                    "credentials": [{
                        "type": "password",
                        "value": password,
                        "temporary": temp_password
                    }]
                }
            )
            
            # Create user profile
            user_profile = UserProfile(
                keycloak_user_id=keycloak_user_id,
                organization_id=organization.id,
                department_id=department_id,
                team_id=team_id,
                employee_id=employee_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                role=UserRole.AGENT,
                created_by_user_id=creator.id,
                can_create_agents=False,
                can_create_managers=False
            )
            self.db.add(user_profile)
            self.db.flush()  # get user_profile.id

            # Create agent profile with generated agent_code
            agent_code = (employee_id or first_name[:1] + last_name[:1]).upper() if (first_name and last_name) else None
            if not agent_code:
                agent_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

            self.agent_repo.create_agent(
                tenant_id="default",
                user_profile_id=user_profile.id,
                data={
                    "agent_code": agent_code,
                    "specializations": [],
                    "languages": [],
                    "is_available": True
                }
            )

            # Update organization agent count
            organization.current_agent_count += 1
            self.db.commit()
            
            # Send verification email
            await self.auth_service._send_verification_email("qa-default", keycloak_user_id)
            
            return {
                "message": "Agent created successfully",
                "user_id": str(user_profile.id),
                "email": email,
                "role": UserRole.AGENT,
                "organization_id": organization_id,
                "invitation_sent": True,
                "temporary_password": temp_password
            }
            
        except ConflictError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create agent: {str(e)}")
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        expected_role: UserRole
    ) -> Dict[str, Any]:
        """Authenticate user with role verification"""
        
        # Get user profile first to verify role
        user_profile = self.user_repo.get_by_email(email)
        if not user_profile:
            raise AuthenticationError("Invalid credentials")
        
        # Verify role matches expected
        if user_profile.role != expected_role:
            raise AuthenticationError(f"User is not authorized as {expected_role}")
        
        # Authenticate with Keycloak
        try:
            auth_result = await self.auth_service.login(
                username=email,
                password=password,
                tenant_id="default"
            )
            
            # Add role-specific information
            permissions = self._get_role_permissions(user_profile.role)
            
            auth_result.update({
                "user": {
                    "id": str(user_profile.id),
                    "email": user_profile.email,
                    "first_name": user_profile.first_name,
                    "last_name": user_profile.last_name,
                    "role": user_profile.role,
                    "organization_id": str(user_profile.organization_id)
                },
                "organization": {
                    "id": str(user_profile.organization.id),
                    "name": user_profile.organization.name,
                    "industry": user_profile.organization.industry
                },
                "permissions": permissions
            })
            
            return auth_result
            
        except Exception as e:
            raise AuthenticationError(str(e))
    
    def _get_role_permissions(self, role: UserRole) -> list[str]:
        """Get permissions for a role"""
        permissions = self.db.query(RolePermission).filter(
            and_(
                RolePermission.role == role,
                RolePermission.is_active == True
            )
        ).all()
        
        return [f"{perm.resource}:{perm.action}" for perm in permissions]

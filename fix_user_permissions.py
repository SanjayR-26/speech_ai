#!/usr/bin/env python3
"""
Script to fix tenant admin user permissions
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi_app.core.database import SessionLocal
from fastapi_app.models.user import UserProfile, UserRole

def fix_tenant_admin_permissions():
    """Fix tenant admin user permissions"""
    db = SessionLocal()
    try:
        # Find all tenant admin users
        tenant_admins = db.query(UserProfile).filter(
            UserProfile.role == UserRole.TENANT_ADMIN
        ).all()
        
        print(f"Found {len(tenant_admins)} tenant admin users")
        
        for admin in tenant_admins:
            print(f"\nUser: {admin.email}")
            print(f"Current can_create_agents: {admin.can_create_agents}")
            print(f"Current can_create_managers: {admin.can_create_managers}")
            
            # Update permissions if needed
            needs_update = False
            if not admin.can_create_agents:
                admin.can_create_agents = True
                needs_update = True
                print("✓ Fixed can_create_agents")
                
            if not admin.can_create_managers:
                admin.can_create_managers = True
                needs_update = True
                print("✓ Fixed can_create_managers")
                
            if admin.max_managers_allowed is None or admin.max_managers_allowed <= 0:
                admin.max_managers_allowed = 10
                needs_update = True
                print("✓ Fixed max_managers_allowed")
                
            if admin.max_agents_allowed is None or admin.max_agents_allowed <= 0:
                admin.max_agents_allowed = 50
                needs_update = True
                print("✓ Fixed max_agents_allowed")
            
            if needs_update:
                db.commit()
                print("✅ User permissions updated")
            else:
                print("✅ User permissions already correct")
                
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_tenant_admin_permissions()

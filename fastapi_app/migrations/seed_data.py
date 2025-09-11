"""
Seed data for initial setup
"""
import asyncio
import logging
from sqlalchemy import text
from datetime import datetime
import uuid

from ..core.database import SessionLocal, init_db

logger = logging.getLogger(__name__)


async def seed_default_evaluation_criteria():
    """Seed default evaluation criteria templates"""
    db = SessionLocal()
    try:
        # Check if already seeded
        result = db.execute(text("SELECT COUNT(*) FROM default_evaluation_criteria"))
        if result.scalar() > 0:
            logger.info("Default evaluation criteria already seeded")
            return
        
        # Default criteria
        criteria = [
            {
                "name": "Opening and Greeting",
                "description": "Professional greeting, introduction, and establishing rapport",
                "category": "communication",
                "default_points": 10
            },
            {
                "name": "Active Listening",
                "description": "Demonstrating understanding, asking clarifying questions",
                "category": "communication",
                "default_points": 15
            },
            {
                "name": "Problem Resolution",
                "description": "Effectively addressing and resolving customer concerns",
                "category": "technical",
                "default_points": 20
            },
            {
                "name": "Product Knowledge",
                "description": "Accurate information and appropriate solutions",
                "category": "technical",
                "default_points": 15
            },
            {
                "name": "Communication Skills",
                "description": "Clear, professional language and tone",
                "category": "communication",
                "default_points": 10
            },
            {
                "name": "Empathy and Patience",
                "description": "Understanding customer emotions and showing patience",
                "category": "soft_skills",
                "default_points": 10
            },
            {
                "name": "Compliance",
                "description": "Following required scripts and procedures",
                "category": "compliance",
                "default_points": 10
            },
            {
                "name": "Call Closing",
                "description": "Proper closure, summary, and next steps",
                "category": "process",
                "default_points": 10
            }
        ]
        
        for criterion in criteria:
            criterion["id"] = str(uuid.uuid4())
            criterion["created_at"] = datetime.utcnow()
            criterion["updated_at"] = datetime.utcnow()
            
            db.execute(
                text("""
                INSERT INTO default_evaluation_criteria 
                (id, name, description, category, default_points, created_at, updated_at)
                VALUES (:id, :name, :description, :category, :default_points, :created_at, :updated_at)
                """),
                criterion
            )
        
        db.commit()
        logger.info(f"Seeded {len(criteria)} default evaluation criteria")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to seed evaluation criteria: {e}")
        raise
    finally:
        db.close()


async def seed_feature_flags():
    """Seed default feature flags"""
    db = SessionLocal()
    try:
        # Default feature flags
        flags = [
            {
                "feature_key": "ai_coach",
                "display_name": "AI Coach",
                "description": "AI-powered training and coaching features",
                "is_enabled": True,
                "rollout_percentage": 100
            },
            {
                "feature_key": "command_center",
                "display_name": "Command Center",
                "description": "Real-time monitoring and analytics dashboard",
                "is_enabled": True,
                "rollout_percentage": 100
            },
            {
                "feature_key": "advanced_analytics",
                "display_name": "Advanced Analytics",
                "description": "Advanced reporting and trend analysis",
                "is_enabled": True,
                "rollout_percentage": 100
            },
            {
                "feature_key": "custom_evaluation",
                "display_name": "Custom Evaluation Criteria",
                "description": "Ability to create custom evaluation criteria",
                "is_enabled": True,
                "rollout_percentage": 100
            },
            {
                "feature_key": "bulk_upload",
                "display_name": "Bulk Upload",
                "description": "Upload multiple audio files at once",
                "is_enabled": False,
                "rollout_percentage": 0
            }
        ]
        
        for flag in flags:
            flag["id"] = str(uuid.uuid4())
            flag["tenant_id"] = "default"
            flag["created_at"] = datetime.utcnow()
            flag["updated_at"] = datetime.utcnow()
            flag["configuration"] = {}
            
            # Check if exists
            result = db.execute(
                text("SELECT id FROM feature_flags WHERE tenant_id = :tid AND feature_key = :key"),
                {"tid": flag["tenant_id"], "key": flag["feature_key"]}
            )
            if result.first():
                continue
            
            db.execute(
                text("""
                INSERT INTO feature_flags 
                (id, tenant_id, feature_key, display_name, description, 
                 is_enabled, rollout_percentage, configuration, created_at, updated_at)
                VALUES (:id, :tenant_id, :feature_key, :display_name, :description,
                        :is_enabled, :rollout_percentage, :configuration::jsonb, 
                        :created_at, :updated_at)
                """),
                flag
            )
        
        db.commit()
        logger.info(f"Seeded {len(flags)} feature flags")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to seed feature flags: {e}")
        raise
    finally:
        db.close()


async def seed_test_data():
    """Seed test data for development"""
    db = SessionLocal()
    try:
        # Create test tenant if not exists
        result = db.execute(
            text("SELECT id FROM tenants WHERE tenant_id = 'test'")
        )
        if not result.first():
            tenant_data = {
                "id": str(uuid.uuid4()),
                "tenant_id": "test",
                "realm_name": "qa-test",
                "subdomain": "test",
                "display_name": "Test Tenant",
                "status": "active",
                "tier": "enterprise",
                "max_users": 1000,
                "max_storage_gb": 1000,
                "max_calls_per_month": 100000,
                "max_agents": 500,
                "features": ["ai_coach", "command_center", "advanced_analytics"],
                "settings": {},
                "branding": {"primary_color": "#1976d2"},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            db.execute(
                text("""
                INSERT INTO tenants (id, tenant_id, realm_name, subdomain, display_name, 
                    status, tier, max_users, max_storage_gb, max_calls_per_month, max_agents,
                    features, settings, branding, created_at, updated_at)
                VALUES (:id, :tenant_id, :realm_name, :subdomain, :display_name,
                    :status, :tier, :max_users, :max_storage_gb, :max_calls_per_month, :max_agents,
                    :features::jsonb, :settings::jsonb, :branding::jsonb, :created_at, :updated_at)
                """),
                tenant_data
            )
            
            # Create test organization
            org_data = {
                "id": str(uuid.uuid4()),
                "tenant_id": "test",
                "name": "Test Organization",
                "industry": "Technology",
                "size": "large",
                "timezone": "America/New_York",
                "settings": {},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            db.execute(
                text("""
                INSERT INTO organizations (id, tenant_id, name, industry, size, timezone, 
                    settings, created_at, updated_at)
                VALUES (:id, :tenant_id, :name, :industry, :size, :timezone,
                    :settings::jsonb, :created_at, :updated_at)
                """),
                org_data
            )
            
            db.commit()
            logger.info("Created test tenant and organization")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to seed test data: {e}")
        raise
    finally:
        db.close()


async def run_seeds():
    """Run all seed scripts"""
    logger.info("Starting database seeding...")
    
    # Initialize database tables
    init_db()
    
    # Run seeds
    await seed_default_evaluation_criteria()
    await seed_feature_flags()
    
    # Only seed test data in development
    import os
    if os.getenv("ENVIRONMENT", "development") == "development":
        await seed_test_data()
    
    logger.info("Database seeding completed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_seeds())

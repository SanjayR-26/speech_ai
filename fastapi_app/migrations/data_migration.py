"""
Data migration script from old schema to new multi-tenant schema
"""
import asyncio
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
import uuid

from ..core.config import settings
from ..core.database import engine as new_engine, SessionLocal as NewSession

logger = logging.getLogger(__name__)

# Old database connection (Supabase)
OLD_DATABASE_URL = os.getenv("OLD_DATABASE_URL", "postgresql://user:pass@localhost/old_qa_platform")


class DataMigrator:
    """Migrate data from old schema to new multi-tenant schema"""
    
    def __init__(self):
        self.old_engine = create_engine(OLD_DATABASE_URL)
        self.OldSession = sessionmaker(bind=self.old_engine)
        self.new_engine = new_engine
        self.NewSession = NewSession
        self.tenant_id = "default"
        self.organization_id = None
        
    async def migrate_all(self):
        """Run all migrations"""
        try:
            # Create default tenant and organization
            await self.create_default_tenant()
            
            # Migrate data
            await self.migrate_agents()
            await self.migrate_customers()
            await self.migrate_calls()
            await self.migrate_transcriptions()
            await self.migrate_evaluations()
            
            logger.info("Data migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
    
    async def create_default_tenant(self):
        """Create default tenant and organization"""
        with self.NewSession() as db:
            # Check if tenant exists
            result = db.execute(
                text("SELECT id FROM tenants WHERE tenant_id = :tid"),
                {"tid": self.tenant_id}
            )
            if result.first():
                logger.info("Default tenant already exists")
                # Get organization
                org_result = db.execute(
                    text("SELECT id FROM organizations WHERE tenant_id = :tid LIMIT 1"),
                    {"tid": self.tenant_id}
                )
                org = org_result.first()
                if org:
                    self.organization_id = org.id
                return
            
            # Create tenant
            tenant_data = {
                "id": str(uuid.uuid4()),
                "tenant_id": self.tenant_id,
                "realm_name": "qa-default",
                "subdomain": "default",
                "display_name": "Default Tenant",
                "status": "active",
                "tier": "professional",
                "max_users": 100,
                "max_storage_gb": 100,
                "max_calls_per_month": 10000,
                "max_agents": 50,
                "features": ["ai_coach", "command_center", "advanced_analytics"],
                "settings": {},
                "branding": {},
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
            
            # Create default organization
            org_data = {
                "id": str(uuid.uuid4()),
                "tenant_id": self.tenant_id,
                "name": "Default Organization",
                "industry": "General",
                "size": "medium",
                "timezone": "UTC",
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
            
            self.organization_id = org_data["id"]
            
            # Initialize default evaluation criteria
            db.execute(
                text("SELECT initialize_default_criteria(:org_id::uuid, :tenant_id)"),
                {"org_id": self.organization_id, "tenant_id": self.tenant_id}
            )
            
            db.commit()
            logger.info("Created default tenant and organization")
    
    async def migrate_agents(self):
        """Migrate agents table"""
        with self.OldSession() as old_db, self.NewSession() as new_db:
            # Get agents from old database
            agents = old_db.execute(text("SELECT * FROM agents")).fetchall()
            
            for agent in agents:
                # Create user profile
                user_id = str(uuid.uuid4())
                user_data = {
                    "id": user_id,
                    "tenant_id": self.tenant_id,
                    "keycloak_user_id": str(uuid.uuid4()),  # Placeholder
                    "organization_id": self.organization_id,
                    "email": f"{agent['name'].lower().replace(' ', '.')}@example.com",
                    "first_name": agent['name'].split()[0] if agent['name'] else "Agent",
                    "last_name": agent['name'].split()[-1] if len(agent['name'].split()) > 1 else "",
                    "role": "agent",
                    "status": "active",
                    "created_at": agent.get('created_at', datetime.utcnow()),
                    "updated_at": datetime.utcnow()
                }
                
                new_db.execute(
                    text("""
                    INSERT INTO user_profiles (id, tenant_id, keycloak_user_id, organization_id,
                        email, first_name, last_name, role, status, created_at, updated_at)
                    VALUES (:id, :tenant_id, :keycloak_user_id, :organization_id,
                        :email, :first_name, :last_name, :role, :status, :created_at, :updated_at)
                    ON CONFLICT DO NOTHING
                    """),
                    user_data
                )
                
                # Create agent profile
                agent_data = {
                    "id": agent['id'],
                    "tenant_id": self.tenant_id,
                    "user_profile_id": user_id,
                    "agent_code": f"AG{agent['id'][:6].upper()}",
                    "is_available": True,
                    "created_at": agent.get('created_at', datetime.utcnow()),
                    "updated_at": datetime.utcnow()
                }
                
                new_db.execute(
                    text("""
                    INSERT INTO agents (id, tenant_id, user_profile_id, agent_code,
                        is_available, created_at, updated_at)
                    VALUES (:id, :tenant_id, :user_profile_id, :agent_code,
                        :is_available, :created_at, :updated_at)
                    ON CONFLICT DO NOTHING
                    """),
                    agent_data
                )
            
            new_db.commit()
            logger.info(f"Migrated {len(agents)} agents")
    
    async def migrate_customers(self):
        """Migrate customers if they exist in old schema"""
        # Old schema might not have customers table
        # Create customers from call data if needed
        pass
    
    async def migrate_calls(self):
        """Migrate call_data table to calls"""
        with self.OldSession() as old_db, self.NewSession() as new_db:
            # Get calls from old database
            calls = old_db.execute(text("SELECT * FROM call_data")).fetchall()
            
            for call in calls:
                # Create call record
                call_data = {
                    "id": call['id'],
                    "tenant_id": self.tenant_id,
                    "organization_id": self.organization_id,
                    "agent_id": call['agent_id'],
                    "status": "completed" if call.get('transcription') else "pending",
                    "metadata": {
                        "tags": call.get('tags', []),
                        "original_metrics": call.get('metrics', {})
                    },
                    "created_at": call.get('uploaded_at', datetime.utcnow()),
                    "updated_at": datetime.utcnow()
                }
                
                new_db.execute(
                    text("""
                    INSERT INTO calls (id, tenant_id, organization_id, agent_id,
                        status, metadata, created_at, updated_at)
                    VALUES (:id, :tenant_id, :organization_id, :agent_id,
                        :status, :metadata::jsonb, :created_at, :updated_at)
                    ON CONFLICT DO NOTHING
                    """),
                    call_data
                )
                
                # Create audio file record
                if call.get('file'):
                    file = call['file']
                    audio_data = {
                        "id": str(uuid.uuid4()),
                        "tenant_id": self.tenant_id,
                        "call_id": call['id'],
                        "organization_id": self.organization_id,
                        "file_name": file.get('file_name', 'audio.mp3'),
                        "file_size": file.get('file_size'),
                        "mime_type": file.get('mime_type', 'audio/mpeg'),
                        "storage_path": file.get('file_url'),
                        "storage_type": "s3",
                        "duration_seconds": file.get('duration_seconds'),
                        "is_processed": bool(call.get('transcription')),
                        "created_at": file.get('uploaded_at', datetime.utcnow()),
                        "updated_at": datetime.utcnow()
                    }
                    
                    new_db.execute(
                        text("""
                        INSERT INTO audio_files (id, tenant_id, call_id, organization_id,
                            file_name, file_size, mime_type, storage_path, storage_type,
                            duration_seconds, is_processed, created_at, updated_at)
                        VALUES (:id, :tenant_id, :call_id, :organization_id,
                            :file_name, :file_size, :mime_type, :storage_path, :storage_type,
                            :duration_seconds, :is_processed, :created_at, :updated_at)
                        ON CONFLICT DO NOTHING
                        """),
                        audio_data
                    )
            
            new_db.commit()
            logger.info(f"Migrated {len(calls)} calls")
    
    async def migrate_transcriptions(self):
        """Migrate transcription data"""
        with self.OldSession() as old_db, self.NewSession() as new_db:
            # Get calls with transcriptions
            calls = old_db.execute(
                text("SELECT * FROM call_data WHERE transcription IS NOT NULL")
            ).fetchall()
            
            for call in calls:
                transcription_obj = call['transcription']
                if not transcription_obj:
                    continue
                
                # Create transcription record
                trans_data = {
                    "id": str(uuid.uuid4()),
                    "tenant_id": self.tenant_id,
                    "call_id": call['id'],
                    "organization_id": self.organization_id,
                    "provider": "assemblyai",
                    "provider_transcript_id": transcription_obj.get('id'),
                    "status": "completed",
                    "language_code": transcription_obj.get('language_code'),
                    "confidence_score": transcription_obj.get('confidence'),
                    "word_count": len(transcription_obj.get('text', '').split()),
                    "raw_response": transcription_obj,
                    "completed_at": transcription_obj.get('completed_at', datetime.utcnow()),
                    "created_at": call.get('uploaded_at', datetime.utcnow()),
                    "updated_at": datetime.utcnow()
                }
                
                new_db.execute(
                    text("""
                    INSERT INTO transcriptions (id, tenant_id, call_id, organization_id,
                        provider, provider_transcript_id, status, language_code,
                        confidence_score, word_count, raw_response, completed_at,
                        created_at, updated_at)
                    VALUES (:id, :tenant_id, :call_id, :organization_id,
                        :provider, :provider_transcript_id, :status, :language_code,
                        :confidence_score, :word_count, :raw_response::jsonb, :completed_at,
                        :created_at, :updated_at)
                    ON CONFLICT DO NOTHING
                    """),
                    trans_data
                )
                
                # Create segments
                segments = transcription_obj.get('segments', [])
                for idx, segment in enumerate(segments):
                    seg_data = {
                        "id": str(uuid.uuid4()),
                        "tenant_id": self.tenant_id,
                        "transcription_id": trans_data["id"],
                        "call_id": call['id'],
                        "segment_index": idx,
                        "speaker_label": segment.get('speaker'),
                        "text": segment.get('text', ''),
                        "start_time": segment.get('start'),
                        "end_time": segment.get('end'),
                        "created_at": datetime.utcnow()
                    }
                    
                    new_db.execute(
                        text("""
                        INSERT INTO transcription_segments (id, tenant_id, transcription_id,
                            call_id, segment_index, speaker_label, text, start_time,
                            end_time, created_at)
                        VALUES (:id, :tenant_id, :transcription_id, :call_id,
                            :segment_index, :speaker_label, :text, :start_time,
                            :end_time, :created_at)
                        ON CONFLICT DO NOTHING
                        """),
                        seg_data
                    )
            
            new_db.commit()
            logger.info(f"Migrated transcriptions for {len(calls)} calls")
    
    async def migrate_evaluations(self):
        """Migrate QA evaluations"""
        with self.OldSession() as old_db, self.NewSession() as new_db:
            # Get calls with QA evaluations
            calls = old_db.execute(
                text("SELECT * FROM call_data WHERE transcription->'qa_evaluation' IS NOT NULL")
            ).fetchall()
            
            for call in calls:
                qa_eval = call['transcription'].get('qa_evaluation')
                if not qa_eval:
                    continue
                
                # Get transcription ID
                trans_result = new_db.execute(
                    text("SELECT id FROM transcriptions WHERE call_id = :call_id"),
                    {"call_id": call['id']}
                )
                trans = trans_result.first()
                if not trans:
                    continue
                
                # Create call analysis
                analysis_data = {
                    "id": str(uuid.uuid4()),
                    "tenant_id": self.tenant_id,
                    "call_id": call['id'],
                    "organization_id": self.organization_id,
                    "transcription_id": trans.id,
                    "analysis_provider": "openai",
                    "model_version": "gpt-4",
                    "total_points_earned": qa_eval.get('score', 0),
                    "total_max_points": 100,
                    "overall_score": qa_eval.get('score', 0),
                    "summary": qa_eval.get('summary', ''),
                    "speaker_mapping": qa_eval.get('speaker_mapping', {}),
                    "raw_analysis_response": qa_eval,
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "created_at": call.get('uploaded_at', datetime.utcnow()),
                    "updated_at": datetime.utcnow()
                }
                
                new_db.execute(
                    text("""
                    INSERT INTO call_analyses (id, tenant_id, call_id, organization_id,
                        transcription_id, analysis_provider, model_version,
                        total_points_earned, total_max_points, overall_score,
                        summary, speaker_mapping, raw_analysis_response, status,
                        completed_at, created_at, updated_at)
                    VALUES (:id, :tenant_id, :call_id, :organization_id,
                        :transcription_id, :analysis_provider, :model_version,
                        :total_points_earned, :total_max_points, :overall_score,
                        :summary, :speaker_mapping::jsonb, :raw_analysis_response::jsonb, :status,
                        :completed_at, :created_at, :updated_at)
                    ON CONFLICT DO NOTHING
                    """),
                    analysis_data
                )
            
            new_db.commit()
            logger.info(f"Migrated QA evaluations for {len(calls)} calls")


async def run_migration():
    """Run the data migration"""
    migrator = DataMigrator()
    await migrator.migrate_all()


if __name__ == "__main__":
    asyncio.run(run_migration())

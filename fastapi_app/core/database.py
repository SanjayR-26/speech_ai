"""
Database configuration and session management
"""
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Engine
import logging
from contextlib import contextmanager
from typing import Generator

from .config import settings
from ..utils.ssh_tunnel import get_database_url_with_tunnel, ensure_tunnel_active

logger = logging.getLogger(__name__)

# Initialize SSH tunnel if configured
def get_engine():
    """Get database engine with SSH tunnel support"""
    # Start with the configured URL
    db_url = settings.database_url

    # Only attempt SSH tunnel for PostgreSQL URLs and when explicitly enabled
    if db_url and db_url.startswith("postgres") and settings.use_ssh_tunnel:
        ensure_tunnel_active()
        db_url = get_database_url_with_tunnel()
    
    return create_engine(
        db_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,  # Verify connections before using
    )

# Create engine with connection pooling (lazy initialization)
_engine = None

def get_db_engine():
    """Get or create database engine"""
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine

# Backward-compatible accessor: call get_db_engine() when needed
def engine():
    return get_db_engine()

# Create session factory (will bind to engine lazily)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Database dependency for FastAPI
    """
    # Bind session to engine on first use
    SessionLocal.configure(bind=get_db_engine())
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database sessions
    """
    # Bind session to engine on first use
    SessionLocal.configure(bind=get_db_engine())
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def set_tenant_context(db: Session, tenant_id: str, user_id: str):
    """
    Set the tenant context for the current database session
    """
    try:
        db.execute(
            text("SELECT set_tenant_context(:tenant_id, :user_id)"),
            {"tenant_id": tenant_id, "user_id": user_id}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to set tenant context: {e}")
        db.rollback()
        raise


# Event listener to set search path for each connection, without touching a specific engine instance
@event.listens_for(Engine, "connect")
def set_search_path(dbapi_conn, connection_record):
    """
    Set the search path to public schema
    """
    with dbapi_conn.cursor() as cursor:
        cursor.execute("SET search_path TO public")


# Initialize database
def init_db():
    """
    Initialize database tables
    Note: In production, use Alembic migrations instead
    """
    try:
        # Import all models to ensure they're registered
        from ..models import (
            tenant, user, call, evaluation, 
            coaching, analytics
        )
        
        # Create all tables (bind lazily created engine)
        Base.metadata.create_all(bind=get_db_engine())
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def check_connection():
    """
    Check if database connection is working
    """
    try:
        with get_db_engine().connect() as conn:
            # Use SQLAlchemy text() for 2.x compatibility
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False

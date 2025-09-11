#!/usr/bin/env python3
"""
Fix missing user_metadata column in user_profiles table
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from fastapi_app.core.database import get_db_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_user_metadata_column():
    """Add missing user_metadata column to user_profiles table"""
    engine = get_db_engine()
    
    try:
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'user_profiles' 
                AND column_name = 'user_metadata'
            """))
            
            if result.first():
                logger.info("user_metadata column already exists")
                return
            
            # Add the missing column
            logger.info("Adding user_metadata column to user_profiles table...")
            conn.execute(text("""
                ALTER TABLE user_profiles 
                ADD COLUMN user_metadata JSONB DEFAULT '{}'::jsonb
            """))
            
            conn.commit()
            logger.info("Successfully added user_metadata column")
            
    except Exception as e:
        logger.error(f"Failed to add user_metadata column: {e}")
        raise

if __name__ == "__main__":
    add_user_metadata_column()

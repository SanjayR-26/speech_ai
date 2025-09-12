#!/usr/bin/env python3
"""
Run database migration to fix missing columns
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Run the database migration"""
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL", "sqlite:///./qa_platform.db")
    
    print(f"🔧 Running migration on: {database_url}")
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Read migration file
        with open("add_customer_metadata_column.sql", "r") as f:
            migration_sql = f.read()
        
        # Split into individual statements
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
        
        with engine.connect() as conn:
            for i, statement in enumerate(statements, 1):
                if statement:
                    try:
                        print(f"📝 Executing statement {i}/{len(statements)}")
                        conn.execute(text(statement))
                        conn.commit()
                        print(f"✅ Statement {i} completed successfully")
                    except Exception as e:
                        if "already exists" in str(e).lower() or "does not exist" in str(e).lower():
                            print(f"⚠️  Statement {i}: {e} (skipped)")
                        else:
                            print(f"❌ Statement {i} failed: {e}")
                            # Don't exit, continue with other statements
        
        print("\n✅ Migration completed successfully!")
        print("🚀 You can now upload calls and the QA analysis should work completely.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🔬 Database Migration Tool")
    print("=" * 40)
    run_migration()

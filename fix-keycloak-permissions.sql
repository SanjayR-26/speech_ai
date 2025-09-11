-- Fix Keycloak Database Permissions
-- Run this on your RDS keycloak database

-- Connect to the keycloak database
\c keycloak

-- Grant all privileges on the public schema to keycloak_user
GRANT ALL ON SCHEMA public TO keycloak_user;

-- Grant create privileges on the database
GRANT CREATE ON DATABASE keycloak TO keycloak_user;

-- Grant all privileges on all tables in public schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO keycloak_user;

-- Grant all privileges on all sequences in public schema
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO keycloak_user;

-- Grant default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO keycloak_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO keycloak_user;

-- Make keycloak_user owner of public schema (this ensures full access)
ALTER SCHEMA public OWNER TO keycloak_user;

-- Verify permissions
\dp public.*

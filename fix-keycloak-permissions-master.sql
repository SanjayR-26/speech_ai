-- Fix Keycloak Database Permissions
-- IMPORTANT: Run this as the MASTER USER (dbadmin or postgres), NOT as keycloak_user

-- Connect to the keycloak database as master user
\c keycloak

-- Drop and recreate keycloak_user with proper permissions
DROP USER IF EXISTS keycloak_user;
CREATE USER keycloak_user WITH PASSWORD 'QAdbadmin_kc_12345';

-- Grant database-level privileges
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak_user;

-- Make keycloak_user a superuser (for development/testing)
ALTER USER keycloak_user WITH SUPERUSER;

-- OR if you don't want superuser, grant specific privileges:
-- ALTER USER keycloak_user WITH CREATEDB CREATEROLE;

-- Grant all privileges on the public schema
GRANT ALL ON SCHEMA public TO keycloak_user;
ALTER SCHEMA public OWNER TO keycloak_user;

-- Grant all privileges on all existing tables and sequences
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO keycloak_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO keycloak_user;

-- Grant default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO keycloak_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO keycloak_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO keycloak_user;

-- Verify the user has proper privileges
SELECT 
    r.rolname,
    r.rolsuper,
    r.rolinherit,
    r.rolcreaterole,
    r.rolcreatedb,
    r.rolcanlogin,
    r.rolreplication
FROM pg_roles r 
WHERE r.rolname = 'keycloak_user';

-- Show schema privileges
SELECT 
    schemaname,
    schemaowner,
    has_schema_privilege('keycloak_user', schemaname, 'CREATE') as can_create,
    has_schema_privilege('keycloak_user', schemaname, 'USAGE') as can_use
FROM pg_namespace n
JOIN information_schema.schemata s ON n.nspname = s.schema_name
WHERE s.schema_name = 'public';

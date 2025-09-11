-- Fix Keycloak Database Permissions (Without Dropping User)
-- IMPORTANT: Run this as the MASTER USER (dbadmin), NOT as keycloak_user

-- Connect to the keycloak database as master user
\c keycloak

-- Make keycloak_user a superuser (simplest fix)
ALTER USER keycloak_user WITH SUPERUSER;

-- Grant database-level privileges
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak_user;

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

-- Verify the user now has superuser privileges
SELECT 
    r.rolname,
    r.rolsuper,
    r.rolinherit,
    r.rolcreaterole,
    r.rolcreatedb,
    r.rolcanlogin
FROM pg_roles r 
WHERE r.rolname = 'keycloak_user';

-- Show success message
SELECT 'keycloak_user permissions fixed - now has SUPERUSER privileges' as status;

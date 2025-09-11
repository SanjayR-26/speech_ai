-- Check what privileges the current user has
-- Run this to see what user you're connected as and their privileges

-- Show current user
SELECT current_user, session_user;

-- Show all users and their privileges
SELECT 
    r.rolname as username,
    r.rolsuper as is_superuser,
    r.rolinherit as can_inherit,
    r.rolcreaterole as can_create_roles,
    r.rolcreatedb as can_create_db,
    r.rolcanlogin as can_login,
    r.rolreplication as can_replicate
FROM pg_roles r 
ORDER BY r.rolname;

-- Show database ownership
SELECT datname, datdba::regrole as owner 
FROM pg_database 
WHERE datname IN ('keycloak', 'postgres');

-- Show who can grant superuser
SELECT rolname FROM pg_roles WHERE rolsuper = true;

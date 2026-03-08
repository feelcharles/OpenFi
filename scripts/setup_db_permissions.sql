-- Database permissions setup for least privilege principle
-- Requirements: 42.9

-- Create read-only user for reporting/monitoring
CREATE USER IF NOT EXISTS openfi_readonly WITH PASSWORD 'CHANGE_ME_READONLY';

-- Grant connect permission
GRANT CONNECT ON DATABASE openfi TO openfi_readonly;

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO openfi_readonly;

-- Grant SELECT on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO openfi_readonly;

-- Grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO openfi_readonly;

-- Create application user with limited permissions
CREATE USER IF NOT EXISTS openfi_app WITH PASSWORD 'CHANGE_ME_APP';

-- Grant connect permission
GRANT CONNECT ON DATABASE openfi TO openfi_app;

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO openfi_app;

-- Grant SELECT, INSERT, UPDATE, DELETE on specific tables
-- (Exclude sensitive admin tables if any)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO openfi_app;

-- Grant usage on sequences (for auto-increment IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO openfi_app;

-- Grant permissions on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO openfi_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public 
    GRANT USAGE, SELECT ON SEQUENCES TO openfi_app;

-- Revoke dangerous permissions from application user
REVOKE CREATE ON SCHEMA public FROM openfi_app;
REVOKE DROP ON ALL TABLES IN SCHEMA public FROM openfi_app;
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM openfi_app;

-- Create admin user for migrations and schema changes
CREATE USER IF NOT EXISTS openfi_admin WITH PASSWORD 'CHANGE_ME_ADMIN';

-- Grant all privileges to admin
GRANT ALL PRIVILEGES ON DATABASE openfi TO openfi_admin;
GRANT ALL PRIVILEGES ON SCHEMA public TO openfi_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO openfi_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO openfi_admin;

-- Set default privileges for admin
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
    GRANT ALL PRIVILEGES ON TABLES TO openfi_admin;

ALTER DEFAULT PRIVILEGES IN SCHEMA public 
    GRANT ALL PRIVILEGES ON SEQUENCES TO openfi_admin;

-- Revoke public schema creation
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Log permissions setup
DO $$
BEGIN
    RAISE NOTICE 'Database permissions configured successfully';
    RAISE NOTICE 'Users created:';
    RAISE NOTICE '  - openfi_readonly: Read-only access for monitoring';
    RAISE NOTICE '  - openfi_app: Application user with limited permissions';
    RAISE NOTICE '  - openfi_admin: Admin user for migrations';
    RAISE NOTICE '';
    RAISE NOTICE 'IMPORTANT: Change default passwords immediately!';
END $$;

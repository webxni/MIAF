-- Enable required Postgres extensions for MIAF.
-- pgvector: semantic memory embeddings (Phase 7).
-- pgcrypto: gen_random_uuid(), digest helpers used across phases.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Production: a non-super app role connects to run the live workload.
-- Migrations and tests still use POSTGRES_USER (the superuser admin).
-- Set MIAF_APP_ROLE_PASSWORD when running prod compose to enable this.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'miaf_app') THEN
    CREATE ROLE miaf_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD 'change-me-app-role-password';
  END IF;
END
$$;

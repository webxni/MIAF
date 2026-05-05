-- Enable required Postgres extensions for FinClaw.
-- pgvector: semantic memory embeddings (Phase 7).
-- pgcrypto: gen_random_uuid(), digest helpers used across phases.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

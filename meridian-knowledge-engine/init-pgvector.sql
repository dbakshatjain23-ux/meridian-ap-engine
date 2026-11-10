-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the uuid-ossp extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the btree_gin extension for composite indexes
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Set default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO meridian;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO meridian;
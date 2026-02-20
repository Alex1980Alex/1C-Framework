-- PostgreSQL initialization for PDF Vector & Graph Framework
-- Runs on first container start via docker-entrypoint-initdb.d

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- Trigram index for fuzzy search
CREATE EXTENSION IF NOT EXISTS btree_gin;    -- GIN index support

-- Schema for document metadata
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    file_hash TEXT UNIQUE NOT NULL,
    page_count INTEGER DEFAULT 0,
    file_size_bytes BIGINT DEFAULT 0,
    indexed_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Schema for chunks
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    page_number INTEGER,
    section_title TEXT,
    breadcrumb TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Schema for conversations (Phase 9)
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Schema for feedback (Phase 22)
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    chunk_id TEXT,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Schema for audit log (Phase 40)
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id TEXT,
    query TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_section ON chunks(section_title);
CREATE INDEX IF NOT EXISTS idx_conversations_thread ON conversations(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_event ON audit_log(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, created_at);

-- GIN index for JSONB metadata search
CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON chunks USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin(metadata);

-- Trigram index for fuzzy text search
CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING gin(content gin_trgm_ops);

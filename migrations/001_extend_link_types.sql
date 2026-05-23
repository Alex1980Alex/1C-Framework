-- Migration 001: Extend link_type CHECK constraint
-- Adds: promoted_to, superseded_by, mirrors, graph_node
-- SQLite doesn't support ALTER TABLE DROP CONSTRAINT,
-- so we use CREATE NEW + COPY DATA + DROP OLD pattern.

BEGIN TRANSACTION;

-- Step 1: Create new table with expanded CHECK
CREATE TABLE entity_links_new (
    link_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    link_type TEXT NOT NULL,
    strength REAL NOT NULL DEFAULT 0.8,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    metadata TEXT,
    bidirectional INTEGER DEFAULT 0,
    expires_at TEXT,
    CHECK (strength >= 0.0 AND strength <= 1.0),
    CHECK (link_type IN (
        'based_on', 'supports', 'contradicts',
        'extends', 'derives_from', 'session_context',
        'promoted_to', 'superseded_by', 'mirrors', 'graph_node'
    ))
);

-- Step 2: Copy data
INSERT INTO entity_links_new
    SELECT * FROM entity_links;

-- Step 3: Drop old table
DROP TABLE entity_links;

-- Step 4: Rename
ALTER TABLE entity_links_new RENAME TO entity_links;

-- Step 5: Recreate indexes
CREATE INDEX idx_links_source ON entity_links(source_id);
CREATE INDEX idx_links_target ON entity_links(target_id);
CREATE INDEX idx_links_type ON entity_links(link_type);
CREATE INDEX idx_links_strength ON entity_links(strength);
CREATE INDEX idx_links_source_type ON entity_links(source_id, link_type);
CREATE INDEX idx_links_target_type ON entity_links(target_id, link_type);
CREATE INDEX idx_links_created ON entity_links(created_at);

-- Step 6: Update schema version
INSERT OR REPLACE INTO schema_info (key, value) VALUES ('version', '2');

COMMIT;

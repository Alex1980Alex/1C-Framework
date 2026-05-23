-- Rollback migration 001: Revert link_type CHECK to original 6 types
-- WARNING: Any links using new types (promoted_to, superseded_by, mirrors, graph_node)
-- will be DELETED during rollback.

BEGIN TRANSACTION;

-- Step 1: Create table with original CHECK
CREATE TABLE entity_links_old (
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
        'extends', 'derives_from', 'session_context'
    ))
);

-- Step 2: Copy only valid (old-type) links
INSERT INTO entity_links_old
    SELECT * FROM entity_links
    WHERE link_type IN (
        'based_on', 'supports', 'contradicts',
        'extends', 'derives_from', 'session_context'
    );

-- Step 3: Drop expanded table
DROP TABLE entity_links;

-- Step 4: Rename
ALTER TABLE entity_links_old RENAME TO entity_links;

-- Step 5: Recreate indexes
CREATE INDEX idx_links_source ON entity_links(source_id);
CREATE INDEX idx_links_target ON entity_links(target_id);
CREATE INDEX idx_links_type ON entity_links(link_type);
CREATE INDEX idx_links_strength ON entity_links(strength);
CREATE INDEX idx_links_source_type ON entity_links(source_id, link_type);
CREATE INDEX idx_links_target_type ON entity_links(target_id, link_type);
CREATE INDEX idx_links_created ON entity_links(created_at);

-- Step 6: Revert schema version
INSERT OR REPLACE INTO schema_info (key, value) VALUES ('version', '1');

COMMIT;

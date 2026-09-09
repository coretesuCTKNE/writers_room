-- Phase 1.5: Script Core — persistence, sessions, git-like versioning
-- Append-only design: versions are immutable, reverts/edits create new versions.

CREATE TABLE IF NOT EXISTS script_branches (
    branch_id String DEFAULT generateUUIDv4(),
    script_id String,
    name String,
    head_version_id String DEFAULT '',
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (script_id, branch_id);

CREATE TABLE IF NOT EXISTS script_versions (
    version_id String DEFAULT generateUUIDv4(),
    script_id String,
    branch_id String,
    parent_version_id String DEFAULT '',
    message String DEFAULT '',
    author String DEFAULT '',
    raw_fountain String,
    content_hash String,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (script_id, branch_id, created_at, version_id);

CREATE TABLE IF NOT EXISTS script_elements (
    version_id String,
    element_id String,
    scene_number UInt16 DEFAULT 0,
    type Enum8(
        'scene_heading' = 1,
        'action' = 2,
        'character' = 3,
        'parenthetical' = 4,
        'dialogue' = 5,
        'transition' = 6
    ),
    ordinal UInt32,
    text String DEFAULT '',
    character_name String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (version_id, ordinal);

CREATE TABLE IF NOT EXISTS active_sessions (
    principal String,
    script_id String DEFAULT '',
    branch_id String DEFAULT '',
    version_id String DEFAULT '',
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (principal);

CREATE DATABASE IF NOT EXISTS greenlight;

CREATE TABLE IF NOT EXISTS scripts (
    id String DEFAULT generateUUIDv4(),
    title String,
    author String,
    draft UInt16 DEFAULT 1,
    genre String DEFAULT '',
    hash String,
    html_rendered String DEFAULT '',
    owner String DEFAULT '',
    deleted_at DateTime DEFAULT toDateTime(0),
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (id);

CREATE TABLE IF NOT EXISTS scenes (
    script_id String,
    scene_id String,
    heading String,
    page UInt16,
    cast Array(String),
    locations Array(String),
    props Array(String),
    ordinal UInt16,
    setting String DEFAULT '',
    time_of_day String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (script_id, ordinal);

CREATE TABLE IF NOT EXISTS characters (
    script_id String,
    character_id String,
    name String,
    role String DEFAULT '',
    register String DEFAULT '',
    notes String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (script_id, character_id);

CREATE TABLE IF NOT EXISTS bible_facts (
    script_id String,
    character_id String,
    fact_id String,
    category String,
    claim String,
    source_page UInt16 DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (script_id, character_id, fact_id);

CREATE TABLE IF NOT EXISTS coverage (
    coverage_id String DEFAULT generateUUIDv4(),
    script_id String,
    verdict String,
    logline String,
    synopsis String,
    scores String DEFAULT '{}',
    analyst_notes String DEFAULT '',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, created_at);

CREATE TABLE IF NOT EXISTS notes (
    note_id String DEFAULT generateUUIDv4(),
    coverage_id String,
    scene_id String DEFAULT '',
    severity String DEFAULT 'info',
    message String,
    span String DEFAULT ''
) ENGINE = MergeTree()
ORDER BY (coverage_id, note_id);

CREATE TABLE IF NOT EXISTS actor_profiles (
    actor_id String DEFAULT generateUUIDv4(),
    name String,
    cadence_tags Array(String),
    register String DEFAULT '',
    comedic_engine String DEFAULT '',
    signature_moves Array(String),
    source_notes String DEFAULT '',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (name, created_at);

CREATE TABLE IF NOT EXISTS sandbox_runs (
    run_id String DEFAULT generateUUIDv4(),
    script_id String,
    scene_id String,
    casting String DEFAULT '{}',
    rewritten_scene_md String DEFAULT '',
    chemistry_read_md String DEFAULT '',
    beats_preserved Bool DEFAULT false,
    beat_diff String DEFAULT '{}',
    lt_findings_summary String DEFAULT '{}',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, scene_id, created_at);

CREATE TABLE IF NOT EXISTS voice_casting (
    script_id String,
    character_name String,
    gemini_voice_id String,
    base_pitch Float32 DEFAULT 1.0,
    base_speed Float32 DEFAULT 1.0,
    updated_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, character_name);

CREATE TABLE IF NOT EXISTS table_read_takes (
    take_id String DEFAULT generateUUIDv4(),
    script_id String,
    scene_number UInt16,
    scene_hash String,
    result_json String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, scene_number, created_at);

CREATE TABLE IF NOT EXISTS tts_turn_cache (
    turn_hash String,
    voice_id String,
    audio_url String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (turn_hash, voice_id);

CREATE TABLE IF NOT EXISTS generated_audio_assets (
    asset_id String DEFAULT generateUUIDv4(),
    script_id String,
    scene_id String,
    purpose String,
    audio_url String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, scene_id, purpose);

CREATE TABLE IF NOT EXISTS scene_edits (
    edit_id String DEFAULT generateUUIDv4(),
    script_id String,
    scene_id String,
    source String,
    before_md String DEFAULT '',
    after_md String DEFAULT '',
    diff String DEFAULT '{}',
    lt_findings_summary String DEFAULT '{}',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, scene_id, created_at);

CREATE TABLE IF NOT EXISTS proofread_runs (
    run_id String DEFAULT generateUUIDv4(),
    script_id String,
    tool_version String DEFAULT '',
    lang String DEFAULT 'en-US',
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, created_at);

CREATE TABLE IF NOT EXISTS proofread_findings (
    run_id String,
    script_id String,
    scene_id String DEFAULT '',
    page UInt16 DEFAULT 0,
    rule_id String DEFAULT '',
    category String,
    severity String DEFAULT 'info',
    message String,
    suggestion String DEFAULT '',
    span_start UInt32 DEFAULT 0,
    span_end UInt32 DEFAULT 0,
    ts DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, run_id, page);

CREATE TABLE IF NOT EXISTS script_access (
    script_id String,
    principal String,
    role String,
    granted_by String DEFAULT '',
    granted_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, principal);

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
    word_count UInt32 DEFAULT 0,
    page_count UInt16 DEFAULT 0,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY (script_id, branch_id, created_at, version_id);

CREATE TABLE IF NOT EXISTS active_sessions (
    principal String,
    script_id String DEFAULT '',
    branch_id String DEFAULT '',
    version_id String DEFAULT '',
    -- DateTime64 ms precision: second-resolution DateTime made two set_active
    -- writes in the same second tie, so get_active could return a stale row.
    -- Plain MergeTree, NOT ReplacingMergeTree: merge-time dedup on the shared
    -- engine was observed to keep arbitrary (non-max) survivors, silently
    -- reverting sessions. get_active() does argMax-style reads instead.
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree
ORDER BY (principal, updated_at);

CREATE TABLE IF NOT EXISTS dictation_sessions (
    session_id String DEFAULT generateUUIDv4(),
    script_id String,
    scene_number UInt16 DEFAULT 0,
    model String DEFAULT '',
    vocabulary_count UInt16 DEFAULT 0,
    created_at DateTime DEFAULT now(),
    ended_at DateTime DEFAULT toDateTime(0),
    ended Bool DEFAULT false
) ENGINE = ReplacingMergeTree(ended_at)
ORDER BY (script_id, session_id);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id String DEFAULT generateUUIDv4(),
    agent String,
    script_id String DEFAULT '',
    scene_id String DEFAULT '',
    status String DEFAULT 'completed',
    prompt String DEFAULT '',
    result_json String DEFAULT '{}',
    elapsed_s Float64 DEFAULT 0,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (agent, script_id, created_at);

CREATE TABLE IF NOT EXISTS scene_stats (
    script_id String,
    version_id String,
    scene_number UInt16,
    heading String,
    setting String DEFAULT '',
    time_of_day String DEFAULT '',
    dialogue_lines UInt16 DEFAULT 0,
    action_lines UInt16 DEFAULT 0,
    dialogue_words UInt32 DEFAULT 0,
    action_words UInt32 DEFAULT 0,
    characters Array(String),
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (script_id, version_id, scene_number);

CREATE TABLE IF NOT EXISTS writing_goals (
    goal_id String DEFAULT generateUUIDv4(),
    script_id String,
    metric String,
    target UInt32,
    deadline Date DEFAULT toDate(0),
    note String DEFAULT '',
    active Bool DEFAULT true,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (script_id, goal_id);

-- Column additions for databases created before the story-ops schema
-- (CREATE IF NOT EXISTS does not evolve existing tables).
ALTER TABLE greenlight.scenes
    ADD COLUMN IF NOT EXISTS setting String DEFAULT '';
ALTER TABLE greenlight.scenes
    ADD COLUMN IF NOT EXISTS time_of_day String DEFAULT '';
ALTER TABLE greenlight.scripts
    ADD COLUMN IF NOT EXISTS owner String DEFAULT '';
ALTER TABLE greenlight.scripts
    ADD COLUMN IF NOT EXISTS deleted_at DateTime DEFAULT toDateTime(0);
ALTER TABLE greenlight.script_versions
    ADD COLUMN IF NOT EXISTS word_count UInt32 DEFAULT 0;
ALTER TABLE greenlight.script_versions
    ADD COLUMN IF NOT EXISTS page_count UInt16 DEFAULT 0;
ALTER TABLE greenlight.dictation_sessions
    ADD COLUMN IF NOT EXISTS ended Bool DEFAULT false;
ALTER TABLE greenlight.dictation_sessions
    ADD COLUMN IF NOT EXISTS ended_at DateTime DEFAULT toDateTime(0);

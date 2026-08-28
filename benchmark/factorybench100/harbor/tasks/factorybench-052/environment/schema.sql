PRAGMA foreign_keys = ON;

CREATE TABLE organizations (
    organization_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ledger_currency TEXT NOT NULL
);

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    approval_limit REAL NOT NULL DEFAULT 0
);

CREATE TABLE evidence_files (
    asset_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    path TEXT NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    media_type TEXT NOT NULL,
    extracted_text TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    UNIQUE (task_id, path)
);

CREATE TABLE api_fixtures (
    fixture_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    effect_json TEXT,
    read_only INTEGER NOT NULL CHECK (read_only IN (0, 1)),
    UNIQUE (task_id, tool_name, arguments_json)
);

CREATE TABLE resource_state (
    task_id TEXT NOT NULL,
    system TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    status TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    revision INTEGER NOT NULL,
    PRIMARY KEY (task_id, resource_id)
);

CREATE TABLE answers (
    task_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (task_id, field)
);

CREATE TABLE audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX idx_evidence_task ON evidence_files(task_id);
CREATE INDEX idx_fixtures_task_tool ON api_fixtures(task_id, tool_name);
CREATE INDEX idx_resource_task_system ON resource_state(task_id, system);
CREATE INDEX idx_audit_task ON audit_log(task_id);

-- CodeOracle migration 003 — ops: source health, heartbeats, config history
-- additive-only per UNIVERSAL_DISCIPLINE §I.1

CREATE TABLE IF NOT EXISTS data_source_health (
    id              BIGSERIAL PRIMARY KEY,
    cycle_ts        TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,
    latency_ms      INT,
    ok              BOOLEAN NOT NULL,
    error_class     TEXT,
    cached_used     BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_dsh_source_ts ON data_source_health (source, cycle_ts DESC);

CREATE TABLE IF NOT EXISTS heartbeats (
    id            BIGSERIAL PRIMARY KEY,
    cycle_ts      TIMESTAMPTZ NOT NULL,
    task_name     TEXT NOT NULL,
    duration_ms   INT NOT NULL,
    ok            BOOLEAN NOT NULL,
    notes         TEXT
);
CREATE INDEX IF NOT EXISTS ix_heartbeats_task_ts ON heartbeats (task_name, cycle_ts DESC);

CREATE TABLE IF NOT EXISTS universe_config_history (
    id            BIGSERIAL PRIMARY KEY,
    changed_ts    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    param         TEXT NOT NULL,
    old_value     TEXT,
    new_value     TEXT,
    rationale     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_uch_ts ON universe_config_history (changed_ts DESC);

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_ts  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sha256      TEXT NOT NULL
);

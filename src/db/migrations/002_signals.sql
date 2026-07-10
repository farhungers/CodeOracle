-- CodeOracle migration 002 — edges + signals + resolutions + shadow_log
-- additive-only per UNIVERSAL_DISCIPLINE §I.1

CREATE TABLE IF NOT EXISTS edges (
    edge_code       TEXT PRIMARY KEY,
    version         INT NOT NULL DEFAULT 1,
    status          TEXT NOT NULL,
    prereg_path     TEXT NOT NULL,
    prereg_sha256   TEXT NOT NULL,
    promoted_at     TIMESTAMPTZ,
    parked_at       TIMESTAMPTZ,
    kill_reason     TEXT,
    CHECK (status IN ('shadow','live','parked','killed','backlog'))
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id         BIGSERIAL PRIMARY KEY,
    emitted_ts        TIMESTAMPTZ NOT NULL,
    edge_code         TEXT NOT NULL REFERENCES edges(edge_code),
    mode              TEXT NOT NULL,
    chain             TEXT NOT NULL,
    token_addr        TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    direction         TEXT NOT NULL,
    medal             SMALLINT NOT NULL,
    entry_price       NUMERIC(30,10) NOT NULL,
    stop_price        NUMERIC(30,10) NOT NULL,
    tp1_price         NUMERIC(30,10) NOT NULL,
    thesis_window_min INT NOT NULL,
    entry_window_min  INT NOT NULL,
    slip_est_bps      INT,
    tg_message_id     BIGINT,
    tg_chat_id        BIGINT,
    card_json         JSONB NOT NULL,
    CHECK (mode IN ('shadow','live','muted')),
    CHECK (direction IN ('long','short_advisory','short_perp')),
    CHECK (medal BETWEEN 1 AND 5)
);
CREATE INDEX IF NOT EXISTS ix_signals_edge_ts ON signals (edge_code, emitted_ts DESC);
CREATE INDEX IF NOT EXISTS ix_signals_token ON signals (chain, token_addr);
CREATE INDEX IF NOT EXISTS ix_signals_mode_ts ON signals (mode, emitted_ts DESC);

CREATE TABLE IF NOT EXISTS resolutions (
    signal_id       BIGINT PRIMARY KEY REFERENCES signals(signal_id),
    resolved_ts     TIMESTAMPTZ NOT NULL,
    outcome         TEXT NOT NULL,
    exit_price      NUMERIC(30,10),
    r_multiple      NUMERIC(8,4) NOT NULL,
    minutes_to_res  INT NOT NULL,
    notes           TEXT,
    CHECK (outcome IN ('tp1','sl','expired','chased','invalid'))
);
CREATE INDEX IF NOT EXISTS ix_resolutions_ts ON resolutions (resolved_ts DESC);

CREATE TABLE IF NOT EXISTS shadow_log (
    shadow_id            BIGSERIAL PRIMARY KEY,
    would_have_fired_ts  TIMESTAMPTZ NOT NULL,
    edge_code            TEXT NOT NULL REFERENCES edges(edge_code),
    chain                TEXT NOT NULL,
    token_addr           TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    card_json            JSONB NOT NULL,
    entry_price          NUMERIC(30,10) NOT NULL,
    stop_price           NUMERIC(30,10) NOT NULL,
    tp1_price            NUMERIC(30,10) NOT NULL,
    thesis_window_min    INT NOT NULL,
    resolved_ts          TIMESTAMPTZ,
    outcome              TEXT,
    r_multiple           NUMERIC(8,4),
    CHECK (outcome IS NULL OR outcome IN ('tp1','sl','expired','chased','invalid'))
);
CREATE INDEX IF NOT EXISTS ix_shadow_edge_ts ON shadow_log (edge_code, would_have_fired_ts DESC);
CREATE INDEX IF NOT EXISTS ix_shadow_resolved ON shadow_log (edge_code, resolved_ts DESC);

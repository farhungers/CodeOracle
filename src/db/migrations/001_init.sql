-- CodeOracle migration 001 — universe snapshots + tokens + token_states
-- additive-only per UNIVERSAL_DISCIPLINE §I.1

CREATE TABLE IF NOT EXISTS universe_snapshots (
    snapshot_id     BIGSERIAL PRIMARY KEY,
    snapshot_ts     TIMESTAMPTZ NOT NULL,
    chain           TEXT NOT NULL,
    token_count     INT NOT NULL,
    source_used     TEXT NOT NULL,
    stale_flag      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_universe_snapshots_ts ON universe_snapshots (snapshot_ts DESC);

CREATE TABLE IF NOT EXISTS tokens (
    token_addr        TEXT NOT NULL,
    chain             TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    name              TEXT,
    first_seen_ts     TIMESTAMPTZ NOT NULL,
    tokenized_stock   BOOLEAN NOT NULL DEFAULT FALSE,
    underlying_ticker TEXT,
    PRIMARY KEY (chain, token_addr)
);

CREATE TABLE IF NOT EXISTS token_states (
    snapshot_id     BIGINT NOT NULL REFERENCES universe_snapshots(snapshot_id),
    token_addr      TEXT NOT NULL,
    chain           TEXT NOT NULL,
    price_usd       NUMERIC(30,10),
    liq_usd         NUMERIC(20,2),
    vol_24h_usd     NUMERIC(20,2),
    mcap_usd        NUMERIC(20,2),
    holder_count    INT,
    top10_pct       NUMERIC(6,4),
    dev_wallet_pct  NUMERIC(6,4),
    lp_locked_until TIMESTAMPTZ,
    contract_badge  TEXT,
    trading_badge   TEXT,
    survives_gate0  BOOLEAN NOT NULL,
    fail_reasons    TEXT[],
    PRIMARY KEY (snapshot_id, chain, token_addr)
);
CREATE INDEX IF NOT EXISTS ix_token_states_recent ON token_states (chain, token_addr, snapshot_id DESC);

CREATE TABLE IF NOT EXISTS tokenized_stock_map (
    chain             TEXT NOT NULL,
    token_addr        TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    underlying_ticker TEXT NOT NULL,
    naming_rule       TEXT NOT NULL DEFAULT 'auto_x_suffix',
    verified_ts       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chain, token_addr)
);

CREATE TABLE IF NOT EXISTS tokenized_stock_unmapped (
    chain          TEXT NOT NULL,
    token_addr     TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    first_seen_ts  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes          TEXT,
    PRIMARY KEY (chain, token_addr)
);

CREATE TABLE IF NOT EXISTS watchlist_pending (
    chain             TEXT NOT NULL,
    token_addr        TEXT NOT NULL,
    first_flagged_ts  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fail_reasons      TEXT[] NOT NULL,
    reeval_after_ts   TIMESTAMPTZ,
    PRIMARY KEY (chain, token_addr)
);

-- RUNNER GENESIS Ω v0.2 additive research schema.
-- SQLite/PostgreSQL-compatible intent; SQLAlchemy Base.metadata.create_all is the runtime
-- migration path in v0.2. This file documents the additive tables for operators.
CREATE TABLE IF NOT EXISTS wallet_metrics (
  id INTEGER PRIMARY KEY,
  wallet_address VARCHAR(128) NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_wallet_metrics_wallet ON wallet_metrics(wallet_address);

CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
  id INTEGER PRIMARY KEY,
  wallet_address VARCHAR(128) NOT NULL,
  source VARCHAR(64) NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  rank INTEGER NULL,
  monthly_pnl FLOAT NULL,
  payload_json TEXT NOT NULL,
  CONSTRAINT uq_leaderboard_wallet_source_time UNIQUE(wallet_address, source, observed_at)
);

CREATE TABLE IF NOT EXISTS smart_token_states (
  id INTEGER PRIMARY KEY,
  token_mint VARCHAR(128) NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  state VARCHAR(32) NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_transitions (
  id INTEGER PRIMARY KEY,
  token_mint VARCHAR(128) NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  old_state VARCHAR(32) NOT NULL,
  new_state VARCHAR(32) NOT NULL,
  reason VARCHAR(128) NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_observations (
  id INTEGER PRIMARY KEY,
  token_mint VARCHAR(128) NULL,
  wallet_address VARCHAR(128) NULL,
  observed_at TIMESTAMP NOT NULL,
  source VARCHAR(64) NOT NULL,
  kind VARCHAR(64) NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rollout_summaries (
  id INTEGER PRIMARY KEY,
  token_mint VARCHAR(128) NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  model VARCHAR(64) NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet_positions (
  id INTEGER PRIMARY KEY,
  wallet_address VARCHAR(128) NOT NULL,
  token_mint VARCHAR(128) NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  state VARCHAR(32) NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actor_clusters (
  id INTEGER PRIMARY KEY,
  token_mint VARCHAR(128) NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  payload_json TEXT NOT NULL
);

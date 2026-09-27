from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class RiskConfig(BaseModel):
    max_position_eur: float = 25.0
    max_account_pct_per_trade: float = 0.08
    max_simultaneous_positions: int = 4
    max_daily_loss_eur: float = 30.0
    max_portfolio_drawdown_pct: float = 0.20
    max_daily_spend_eur: float = 120.0
    max_slippage_pct: float = 0.12
    min_liquidity_usd: float = 10_000.0
    max_dev_holdings_pct: float = 0.12
    max_sniper_pct: float = 0.30
    max_bundle_pct: float = 0.30
    max_suspected_related_concentration_pct: float = 0.35
    max_correlated_exposure_pct: float = 0.35
    min_cluster_fraction_for_exposure: float = 0.50
    min_sellability_score: float = 0.25
    max_manipulation_risk: float = 0.78
    kill_switch: bool = False


class ExecutionConfig(BaseModel):
    latency_ms_mean: float = 1100.0
    latency_ms_std: float = 250.0
    execution_delay_seconds: float = 60.0
    base_fee_bps: float = 35.0
    priority_fee_bps: float = 10.0
    mev_adverse_bps: float = 20.0
    base_slippage_bps: float = 35.0
    impact_coefficient: float = 1.25
    max_liquidity_fraction: float = 0.02
    failed_tx_base_probability: float = 0.015
    partial_fill_enabled: bool = True
    network_base_fee_lamports: int = 5000
    network_priority_fee_lamports: int = 0
    network_signature_count: int = 1


class TraderConfig(BaseModel):
    min_genesis_to_watch: float = 0.55
    min_entry_edge: float = 0.025
    min_hold_score: float = 0.52
    reduce_below_hold_score: float = 0.42
    exit_below_hold_score: float = 0.28
    moonbag_fraction: float = 0.15
    max_adds_per_position: int = 2
    default_position_eur: float = 10.0
    require_trained_for_entry: bool = True
    allow_untrained_paper_entry: bool = True


class SmartCapitalConfig(BaseModel):
    enabled: bool = True
    min_wallet_quality: float = 0.20
    min_strategy_match: float = 0.35
    min_effective_wallets: float = 1.25
    min_consensus: float = 0.55
    min_accumulation: float = 0.45
    min_conviction: float = 0.35
    max_entry_distance_price: float = 1.50
    freshness_half_life_seconds: float = 900.0
    quality_sample_target: int = 30
    state_confirm_threshold: float = 0.62
    state_persistence_threshold: float = 0.68
    distribution_protect_threshold: float = 0.58
    distribution_exit_threshold: float = 0.76


class FomoConfig(BaseModel):
    enabled: bool = False
    minimum_source_confidence: float = 0.35
    maximum_source_age_seconds: float = 900.0
    window_seconds: float = 300.0


class MiroFishConfig(BaseModel):
    enabled: bool = False
    num_rollouts: int = 128
    horizon_seconds: int = 900
    random_seed: int = 20260927
    max_agents: int = 64
    rollout_timeout_ms: int = 250
    use_world_model_prior: bool = True
    require_min_data_quality: float = 0.45
    trigger_min_consensus: float = 0.25
    trigger_min_accumulation: float = 0.20
    trigger_min_top_trader_wave: float = 0.20
    trigger_min_fomo: float = 0.30
    trigger_min_early_formation: float = 0.45
    min_rerun_seconds: float = 20.0
    material_change_threshold: float = 0.08


class PumpDiscoveryConfig(BaseModel):
    enabled: bool = True
    top_traders_enabled: bool = True
    kol_enabled: bool = True
    cohort_enabled: bool = True
    max_snapshot_age_seconds: float = 3600.0


class PersistenceConfig(BaseModel):
    enabled: bool = True


class EarlyFormationConfig(BaseModel):
    enabled: bool = True
    lookback_seconds: float = 60.0
    history_seconds: float = 300.0
    min_elapsed_seconds: float = 20.0
    max_price_runup_for_headroom: float = 0.60
    watch_threshold: float = 0.35
    forming_threshold: float = 0.55


class HeliusHistoryConfig(BaseModel):
    enabled: bool = True
    page_limit: int = 100
    max_pages: int = 5
    min_funding_sol: float = 0.01
    refresh_seconds: float = 21600.0
    max_concurrency: int = 4
    hydrate_max_rows: int = 100000


class ExternalDiscoveryConfig(BaseModel):
    fomoscan_enabled: bool = False
    auto_refresh: bool = False
    refresh_seconds: float = 300.0
    max_wallets_per_refresh: int = 25
    # Legacy split kept for config compatibility; priority scoring supersedes it when enabled.
    top_wallet_backfill_fraction: float = 0.60
    wallet_priority_enabled: bool = True
    wallet_priority_candidate_pool: int = 200
    wallet_priority_rank_weight: float = 0.16
    wallet_priority_rank_momentum_weight: float = 0.10
    wallet_priority_smart_30d_weight: float = 0.20
    wallet_priority_emerging_weight: float = 0.18
    wallet_priority_recent_activity_weight: float = 0.12
    wallet_priority_independence_weight: float = 0.10
    wallet_priority_cohort_weight: float = 0.08
    wallet_priority_data_gap_weight: float = 0.08
    wallet_priority_source_confidence_weight: float = 0.06
    wallet_priority_activity_half_life_seconds: float = 1800.0


class Settings(BaseModel):
    mode: str = "PAPER"
    live_trading: bool = False
    paper_starting_capital_eur: float = 300.0
    currency: str = "EUR"
    features: dict[str, Any] = Field(default_factory=dict)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    trader: TraderConfig = Field(default_factory=TraderConfig)
    smart_capital: SmartCapitalConfig = Field(default_factory=SmartCapitalConfig)
    fomo: FomoConfig = Field(default_factory=FomoConfig)
    mirofish: MiroFishConfig = Field(default_factory=MiroFishConfig)
    pump_discovery: PumpDiscoveryConfig = Field(default_factory=PumpDiscoveryConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    early_formation: EarlyFormationConfig = Field(default_factory=EarlyFormationConfig)
    helius_history: HeliusHistoryConfig = Field(default_factory=HeliusHistoryConfig)
    external_discovery: ExternalDiscoveryConfig = Field(default_factory=ExternalDiscoveryConfig)
    point_in_time: dict[str, Any] = Field(default_factory=lambda: {"strict": True})
    database_url: str = "sqlite:///./runner_genesis.db"
    solana_rpc_http: str = "https://api.mainnet-beta.solana.com"
    solana_rpc_ws: str = "wss://api.mainnet-beta.solana.com"
    helius_api_key: str | None = None
    fomoscan_api_key: str | None = None
    fomoscan_base_url: str = "https://api.fomoscan.sh"

    @property
    def paper_only(self) -> bool:
        return not self.live_trading or self.mode.upper() != "LIVE"


def _deep_update(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v
    return dst


def load_settings(path: str | Path | None = None) -> Settings:
    load_dotenv(dotenv_path=Path(".env"), override=False)
    cfg_path = Path(path or os.getenv("RUNNER_CONFIG", "config/default.yaml"))
    data: dict[str, Any] = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    env_overlay: dict[str, Any] = {}
    if os.getenv("RUNNER_MODE"):
        env_overlay["mode"] = os.environ["RUNNER_MODE"]
    if os.getenv("DATABASE_URL"):
        env_overlay["database_url"] = os.environ["DATABASE_URL"]
    if os.getenv("SOLANA_RPC_HTTP"):
        env_overlay["solana_rpc_http"] = os.environ["SOLANA_RPC_HTTP"]
    if os.getenv("SOLANA_RPC_WS"):
        env_overlay["solana_rpc_ws"] = os.environ["SOLANA_RPC_WS"]
    if os.getenv("HELIUS_API_KEY"):
        env_overlay["helius_api_key"] = os.environ["HELIUS_API_KEY"]
    if os.getenv("FOMOSCAN_API_KEY"):
        env_overlay["fomoscan_api_key"] = os.environ["FOMOSCAN_API_KEY"]
    if os.getenv("FOMOSCAN_BASE_URL"):
        env_overlay["fomoscan_base_url"] = os.environ["FOMOSCAN_BASE_URL"]
    if os.getenv("LIVE_TRADING") is not None:
        env_overlay["live_trading"] = os.getenv("LIVE_TRADING", "false").lower() == "true"
    if os.getenv("PAPER_STARTING_CAPITAL_EUR"):
        env_overlay["paper_starting_capital_eur"] = float(os.environ["PAPER_STARTING_CAPITAL_EUR"])
    _deep_update(data, env_overlay)
    settings = Settings.model_validate(data)
    if settings.live_trading and settings.mode.upper() != "LIVE":
        raise ValueError("LIVE_TRADING=true requires mode=LIVE explicitly")
    return settings

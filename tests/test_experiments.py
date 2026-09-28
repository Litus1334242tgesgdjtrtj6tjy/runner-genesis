from runner_genesis.config import Settings
from runner_genesis.experiments import DEFAULT_ABLATIONS, settings_for_variant


def test_ablation_variants_are_backtest_only_and_external_fetch_disabled():
    base = Settings(mode="PAPER", live_trading=False)
    for variant in DEFAULT_ABLATIONS:
        cfg = settings_for_variant(base, variant)
        assert cfg.mode == "BACKTEST"
        assert cfg.live_trading is False
        assert cfg.external_discovery.auto_refresh is False
        assert cfg.external_discovery.fomoscan_enabled is False
        assert cfg.features["database_persistence"]["enabled"] is False
        assert bool(cfg.features["flywire"]["enabled"]) is variant.flywire
        assert cfg.mirofish.enabled is variant.mirofish
        assert cfg.fomo.enabled is variant.fomo
        assert cfg.pump_discovery.enabled is variant.pump_discovery

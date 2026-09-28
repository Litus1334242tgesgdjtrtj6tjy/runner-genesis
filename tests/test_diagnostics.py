from runner_genesis.config import Settings
from runner_genesis.diagnostics import build_doctor_report


def test_doctor_never_reports_real_research_ready_without_helius_key():
    settings = Settings()
    settings.helius_api_key = None
    settings.fomoscan_api_key = None
    report = build_doctor_report(settings)
    assert report["live_trading"] is False
    assert report["research_ready"] is False
    assert report["automatic_pump_discovery_ready"] is False
    assert "HELIUS_API_KEY_REQUIRED_FOR_REAL_ONCHAIN_HISTORY_AND_SHADOW" in report["blockers_or_optional_missing"]


def test_doctor_marks_fomoscan_as_optional_for_full_auto_discovery():
    settings = Settings(helius_api_key="test")
    settings.fomoscan_api_key = None
    report = build_doctor_report(settings)
    assert report["research_ready"] is True
    assert report["automatic_pump_discovery_ready"] is False

from __future__ import annotations
from datetime import datetime
import json
from typing import Any
from sqlalchemy import create_engine, String, Float, Integer, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.exc import IntegrityError


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    wallet: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default='normalized')
    asset_match_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    payload_json: Mapped[str] = mapped_column(Text)


class DecisionRow(Base):
    __tablename__ = 'decisions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(32))
    model_version: Mapped[str] = mapped_column(String(128))
    snapshot_json: Mapped[str] = mapped_column(Text)


class FillRow(Base):
    __tablename__ = 'paper_fills'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    side: Mapped[str] = mapped_column(String(8))
    filled_eur: Mapped[float] = mapped_column(Float)
    execution_price: Mapped[float] = mapped_column(Float)
    fees_eur: Mapped[float] = mapped_column(Float)
    failed: Mapped[bool] = mapped_column(Boolean, default=False)
    payload_json: Mapped[str] = mapped_column(Text)


class WalletMetricRow(Base):
    __tablename__ = 'wallet_metrics'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class LeaderboardSnapshotRow(Base):
    __tablename__ = 'leaderboard_snapshots'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(128), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('wallet_address', 'source', 'observed_at', name='uq_leaderboard_wallet_source_time'),)




class WalletPositionRow(Base):
    __tablename__ = 'wallet_positions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(128), index=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class ActorClusterRow(Base):
    __tablename__ = 'actor_clusters'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class SmartTokenStateRow(Base):
    __tablename__ = 'smart_token_states'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class StateTransitionRow(Base):
    __tablename__ = 'state_transitions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    old_state: Mapped[str] = mapped_column(String(32))
    new_state: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(128))
    payload_json: Mapped[str] = mapped_column(Text)


class DiscoveryObservationRow(Base):
    __tablename__ = 'discovery_observations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_mint: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    wallet_address: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)


class RolloutSummaryRow(Base):
    __tablename__ = 'rollout_summaries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    model: Mapped[str] = mapped_column(String(64), default='MIROFISH')
    payload_json: Mapped[str] = mapped_column(Text)


class PaperTradeUpdateRow(Base):
    __tablename__ = 'paper_trade_updates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    update_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class BacktestRunRow(Base):
    __tablename__ = 'backtest_runs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    variant: Mapped[str] = mapped_column(String(128), index=True)
    dataset_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)


class BacktestMetricRow(Base):
    __tablename__ = 'backtest_metrics'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    metric_name: Mapped[str] = mapped_column(String(128), index=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    slice_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class ModelVersionRow(Base):
    __tablename__ = 'model_versions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(128), index=True)
    model_version: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('model_name', 'model_version', name='uq_model_name_version'),)


class ExperimentResultRow(Base):
    __tablename__ = 'experiment_results'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    variant: Mapped[str] = mapped_column(String(128), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


def make_session_factory(url: str):
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(',', ':'))


class RuntimeRepository:
    """Small append-only persistence layer for research reproducibility."""

    def __init__(self, url: str):
        self.Session = make_session_factory(url)

    def record_event(self, e) -> None:
        with self.Session() as s:
            s.add(EventRow(
                event_id=e.event_id, timestamp=e.timestamp, token_mint=e.token_mint,
                event_type=e.event_type.value, wallet=e.wallet, source=e.source,
                asset_match_verified=e.asset_match_verified,
                payload_json=e.model_dump_json(),
            ))
            try:
                s.commit()
            except IntegrityError:
                s.rollback()

    def record_decision(self, d) -> None:
        with self.Session() as s:
            s.add(DecisionRow(timestamp=d.decision_time, token_mint=d.token_mint, action=d.action, model_version=d.model_version, snapshot_json=d.model_dump_json()))
            s.commit()

    def record_fill(self, fill) -> None:
        if fill is None:
            return
        with self.Session() as s:
            s.add(FillRow(timestamp=fill.timestamp, token_mint=fill.token_mint, side=fill.side, filled_eur=fill.filled_eur, execution_price=fill.execution_price, fees_eur=fill.fees_eur, failed=fill.failed, payload_json=_json(fill.__dict__)))
            s.commit()

    def record_wallet_metrics(self, wallet: str, observed_at: datetime, payload: dict) -> None:
        with self.Session() as s:
            s.add(WalletMetricRow(wallet_address=wallet, observed_at=observed_at, payload_json=_json(payload)))
            s.commit()

    def record_smart_state(self, mint: str, observed_at: datetime, payload: dict) -> None:
        with self.Session() as s:
            s.add(SmartTokenStateRow(token_mint=mint, observed_at=observed_at, state=str(payload.get('smart_capital_state') or 'UNKNOWN'), payload_json=_json(payload)))
            s.commit()

    def record_wallet_position(self, wallet: str, mint: str, observed_at: datetime, payload: dict) -> None:
        with self.Session() as s:
            s.add(WalletPositionRow(wallet_address=wallet, token_mint=mint, observed_at=observed_at, state=str(payload.get('state') or 'UNKNOWN'), payload_json=_json(payload)))
            s.commit()

    def record_actor_cluster(self, mint: str, observed_at: datetime, payload: dict) -> None:
        with self.Session() as s:
            s.add(ActorClusterRow(token_mint=mint, observed_at=observed_at, payload_json=_json(payload)))
            s.commit()

    def record_transition(self, tr) -> None:
        with self.Session() as s:
            s.add(StateTransitionRow(token_mint=tr.token_mint, timestamp=tr.timestamp, old_state=tr.old_state, new_state=tr.new_state, reason=tr.reason, payload_json=_json(tr.metrics_snapshot)))
            s.commit()

    def record_leaderboard(self, payload: dict) -> None:
        with self.Session() as s:
            row = LeaderboardSnapshotRow(
                wallet_address=str(payload['wallet_address']), source=str(payload.get('source') or 'PUMP_OFFICIAL'),
                observed_at=payload['observed_at'], rank=payload.get('rank'), monthly_pnl=payload.get('monthly_pnl'), payload_json=_json(payload),
            )
            s.add(row)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()

    def record_discovery(self, payload: dict) -> None:
        with self.Session() as s:
            s.add(DiscoveryObservationRow(
                token_mint=payload.get('token_mint'), wallet_address=payload.get('wallet_address'),
                observed_at=payload['observed_at'], source=str(payload.get('source') or 'UNKNOWN'),
                kind=str(payload.get('kind') or 'OBSERVATION'), payload_json=_json(payload),
            ))
            s.commit()

    def record_rollout(self, mint: str, observed_at: datetime, payload: dict) -> None:
        if payload.get('mirofish_status') != 'SIMULATION':
            return
        with self.Session() as s:
            s.add(RolloutSummaryRow(token_mint=mint, observed_at=observed_at, model='MIROFISH', payload_json=_json(payload)))
            s.commit()

    def record_paper_update(self, mint: str, observed_at: datetime, update_type: str, payload: dict) -> None:
        with self.Session() as s:
            s.add(PaperTradeUpdateRow(token_mint=mint, observed_at=observed_at, update_type=update_type, payload_json=_json(payload)))
            s.commit()

    def record_backtest_run(self, run_id: str, created_at: datetime, variant: str, payload: dict, dataset_id: str | None = None) -> None:
        with self.Session() as s:
            s.add(BacktestRunRow(run_id=run_id, created_at=created_at, variant=variant, dataset_id=dataset_id, payload_json=_json(payload)))
            s.commit()

    def record_backtest_metrics(self, run_id: str, metrics: dict, slice_key: str | None = None) -> None:
        with self.Session() as s:
            for name, value in metrics.items():
                numeric = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
                s.add(BacktestMetricRow(run_id=run_id, metric_name=str(name), metric_value=numeric, slice_key=slice_key, payload_json=_json({"value": value})))
            s.commit()

    def record_model_version(self, model_name: str, model_version: str, created_at: datetime, status: str, payload: dict) -> None:
        with self.Session() as s:
            s.add(ModelVersionRow(model_name=model_name, model_version=model_version, created_at=created_at, status=status, payload_json=_json(payload)))
            try:
                s.commit()
            except IntegrityError:
                s.rollback()

    def record_experiment(self, experiment_id: str, created_at: datetime, variant: str, payload: dict) -> None:
        with self.Session() as s:
            s.add(ExperimentResultRow(experiment_id=experiment_id, created_at=created_at, variant=variant, payload_json=_json(payload)))
            s.commit()

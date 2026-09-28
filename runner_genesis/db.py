from __future__ import annotations
from datetime import datetime
from contextlib import contextmanager
from contextvars import ContextVar
import json
from typing import Any
from sqlalchemy import create_engine, String, Float, Integer, DateTime, Boolean, Text, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.exc import IntegrityError


class Base(DeclarativeBase):
    pass


class RuntimeCheckpointRow(Base):
    __tablename__ = 'runtime_checkpoints'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)


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


class WalletTransactionRow(Base):
    __tablename__ = 'wallet_transactions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String(128), index=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(64), default='normalized')
    payload_json: Mapped[str] = mapped_column(Text)


class WalletMetricRow(Base):
    __tablename__ = 'wallet_metrics'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class WalletBackfillStatusRow(Base):
    __tablename__ = 'wallet_backfill_status'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    last_success_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    transactions: Mapped[int] = mapped_column(Integer, default=0)
    swap_events: Mapped[int] = mapped_column(Integer, default=0)
    resolved_outcomes: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[str] = mapped_column(Text)


class WalletOutcomeRow(Base):
    __tablename__ = 'wallet_outcomes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(128), index=True)
    token_mint: Mapped[str] = mapped_column(String(128), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    buy_eur: Mapped[float] = mapped_column(Float, default=0.0)
    realized_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    runner_capture_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('wallet_address', 'token_mint', 'event_time', 'resolved_at', name='uq_wallet_outcome_cycle'),)


class FundingRelationshipRow(Base):
    __tablename__ = 'funding_relationships'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(String(128), index=True)
    funder_address: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    tx_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint('wallet_address', 'funder_address', 'observed_at', 'tx_signature', name='uq_funding_relationship_event'),)


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
        self._active_session = ContextVar('runner_repository_session', default=None)

    @contextmanager
    def _session(self):
        active = self._active_session.get()
        if active is not None:
            yield active
        else:
            with self.Session() as session:
                yield session

    def _commit(self, session):
        if self._active_session.get() is session:
            session.flush()
        else:
            session.commit()

    def _rollback(self, session):
        if self._active_session.get() is session:
            raise RuntimeError('Persistence conflict: atomic event rolled back; restart required')
        session.rollback()

    @contextmanager
    def transaction(self):
        if self._active_session.get() is not None:
            yield
            return
        with self.Session.begin() as session:
            token = self._active_session.set(session)
            try:
                yield
            finally:
                self._active_session.reset(token)

    def has_event(self, event_id: str) -> bool:
        with self._session() as s:
            return s.execute(select(EventRow.id).where(EventRow.event_id == event_id)).first() is not None

    def record_checkpoint(self, payload: dict) -> None:
        with self._session() as s:
            row = s.get(RuntimeCheckpointRow, 'paper')
            if row is None:
                s.add(RuntimeCheckpointRow(key='paper', payload_json=_json(payload)))
            else:
                row.payload_json = _json(payload)
            self._commit(s)

    def load_checkpoint(self) -> dict | None:
        with self._session() as s:
            row = s.get(RuntimeCheckpointRow, 'paper')
            return json.loads(row.payload_json) if row is not None else None

    def record_event(self, e) -> None:
        with self._session() as s:
            s.add(EventRow(
                event_id=e.event_id, timestamp=e.timestamp, token_mint=e.token_mint,
                event_type=e.event_type.value, wallet=e.wallet, source=e.source,
                asset_match_verified=e.asset_match_verified,
                payload_json=e.model_dump_json(),
            ))
            try:
                self._commit(s)
            except IntegrityError:
                self._rollback(s)

    def load_recent_event_ids(self, limit: int = 200_000) -> list[str]:
        with self._session() as s:
            rows = s.execute(
                select(EventRow.event_id)
                .order_by(EventRow.id.desc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            return [str(x) for x in reversed(rows)]

    def record_decision(self, d) -> None:
        with self._session() as s:
            s.add(DecisionRow(timestamp=d.decision_time, token_mint=d.token_mint, action=d.action, model_version=d.model_version, snapshot_json=d.model_dump_json()))
            self._commit(s)

    def record_fill(self, fill) -> None:
        if fill is None:
            return
        with self._session() as s:
            s.add(FillRow(timestamp=fill.timestamp, token_mint=fill.token_mint, side=fill.side, filled_eur=fill.filled_eur, execution_price=fill.execution_price, fees_eur=fill.fees_eur, failed=fill.failed, payload_json=_json(fill.__dict__)))
            self._commit(s)

    def load_fills(self, limit: int = 100_000) -> list[dict]:
        with self._session() as s:
            rows = s.execute(
                select(FillRow)
                .order_by(FillRow.timestamp.asc(), FillRow.id.asc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r.payload_json) if r.payload_json else {}
                except Exception:
                    payload = {}
                payload.update({
                    'token_mint': r.token_mint,
                    'side': r.side,
                    'filled_eur': r.filled_eur,
                    'execution_price': r.execution_price,
                    'fees_eur': r.fees_eur,
                    'failed': r.failed,
                    'timestamp': r.timestamp,
                })
                out.append(payload)
            return out

    def record_wallet_backfill_status(self, wallet: str, last_success_at: datetime, payload: dict | None = None) -> None:
        payload = dict(payload or {})
        with self._session() as s:
            row = s.execute(
                select(WalletBackfillStatusRow)
                .where(WalletBackfillStatusRow.wallet_address == str(wallet))
            ).scalar_one_or_none()
            values = {
                'transactions': int(payload.get('transactions') or 0),
                'swap_events': int(payload.get('swap_events') or 0),
                'resolved_outcomes': int(payload.get('resolved_outcomes') or 0),
                'payload_json': _json(payload),
            }
            if row is None:
                row = WalletBackfillStatusRow(
                    wallet_address=str(wallet),
                    last_success_at=last_success_at,
                    **values,
                )
                s.add(row)
            else:
                row.last_success_at = last_success_at
                row.transactions = values['transactions']
                row.swap_events = values['swap_events']
                row.resolved_outcomes = values['resolved_outcomes']
                row.payload_json = values['payload_json']
            self._commit(s)

    def load_wallet_backfill_status(self, limit: int = 100_000) -> list[dict]:
        with self._session() as s:
            rows = s.execute(
                select(WalletBackfillStatusRow)
                .order_by(WalletBackfillStatusRow.last_success_at.desc(), WalletBackfillStatusRow.id.desc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r.payload_json) if r.payload_json else {}
                except Exception:
                    payload = {}
                out.append({
                    'wallet_address': r.wallet_address,
                    'last_success_at': r.last_success_at,
                    'transactions': r.transactions,
                    'swap_events': r.swap_events,
                    'resolved_outcomes': r.resolved_outcomes,
                    'payload': payload,
                })
            return out

    def record_wallet_transaction(self, e) -> None:
        if e is None or not getattr(e, 'wallet', None):
            return
        event_id = str(getattr(e, 'event_id', '') or '')
        if not event_id:
            return
        event_type = getattr(getattr(e, 'event_type', None), 'value', str(getattr(e, 'event_type', 'UNKNOWN')))
        with self._session() as s:
            if s.execute(select(WalletTransactionRow.id).where(WalletTransactionRow.event_id == event_id)).first():
                return
            s.add(WalletTransactionRow(
                event_id=event_id,
                wallet_address=str(e.wallet),
                token_mint=str(e.token_mint),
                timestamp=e.timestamp,
                event_type=str(event_type),
                source=str(getattr(e, 'source', None) or 'normalized'),
                payload_json=e.model_dump_json(),
            ))
            try:
                self._commit(s)
            except IntegrityError:
                self._rollback(s)

    def load_wallet_transactions(self, limit: int = 500_000, wallet_address: str | None = None) -> list[dict]:
        with self._session() as s:
            stmt = select(WalletTransactionRow)
            if wallet_address is not None:
                stmt = stmt.where(WalletTransactionRow.wallet_address == str(wallet_address))
            rows = s.execute(
                stmt
                .order_by(WalletTransactionRow.timestamp.asc(), WalletTransactionRow.id.asc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r.payload_json) if r.payload_json else {}
                except Exception:
                    payload = {}
                out.append({
                    'event_id': r.event_id,
                    'wallet_address': r.wallet_address,
                    'token_mint': r.token_mint,
                    'timestamp': r.timestamp,
                    'event_type': r.event_type,
                    'source': r.source,
                    'payload': payload,
                })
            return out

    def record_wallet_metrics(self, wallet: str, observed_at: datetime, payload: dict) -> None:
        with self._session() as s:
            s.add(WalletMetricRow(wallet_address=wallet, observed_at=observed_at, payload_json=_json(payload)))
            self._commit(s)

    def record_wallet_outcome(self, wallet: str, obs) -> None:
        with self._session() as s:
            s.add(WalletOutcomeRow(
                wallet_address=wallet,
                token_mint=obs.token_mint,
                event_time=obs.event_time,
                resolved_at=obs.resolved_at,
                buy_eur=float(obs.buy_eur or 0.0),
                realized_return=obs.realized_return,
                runner_capture_ratio=obs.runner_capture_ratio,
                hold_seconds=obs.hold_seconds,
                payload_json=_json(obs.__dict__),
            ))
            try:
                self._commit(s)
            except IntegrityError:
                self._rollback(s)

    def load_wallet_outcomes(self, limit: int = 100_000) -> list[dict]:
        with self._session() as s:
            rows = s.execute(
                select(WalletOutcomeRow)
                .order_by(WalletOutcomeRow.resolved_at.asc(), WalletOutcomeRow.id.asc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            return [{
                'wallet_address': r.wallet_address,
                'token_mint': r.token_mint,
                'event_time': r.event_time,
                'resolved_at': r.resolved_at,
                'buy_eur': r.buy_eur,
                'realized_return': r.realized_return,
                'runner_capture_ratio': r.runner_capture_ratio,
                'hold_seconds': r.hold_seconds,
            } for r in rows]

    def record_funding_relationship(self, link) -> None:
        with self._session() as s:
            s.add(FundingRelationshipRow(
                wallet_address=link.wallet,
                funder_address=link.funder,
                observed_at=link.timestamp,
                confidence=float(link.confidence),
                tx_signature=link.signature,
                payload_json=_json(link.__dict__),
            ))
            try:
                self._commit(s)
            except IntegrityError:
                self._rollback(s)

    def load_funding_relationships(self, limit: int = 100_000) -> list[dict]:
        with self._session() as s:
            rows = s.execute(
                select(FundingRelationshipRow)
                .order_by(FundingRelationshipRow.observed_at.asc(), FundingRelationshipRow.id.asc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            return [{
                'wallet': r.wallet_address,
                'funder': r.funder_address,
                'timestamp': r.observed_at,
                'confidence': r.confidence,
                'signature': r.tx_signature,
            } for r in rows]

    def record_smart_state(self, mint: str, observed_at: datetime, payload: dict) -> None:
        with self._session() as s:
            s.add(SmartTokenStateRow(token_mint=mint, observed_at=observed_at, state=str(payload.get('smart_capital_state') or 'UNKNOWN'), payload_json=_json(payload)))
            self._commit(s)

    def record_wallet_position(self, wallet: str, mint: str, observed_at: datetime, payload: dict) -> None:
        with self._session() as s:
            s.add(WalletPositionRow(wallet_address=wallet, token_mint=mint, observed_at=observed_at, state=str(payload.get('state') or 'UNKNOWN'), payload_json=_json(payload)))
            self._commit(s)

    def load_latest_wallet_positions(self, limit: int = 100_000) -> list[dict]:
        """Return the newest persisted Smart-Capital position snapshot per wallet+mint."""
        with self._session() as s:
            rows = s.execute(
                select(WalletPositionRow)
                .order_by(WalletPositionRow.observed_at.desc(), WalletPositionRow.id.desc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            seen: set[tuple[str, str]] = set()
            out: list[dict] = []
            for r in rows:
                key = (r.wallet_address, r.token_mint)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    payload = json.loads(r.payload_json) if r.payload_json else {}
                except Exception:
                    payload = {}
                out.append({
                    'wallet_address': r.wallet_address,
                    'token_mint': r.token_mint,
                    'observed_at': r.observed_at,
                    'state': r.state,
                    'payload': payload,
                })
            return out

    def load_latest_smart_states(self, limit: int = 100_000) -> list[dict]:
        """Return the newest persisted Smart-Capital token state per mint."""
        with self._session() as s:
            rows = s.execute(
                select(SmartTokenStateRow)
                .order_by(SmartTokenStateRow.observed_at.desc(), SmartTokenStateRow.id.desc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            seen: set[str] = set()
            out: list[dict] = []
            for r in rows:
                if r.token_mint in seen:
                    continue
                seen.add(r.token_mint)
                try:
                    payload = json.loads(r.payload_json) if r.payload_json else {}
                except Exception:
                    payload = {}
                out.append({
                    'token_mint': r.token_mint,
                    'observed_at': r.observed_at,
                    'state': r.state,
                    'payload': payload,
                })
            return out

    def record_actor_cluster(self, mint: str, observed_at: datetime, payload: dict) -> None:
        with self._session() as s:
            s.add(ActorClusterRow(token_mint=mint, observed_at=observed_at, payload_json=_json(payload)))
            self._commit(s)

    def record_transition(self, tr) -> None:
        with self._session() as s:
            s.add(StateTransitionRow(token_mint=tr.token_mint, timestamp=tr.timestamp, old_state=tr.old_state, new_state=tr.new_state, reason=tr.reason, payload_json=_json(tr.metrics_snapshot)))
            self._commit(s)

    def record_leaderboard(self, payload: dict) -> None:
        with self._session() as s:
            row = LeaderboardSnapshotRow(
                wallet_address=str(payload['wallet_address']), source=str(payload.get('source') or 'PUMP_OFFICIAL'),
                observed_at=payload['observed_at'], rank=payload.get('rank'), monthly_pnl=payload.get('monthly_pnl'), payload_json=_json(payload),
            )
            s.add(row)
            try:
                self._commit(s)
            except IntegrityError:
                self._rollback(s)

    def load_leaderboard_snapshots(self, limit: int = 100_000) -> list[dict]:
        with self._session() as s:
            rows = s.execute(
                select(LeaderboardSnapshotRow)
                .order_by(LeaderboardSnapshotRow.observed_at.asc(), LeaderboardSnapshotRow.id.asc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            out = []
            for r in rows:
                payload = json.loads(r.payload_json) if r.payload_json else {}
                out.append({
                    'wallet_address': r.wallet_address,
                    'source': r.source,
                    'observed_at': r.observed_at,
                    'rank': r.rank,
                    'monthly_pnl': r.monthly_pnl,
                    'username': payload.get('username'),
                    'source_window': payload.get('source_window') or '1M',
                    'source_confidence': payload.get('source_confidence', 1.0),
                    'mapping_confidence': payload.get('mapping_confidence', 1.0),
                })
            return out

    def record_discovery(self, payload: dict) -> None:
        with self._session() as s:
            s.add(DiscoveryObservationRow(
                token_mint=payload.get('token_mint'), wallet_address=payload.get('wallet_address'),
                observed_at=payload['observed_at'], source=str(payload.get('source') or 'UNKNOWN'),
                kind=str(payload.get('kind') or 'OBSERVATION'), payload_json=_json(payload),
            ))
            self._commit(s)

    def record_rollout(self, mint: str, observed_at: datetime, payload: dict) -> None:
        if payload.get('mirofish_status') != 'SIMULATION':
            return
        with self._session() as s:
            s.add(RolloutSummaryRow(token_mint=mint, observed_at=observed_at, model='MIROFISH', payload_json=_json(payload)))
            self._commit(s)

    def record_paper_update(self, mint: str, observed_at: datetime, update_type: str, payload: dict) -> None:
        with self._session() as s:
            s.add(PaperTradeUpdateRow(token_mint=mint, observed_at=observed_at, update_type=update_type, payload_json=_json(payload)))
            self._commit(s)

    def load_paper_updates(self, limit: int = 100_000) -> list[dict]:
        with self._session() as s:
            rows = s.execute(
                select(PaperTradeUpdateRow)
                .order_by(PaperTradeUpdateRow.observed_at.desc(), PaperTradeUpdateRow.id.desc())
                .limit(max(1, int(limit)))
            ).scalars().all()
            out = []
            for r in reversed(rows):
                try:
                    payload = json.loads(r.payload_json) if r.payload_json else {}
                except Exception:
                    payload = {}
                out.append({
                    'token_mint': r.token_mint,
                    'observed_at': r.observed_at,
                    'update_type': r.update_type,
                    'payload': payload,
                })
            return out

    def record_backtest_run(self, run_id: str, created_at: datetime, variant: str, payload: dict, dataset_id: str | None = None) -> None:
        with self._session() as s:
            s.add(BacktestRunRow(run_id=run_id, created_at=created_at, variant=variant, dataset_id=dataset_id, payload_json=_json(payload)))
            self._commit(s)

    def record_backtest_metrics(self, run_id: str, metrics: dict, slice_key: str | None = None) -> None:
        with self._session() as s:
            for name, value in metrics.items():
                numeric = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
                s.add(BacktestMetricRow(run_id=run_id, metric_name=str(name), metric_value=numeric, slice_key=slice_key, payload_json=_json({"value": value})))
            self._commit(s)

    def record_model_version(self, model_name: str, model_version: str, created_at: datetime, status: str, payload: dict) -> None:
        with self._session() as s:
            s.add(ModelVersionRow(model_name=model_name, model_version=model_version, created_at=created_at, status=status, payload_json=_json(payload)))
            try:
                self._commit(s)
            except IntegrityError:
                self._rollback(s)

    def record_experiment(self, experiment_id: str, created_at: datetime, variant: str, payload: dict) -> None:
        with self._session() as s:
            s.add(ExperimentResultRow(experiment_id=experiment_id, created_at=created_at, variant=variant, payload_json=_json(payload)))
            self._commit(s)

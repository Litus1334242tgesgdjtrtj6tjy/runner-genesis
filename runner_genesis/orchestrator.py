from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta, timezone
import numpy as np

from .config import Settings
from .domain.events import MarketEvent, DecisionSnapshot
from .domain.state import WalletBuyObservation
from .state_store import MarketStateStore, BUY_TYPES
from .engines.capital_surprise import CapitalSurpriseEngine
from .engines.wallet_quality import WalletQualityEngine
from .engines.actor_graph import ActorGraphEngine
from .engines.funding_graph import FundingGraphEngine
from .engines.market_acceleration import MarketAccelerationEngine
from .engines.token_quality import TokenQualityEngine
from .engines.hawkes import HawkesCascadeEngine
from .engines.flow import GraphFlowDynamicsEngine
from .engines.hypergraph import TemporalHypergraphState
from .engines.sequence import TemporalSequenceEngine
from .engines.jump_sde import LatentJumpSDEEngine, NoOpJumpSDE
from .engines.elite_holder import EliteRunnerHolderEngine
from .engines.quantum_graph import QuantumInspiredGraphEngine
from .engines.flywire import FlyWireReservoir
from .engines.genesis import RunnerGenesisModel
from .engines.persistence import RunnerPersistenceEngine
from .engines.executable_alpha import ExecutableAlphaModel
from .engines.world_model import RunnerWorldModel
from .engines.discovery import PumpDiscoveryEngine
from .engines.smart_capital import SmartCapitalEngine
from .engines.launch_integrity import LaunchIntegrityEngine
from .engines.fomo import FomoEngine
from .engines.mirofish import MiroFishRolloutEngine
from .engines.cohorts import CohortDiscoveryEngine
from .engines.fusion import MultiBrainStateFusionEngine
from .engines.early_formation import EarlySmartCapitalFormationEngine
from .ai_trader import AIPaperTrader, Action, TradeProposal
from .risk_governor import RiskGovernor
from .execution import PaperExecutionEngine, PaperFill
from .portfolio import PortfolioLedger
from .db import RuntimeRepository
from .alerts import AlertEngine
from .paper_recovery import recover_pending_specs
from .ingestion.gates import CandidateUniverseGate


@dataclass
class ProcessResult:
    snapshot: DecisionSnapshot
    fill: PaperFill | None
    risk_approved: bool
    risk_reasons: list[str]


@dataclass
class PendingPaperOrder:
    proposal: TradeProposal
    signal_time: datetime
    due_time: datetime
    signal_features: dict


class RunnerGenesisOmega:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = MarketStateStore()
        self.candidate_gate = CandidateUniverseGate()
        self.capital = CapitalSurpriseEngine()
        self.wallet_quality = WalletQualityEngine()
        self.actor = ActorGraphEngine()
        self.funding = FundingGraphEngine()
        self.market = MarketAccelerationEngine()
        self.token_quality = TokenQualityEngine()
        self.hawkes = HawkesCascadeEngine(float(settings.features.get('hawkes', {}).get('half_life_seconds', 25.0)))
        self.flow = GraphFlowDynamicsEngine()
        self.hyper = TemporalHypergraphState()
        self.sequence = TemporalSequenceEngine()
        js = settings.features.get('jump_sde', {})
        self.jump = LatentJumpSDEEngine(int(js.get('state_dim', 32))) if js.get('enabled', True) else NoOpJumpSDE()
        self.elite = EliteRunnerHolderEngine(self.wallet_quality)
        q = settings.features.get('quantum_graph', {})
        self.quantum = QuantumInspiredGraphEngine(bool(q.get('enabled', False)), int(q.get('max_nodes', 128)))
        fw = settings.features.get('flywire', {})
        self.fly = FlyWireReservoir(
            fw.get('artifact_dir', './artifacts/flywire'), bool(fw.get('enabled', False)),
            int(fw.get('state_dim', 64)), float(fw.get('alpha', 0.9)), variant=str(fw.get('variant', 'FLY_REAL')),
        )
        gm = settings.features.get('genesis_model', {})
        self.genesis = RunnerGenesisModel(gm.get('model_path'))
        self.persistence = RunnerPersistenceEngine()
        wm = settings.features.get('world_model', {})
        self.world = RunnerWorldModel(wm.get('model_path'), bool(wm.get('enabled', True)))
        self.discovery = PumpDiscoveryEngine(settings.pump_discovery)
        self.smart = SmartCapitalEngine(settings.smart_capital, self.wallet_quality, self.discovery)
        self.launch_integrity = LaunchIntegrityEngine()
        self.fomo = FomoEngine(settings.fomo)
        self.mirofish = MiroFishRolloutEngine(settings.mirofish, deterministic=settings.mode.upper() in {'BACKTEST','REPLAY'})
        self.cohorts = CohortDiscoveryEngine()
        self.fusion = MultiBrainStateFusionEngine()
        self.early_formation = EarlySmartCapitalFormationEngine(settings.early_formation)
        self.exec_alpha = ExecutableAlphaModel()
        self.trader = AIPaperTrader(settings.trader, paper_only=settings.paper_only)
        self.risk = RiskGovernor(settings.risk)
        self.execution = PaperExecutionEngine(settings.execution)
        self.portfolio = PortfolioLedger(settings.paper_starting_capital_eur)
        self.decisions: list[DecisionSnapshot] = []
        self.pending_orders: dict[str, PendingPaperOrder] = {}
        self.alerts = AlertEngine()
        self._persisted_transition_count = 0
        self._max_processed_event_ids = 200_000
        self._processed_event_ids: set[str] = set()
        self._processed_event_order: deque[str] = deque()
        self._event_result_cache: dict[str, ProcessResult] = {}
        self._event_result_order: deque[str] = deque()
        db_enabled = bool(settings.features.get('database_persistence', {}).get('enabled', True))
        self.repository = RuntimeRepository(settings.database_url) if db_enabled else None
        if self.repository:
            self._hydrate_processed_event_ids()
            self._hydrate_research_state()
            self._hydrate_paper_portfolio()
            self._hydrate_pending_paper()

    @staticmethod
    def _aware(ts: datetime) -> datetime:
        return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)

    def _hydrate_processed_event_ids(self) -> None:
        if not self.repository:
            return
        for event_id in self.repository.load_recent_event_ids(limit=self._max_processed_event_ids):
            if event_id in self._processed_event_ids:
                continue
            self._processed_event_ids.add(event_id)
            self._processed_event_order.append(event_id)

    def _remember_event_result(self, event_id: str | None, result: ProcessResult) -> None:
        if not event_id:
            return
        if event_id not in self._processed_event_ids:
            self._processed_event_ids.add(event_id)
            self._processed_event_order.append(event_id)
        self._event_result_cache[event_id] = result
        self._event_result_order.append(event_id)
        while len(self._processed_event_order) > self._max_processed_event_ids:
            expired = self._processed_event_order.popleft()
            self._processed_event_ids.discard(expired)
            self._event_result_cache.pop(expired, None)
        while len(self._event_result_order) > 10_000:
            expired = self._event_result_order.popleft()
            if expired not in self._event_result_order:
                self._event_result_cache.pop(expired, None)

    def _duplicate_result(self, e: MarketEvent) -> ProcessResult:
        cached = self._event_result_cache.get(e.event_id)
        if cached is not None:
            return cached
        snapshot = DecisionSnapshot(
            decision_time=e.timestamp,
            token_mint=e.token_mint,
            model_version=self.genesis.model_version,
            data_available_until=e.timestamp,
            features={'event_status':'DUPLICATE_IGNORED'},
            probabilities={'genesis_prob':None},
            action='DUPLICATE_IGNORED',
            reasons=['DUPLICATE_EVENT_ID'],
            risks=[],
        )
        return ProcessResult(snapshot, None, False, ['DUPLICATE_EVENT_ID'])

    def _hydrate_research_state(self) -> None:
        """Restore persistent wallet outcomes/funding evidence without replaying them as market events."""
        if not self.repository:
            return
        limit = max(1, int(self.settings.helius_history.hydrate_max_rows))
        by_wallet: dict[str, list[WalletBuyObservation]] = {}
        for row in self.repository.load_wallet_outcomes(limit=limit):
            obs = WalletBuyObservation(
                event_time=self._aware(row['event_time']),
                resolved_at=self._aware(row['resolved_at']),
                token_mint=row['token_mint'],
                buy_eur=float(row.get('buy_eur') or 0.0),
                realized_return=row.get('realized_return'),
                runner_capture_ratio=row.get('runner_capture_ratio'),
                hold_seconds=row.get('hold_seconds'),
            )
            by_wallet.setdefault(row['wallet_address'], []).append(obs)
        for wallet, observations in by_wallet.items():
            self.store.backfill_wallet_observations(wallet, observations)
        for row in self.repository.load_funding_relationships(limit=limit):
            self.actor.observe_funding_link(
                row['wallet'],
                row['funder'],
                self._aware(row['timestamp']),
                float(row.get('confidence') or 0.0),
            )

        for row in self.repository.load_leaderboard_snapshots(limit=limit):
            observed_at = self._aware(row['observed_at'])
            self.discovery.ingest_leaderboard(
                [{
                    'wallet_address': row['wallet_address'],
                    'username': row.get('username'),
                    'rank': row.get('rank'),
                    'monthly_pnl': row.get('monthly_pnl'),
                    'source_window': row.get('source_window') or '1M',
                    'source_confidence': row.get('source_confidence', 1.0),
                    'mapping_confidence': row.get('mapping_confidence', 1.0),
                }],
                observed_at=observed_at,
                source=str(row.get('source') or 'PUMP_OFFICIAL'),
            )

        for row in self.repository.load_latest_wallet_positions(limit=limit):
            self.smart.restore_position_snapshot(
                str(row['wallet_address']),
                str(row['token_mint']),
                dict(row.get('payload') or {}),
            )
        for row in self.repository.load_latest_smart_states(limit=limit):
            self.smart.restore_token_state(str(row['token_mint']), row.get('state'))

    def _hydrate_paper_portfolio(self) -> None:
        """Replay persisted PAPER fills so process restarts do not reset cash/positions."""
        if not self.repository:
            return
        for row in self.repository.load_fills(limit=100_000):
            ts = row.get('timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if not isinstance(ts, datetime):
                continue
            ts = self._aware(ts)
            try:
                fill = PaperFill(
                    token_mint=str(row['token_mint']),
                    side=str(row.get('side') or 'NA'),
                    requested_eur=float(row.get('requested_eur') or row.get('filled_eur') or 0.0),
                    filled_eur=float(row.get('filled_eur') or 0.0),
                    quantity=float(row.get('quantity') or 0.0),
                    reference_price=float(row.get('reference_price') or row.get('execution_price') or 0.0),
                    execution_price=float(row.get('execution_price') or 0.0),
                    slippage_pct=float(row.get('slippage_pct') or 0.0),
                    fees_eur=float(row.get('fees_eur') or 0.0),
                    latency_ms=float(row.get('latency_ms') or 0.0),
                    failed=bool(row.get('failed', False)),
                    partial=bool(row.get('partial', False)),
                    timestamp=ts,
                    reason=str(row.get('reason') or ''),
                    protocol_fee_bps=row.get('protocol_fee_bps'),
                    fee_source=str(row.get('fee_source') or 'CONFIG_FALLBACK'),
                    fee_schedule_version=row.get('fee_schedule_version'),
                    fee_confidence=float(row.get('fee_confidence') or 0.0),
                    network_fee_eur=float(row.get('network_fee_eur') or 0.0),
                    risk_cluster_id=row.get('risk_cluster_id'),
                    risk_cluster_fraction=float(row.get('risk_cluster_fraction') or 0.0),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self.portfolio.apply_fill(fill)
        prices = {
            mint: position.avg_entry_price
            for mint, position in self.portfolio.account.positions.items()
        }
        self.portfolio.mark_to_market(prices)

    def _hydrate_pending_paper(self) -> None:
        if not self.repository:
            return
        specs = recover_pending_specs(
            self.repository.load_paper_updates(limit=100_000),
            self.repository.load_fills(limit=100_000),
            float(self.settings.execution.execution_delay_seconds),
        )
        for spec in specs:
            action = Action.ENTER if spec['action'] == 'ENTER' else Action.ADD
            proposal = TradeProposal(
                action=action,
                token_mint=spec['token_mint'],
                amount_eur=float(spec['amount_eur']),
                confidence=float(spec['confidence']),
                reasons=['RESTORED_DELAYED_PAPER_SIGNAL'],
            )
            self.pending_orders[spec['token_mint']] = PendingPaperOrder(
                proposal=proposal,
                signal_time=spec['signal_time'],
                due_time=spec['due_time'],
                signal_features=dict(spec['signal_features']),
            )

    def _fly_embedding(self, f: dict) -> np.ndarray:
        keys = [
            'capital_surprise', 'wallet_quality', 'pre_funding_score', 'cluster_density',
            'buyer_acceleration', 'net_buy_pressure_60s', 'token_risk', 'runner_cascade_r',
            'capital_convergence', 'flow_coherence', 'runner_holder_retention',
            'weighted_smart_capital_consensus', 'jump_state_positive_mass',
            'higher_order_edge_fraction', 'world_new_elite_score', 'world_smart_wave_score',
        ]
        return np.array([float(f.get(k, 0.0) or 0.0) for k in keys], dtype=np.float32)

    def _execute(self, proposal: TradeProposal, token, now: datetime, features: dict) -> tuple[PaperFill | None, bool, list[str]]:
        pos = self.portfolio.account.positions.get(proposal.token_mint)
        position_qty = pos.quantity if pos else 0.0
        requested = proposal.amount_eur if proposal.amount_eur else (position_qty * float(token.price_usd or 0) * proposal.reduce_fraction)
        est_slip = self.execution.estimate_slippage(requested, float(token.liquidity_usd or 0)) if requested > 0 and token.liquidity_usd else 0.0
        rd = self.risk.evaluate(proposal, self.portfolio.account, token, est_slip, features, now=now)
        fill = None
        if rd.approved:
            fill = self.execution.execute(proposal, token, now, position_qty)
            if fill is not None:
                if fill.side == 'BUY':
                    cluster_id = features.get('dominant_actor_cluster_id')
                    fill.risk_cluster_id = str(cluster_id) if cluster_id else None
                    fill.risk_cluster_fraction = float(features.get('dominant_actor_cluster_fraction', 0.0) or 0.0)
                applied = self.portfolio.apply_fill(fill)
                if not applied:
                    return None, False, rd.reasons + ['PORTFOLIO_REJECTED_FILL']
                if self.repository:
                    self.repository.record_fill(fill)
                    self.repository.record_paper_update(
                        proposal.token_mint,
                        fill.timestamp,
                        f"FILL_{fill.side}" if not fill.failed else "FILL_FAILED",
                        {
                            "proposal_action": proposal.action.value,
                            "filled_eur": fill.filled_eur,
                            "execution_price": fill.execution_price,
                            "fees_eur": fill.fees_eur,
                            "slippage_pct": fill.slippage_pct,
                            "failed": fill.failed,
                            "partial": fill.partial,
                            "risk_cluster_id": getattr(fill, 'risk_cluster_id', None),
                            "risk_cluster_fraction": getattr(fill, 'risk_cluster_fraction', 0.0),
                        },
                    )
        return fill, rd.approved, rd.reasons

    def _execute_due_pending(
        self,
        mint: str,
        now: datetime,
        token,
        features: dict,
        market_event: MarketEvent | None = None,
    ) -> tuple[PaperFill | None, list[str]]:
        pending = self.pending_orders.get(mint)
        if pending is None or now < pending.due_time:
            return None, []

        if str(features.get('entry_validity')) != 'VALID':
            del self.pending_orders[mint]
            if self.repository:
                self.repository.record_paper_update(
                    mint, now, 'PENDING_SIGNAL_INVALIDATED',
                    {'entry_validity': features.get('entry_validity'), 'signal_time': pending.signal_time, 'due_time': pending.due_time},
                )
            return None, ['PENDING_SIGNAL_INVALIDATED']

        # A delayed entry must use a quote explicitly observed on the current verified
        # event. TokenState may still contain an older cached price/liquidity value.
        if market_event is not None:
            fresh_quote = (
                market_event.token_mint == mint
                and bool(market_event.asset_match_verified)
                and market_event.timestamp >= pending.due_time
                and market_event.price_usd is not None
                and float(market_event.price_usd) > 0
                and market_event.liquidity_usd is not None
                and float(market_event.liquidity_usd) > 0
            )
            if not fresh_quote:
                return None, ['WAITING_FRESH_EXECUTION_QUOTE']

        execution_features = dict(features)
        if not execution_features.get('dominant_actor_cluster_id'):
            signal_cluster = pending.signal_features.get('dominant_actor_cluster_id')
            if signal_cluster:
                execution_features['dominant_actor_cluster_id'] = signal_cluster
                execution_features['dominant_actor_cluster_fraction'] = pending.signal_features.get(
                    'dominant_actor_cluster_fraction', 0.0
                )

        del self.pending_orders[mint]
        fill, approved, reasons = self._execute(pending.proposal, token, now, execution_features)
        if not approved:
            return fill, reasons
        return fill, []

    def _persist_new_transitions(self) -> None:
        if not self.repository:
            return
        new = self.smart.transitions[self._persisted_transition_count:]
        for tr in new:
            self.repository.record_transition(tr)
        self._persisted_transition_count = len(self.smart.transitions)

    def process(self, e: MarketEvent) -> ProcessResult:
        if e.event_id and e.event_id in self._processed_event_ids:
            return self._duplicate_result(e)

        gate = self.candidate_gate.evaluate(e)
        if not gate.allowed:
            snapshot = DecisionSnapshot(
                decision_time=e.timestamp, token_mint=e.token_mint, model_version=self.genesis.model_version,
                data_available_until=e.timestamp, features={'candidate_gate':'REJECTED','candidate_gate_reason':gate.reason},
                probabilities={'genesis_prob':None}, action='IGNORED_NON_CANDIDATE', reasons=[gate.reason], risks=[]
            )
            self.decisions.append(snapshot)
            if self.repository:
                self.repository.record_event(e); self.repository.record_decision(snapshot)
            result = ProcessResult(snapshot, None, False, [gate.reason])
            self._remember_event_result(e.event_id, result)
            return result

        # DATA CORRECTNESS GATE: ambiguous asset identity cannot populate price/MC features.
        if not e.asset_match_verified:
            e.price_usd = None
            e.market_cap_usd = None

        if self.repository:
            self.repository.record_event(e)

        # Historical wallet features are evaluated BEFORE the current event enters wallet history.
        cs = self.capital.compute(e, self.store)
        wq = self.wallet_quality.compute(e.wallet, e.timestamp, self.store)
        funding = self.funding.features(e, self.store)

        # The current event is now valid information at decision time T.
        token = self.store.apply(e)
        self.actor.observe(e)
        self.hyper.observe(e)
        sequence = self.sequence.observe_and_features(e)
        self.smart.observe(e)

        cluster = self.actor.token_cluster_features(e.token_mint, e.timestamp)
        tq = self.token_quality.features(token)
        accel = self.market.features(token, e.timestamp)
        mark = max(0.1, 1.0 + 2.0 * cs.capital_surprise + 1.5 * wq.quality)
        hawkes = self.hawkes.observe_and_features(e, mark)
        flow = self.flow.features(token, e.timestamp)
        elite = self.elite.observe_and_features(e, self.store)
        jump = self.jump.observe(e, {
            'capital_surprise': cs.capital_surprise,
            'wallet_quality': wq.quality,
            'token_risk': float(tq.get('token_risk') if tq.get('token_risk') is not None else 0.5),
        })
        hyper = self.hyper.features(e.token_mint, e.timestamp)
        active_wallets = [x.wallet for x in token.events[-128:] if getattr(x, 'wallet', None) and getattr(x, 'event_type', None) in BUY_TYPES]
        quantum = self.quantum.features(self.actor.graph, active_wallets)
        discovery = self.discovery.token_wave_features(active_wallets, e.timestamp, actor=self.actor, events=token.events[-256:])
        smart = self.smart.token_features(e.token_mint, e.timestamp, self.store, self.actor)

        f: dict = {}
        f.update(cs.as_features())
        f['wallet_quality'] = wq.quality
        f['wallet_role'] = wq.role
        f['wallet_quality_confidence'] = wq.confidence
        for d in (funding, cluster, tq, accel, hawkes, flow, elite, jump, hyper, sequence, quantum, discovery, smart):
            f.update(d)

        launch = self.launch_integrity.features(token, {**cluster, **smart})
        f.update(launch)
        fomo = self.fomo.features(e.token_mint, e.timestamp)
        f.update(fomo)
        formation = self.early_formation.observe_and_features(
            e.token_mint,
            e.timestamp,
            f,
            token.price_usd,
        )
        f.update(formation)

        world = self.world.predict(f)
        f.update(world)
        fly = self.fly.step(self._fly_embedding(f), key=e.token_mint)
        f.update(fly)
        mirofish = self.mirofish.rollouts(e.token_mint, e.timestamp, f)
        f.update(mirofish)

        probs = self.genesis.predict(f)
        f['genesis_model_status'] = self.genesis.model_status
        f['genesis_score'] = float(probs.get('genesis_score') or probs.get('genesis_prob') or 0.0)
        persistence = self.persistence.compute(f)
        f.update(persistence)
        f['smart_capital_state'] = self.smart.apply_persistence(
            e.token_mint, e.timestamp, float(persistence.get('runner_persistence', 0.0)),
            float(persistence.get('distribution_score', 0.0)), f,
        )

        fusion = self.fusion.compute(f, probs)
        f.update(fusion)

        alpha = self.exec_alpha.compute(probs, f, self.settings.trader.default_position_eur, self.settings.execution)
        f.update(alpha)

        # Risk sizing/drawdown must see the newest point-in-time marks, not the previous
        # event's cached account equity.
        pre_trade_prices = {
            m: float(self.store.token(m).price_usd or p.avg_entry_price)
            for m, p in self.portfolio.account.positions.items()
        }
        self.portfolio.mark_to_market(pre_trade_prices)

        # A previously confirmed ENTER/ADD is executed at the first verified market event
        # at or after the configured delay, never at the signal-time price.
        due_fill, due_reasons = self._execute_due_pending(
            e.token_mint, e.timestamp, token, f, market_event=e
        )

        pos = self.portfolio.account.positions.get(e.token_mint)
        has_pos = pos is not None
        current_cost = pos.cost_basis_eur if pos else 0.0
        adds = pos.adds if pos else 0
        proposal = self.trader.decide(e.token_mint, f, probs, alpha, persistence, has_pos, current_cost, adds)

        fill = due_fill
        risk_approved = True
        risk_reasons = list(due_reasons)
        action_label = proposal.action.value

        if proposal.action in (Action.ENTER, Action.ADD) and float(self.settings.execution.execution_delay_seconds) > 0:
            pre_rd = self.risk.evaluate(proposal, self.portfolio.account, token, 0.0, f, now=e.timestamp)
            risk_approved = pre_rd.approved
            risk_reasons.extend(pre_rd.reasons)
            if pre_rd.approved and e.token_mint not in self.pending_orders:
                due = e.timestamp + timedelta(seconds=float(self.settings.execution.execution_delay_seconds))
                self.pending_orders[e.token_mint] = PendingPaperOrder(proposal, e.timestamp, due, dict(f))
                if self.repository:
                    self.repository.record_paper_update(
                        e.token_mint, e.timestamp, f'PENDING_{proposal.action.value}',
                        {
                            'due_time': due,
                            'amount_eur': proposal.amount_eur,
                            'fusion_research_score': f.get('fusion_research_score'),
                            'fusion_confidence': f.get('fusion_confidence'),
                            'weighted_smart_capital_consensus': f.get('weighted_smart_capital_consensus'),
                            'top_trader_wave_score': f.get('top_trader_wave_score'),
                            'dominant_actor_cluster_id': f.get('dominant_actor_cluster_id'),
                            'dominant_actor_cluster_fraction': f.get('dominant_actor_cluster_fraction'),
                        },
                    )
                action_label = f'PENDING_{proposal.action.value}'
        elif proposal.action in (Action.PROTECT, Action.PARTIAL_EXIT, Action.REDUCE, Action.EXIT, Action.KEEP_RUNNER_BAG):
            immediate_fill, approved, reasons = self._execute(proposal, token, e.timestamp, f)
            risk_approved = approved
            risk_reasons.extend(reasons)
            if immediate_fill is not None:
                fill = immediate_fill
        elif proposal.action not in (Action.PASS, Action.WATCH, Action.HOLD):
            immediate_fill, approved, reasons = self._execute(proposal, token, e.timestamp, f)
            risk_approved = approved
            risk_reasons.extend(reasons)
            if immediate_fill is not None:
                fill = immediate_fill

        prices = {m: float(self.store.token(m).price_usd or p.avg_entry_price) for m, p in self.portfolio.account.positions.items()}
        self.portfolio.mark_to_market(prices)

        snapshot = DecisionSnapshot(
            decision_time=e.timestamp,
            token_mint=e.token_mint,
            model_version=self.genesis.model_version,
            data_available_until=e.timestamp,
            features=f,
            probabilities=probs,
            action=action_label if risk_approved else 'RISK_REJECT',
            reasons=proposal.reasons,
            risks=proposal.risks + risk_reasons,
        )
        self.decisions.append(snapshot)
        self.alerts.evaluate(e.timestamp, e.token_mint, f, proposal.action.value, e.wallet)

        if self.repository:
            self.repository.record_decision(snapshot)
            self.repository.record_smart_state(e.token_mint, e.timestamp, smart)
            if e.wallet:
                self.repository.record_wallet_metrics(e.wallet, e.timestamp, self.smart.wallet_metrics(e.wallet, e.timestamp, self.store))
                pos_snapshot = self.smart.position_snapshot(e.wallet, e.token_mint, e.timestamp)
                if pos_snapshot:
                    self.repository.record_wallet_position(e.wallet, e.token_mint, e.timestamp, pos_snapshot)
            self.repository.record_actor_cluster(e.token_mint, e.timestamp, cluster)
            self.repository.record_rollout(e.token_mint, e.timestamp, mirofish)
            self._persist_new_transitions()

        result = ProcessResult(snapshot, fill, risk_approved, risk_reasons)
        self._remember_event_result(e.event_id, result)
        return result

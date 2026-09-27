from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

from .config import Settings
from .domain.events import MarketEvent, DecisionSnapshot
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
from .ai_trader import AIPaperTrader, Action, TradeProposal
from .risk_governor import RiskGovernor
from .execution import PaperExecutionEngine, PaperFill
from .portfolio import PortfolioLedger
from .db import RuntimeRepository
from .alerts import AlertEngine
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
        self.mirofish = MiroFishRolloutEngine(settings.mirofish)
        self.cohorts = CohortDiscoveryEngine()
        self.exec_alpha = ExecutableAlphaModel()
        self.trader = AIPaperTrader(settings.trader)
        self.risk = RiskGovernor(settings.risk)
        self.execution = PaperExecutionEngine(settings.execution)
        self.portfolio = PortfolioLedger(settings.paper_starting_capital_eur)
        self.decisions: list[DecisionSnapshot] = []
        self.pending_orders: dict[str, PendingPaperOrder] = {}
        self.alerts = AlertEngine()
        self._persisted_transition_count = 0
        db_enabled = bool(settings.features.get('database_persistence', {}).get('enabled', True))
        self.repository = RuntimeRepository(settings.database_url) if db_enabled else None

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
        rd = self.risk.evaluate(proposal, self.portfolio.account, token, est_slip, features)
        fill = None
        if rd.approved:
            fill = self.execution.execute(proposal, token, now, position_qty)
            if fill is not None:
                self.portfolio.apply_fill(fill)
                if self.repository:
                    self.repository.record_fill(fill)
        return fill, rd.approved, rd.reasons

    def _execute_due_pending(self, mint: str, now: datetime, token, features: dict) -> tuple[PaperFill | None, list[str]]:
        pending = self.pending_orders.get(mint)
        if pending is None or now < pending.due_time:
            return None, []
        del self.pending_orders[mint]
        if str(features.get('entry_validity')) != 'VALID':
            return None, ['PENDING_SIGNAL_INVALIDATED']
        fill, approved, reasons = self._execute(pending.proposal, token, now, features)
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
            return ProcessResult(snapshot, None, False, [gate.reason])

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

        cluster = self.actor.token_cluster_features(e.token_mint)
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
        discovery = self.discovery.token_wave_features(active_wallets, e.timestamp)
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

        world = self.world.predict(f)
        f.update(world)
        fly = self.fly.step(self._fly_embedding(f))
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

        alpha = self.exec_alpha.compute(probs, f, self.settings.trader.default_position_eur, self.settings.execution)
        f.update(alpha)

        # A previously confirmed ENTER/ADD is executed at the first verified market event
        # at or after the configured delay, never at the signal-time price.
        due_fill, due_reasons = self._execute_due_pending(e.token_mint, e.timestamp, token, f)

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
            pre_rd = self.risk.evaluate(proposal, self.portfolio.account, token, 0.0, f)
            risk_approved = pre_rd.approved
            risk_reasons.extend(pre_rd.reasons)
            if pre_rd.approved and e.token_mint not in self.pending_orders:
                due = e.timestamp + timedelta(seconds=float(self.settings.execution.execution_delay_seconds))
                self.pending_orders[e.token_mint] = PendingPaperOrder(proposal, e.timestamp, due, dict(f))
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

        return ProcessResult(snapshot, fill, risk_approved, risk_reasons)

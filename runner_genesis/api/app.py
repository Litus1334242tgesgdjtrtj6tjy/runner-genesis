from __future__ import annotations
from datetime import datetime, timedelta, timezone
import asyncio
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from ..config import load_settings
from ..orchestrator import RunnerGenesisOmega
from ..domain.events import MarketEvent
from ..ingestion.helius import HeliusWebhookNormalizer
from ..ingestion.enrich import DexScreenerEnricher
from ..paper_profile import build_paper_profile
from ..ingestion.helius_history import HeliusWalletHistoryClient
from ..research_sources import WalletResearchBackfillService
from ..research_sync import ResearchSyncCoordinator

settings = load_settings()
engine = RunnerGenesisOmega(settings)
app = FastAPI(title='RUNNER GENESIS Ω', version='0.2.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['*'],
    allow_headers=['*'],
)
normalizer = HeliusWebhookNormalizer()
market_enricher = DexScreenerEnricher(ttl_seconds=15.0, sol_ttl_seconds=15.0)
research_sync = ResearchSyncCoordinator(settings, engine)
_research_stop = asyncio.Event()
_research_task: asyncio.Task | None = None


@app.on_event('startup')
async def _start_research_sync():
    global _research_task
    if settings.external_discovery.auto_refresh and research_sync.enabled:
        _research_stop.clear()
        _research_task = asyncio.create_task(research_sync.run_loop(_research_stop))


@app.on_event('shutdown')
async def _stop_research_sync():
    global _research_task
    _research_stop.set()
    if _research_task is not None:
        try:
            await asyncio.wait_for(_research_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _research_task.cancel()
        _research_task = None
    await market_enricher.aclose()


@app.get('/health')
def health():
    return {
        'ok': True,
        'version': '0.2.0',
        'mode': settings.mode,
        'network': settings.network,
        'paper_starting_capital_eur': settings.paper_starting_capital_eur,
        'live_trading': settings.live_trading,
        'paper_only': settings.paper_only,
        'genesis_model_status': engine.genesis.model_status,
        'world_model_status': engine.world.model_status,
        'mirofish_enabled': settings.mirofish.enabled,
        'fomo_enabled': settings.fomo.enabled,
        'flywire_enabled': bool(settings.features.get('flywire', {}).get('enabled', False)),
        'pending_paper_orders': len(engine.pending_orders),
        'research_sync': research_sync.status(),
    }


@app.post('/api/event')
async def ingest_event(event: MarketEvent):
    event = await market_enricher.enrich(event)
    result = engine.process(event)
    return {
        'snapshot': result.snapshot.model_dump(mode='json'),
        'risk_approved': result.risk_approved,
        'risk_reasons': result.risk_reasons,
        'fill': result.fill.__dict__ if result.fill else None,
    }


@app.post('/api/helius/webhook')
async def helius_webhook(payload: dict, x_runner_secret: str | None = Header(default=None)):
    import os
    expected = os.getenv('HELIUS_WEBHOOK_SECRET')
    if expected and x_runner_secret != expected:
        raise HTTPException(401, 'invalid webhook secret')
    results = []
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        for event in normalizer.normalize(item):
            event = await market_enricher.enrich(event)
            r = engine.process(event)
            results.append(r.snapshot.model_dump(mode='json'))
    return {'processed': len(results), 'decisions': results}


@app.get('/api/tokens')
def tokens():
    rows = []
    last = {d.token_mint: d for d in engine.decisions}
    for mint, t in engine.store.tokens.items():
        d = last.get(mint)
        probs = d.probabilities if d else {}
        features = d.features if d else {}
        rows.append({
            'token': mint,
            'chain': 'solana',
            'name': t.metadata.get('token_name'),
            'symbol': t.metadata.get('token_symbol'),
            'image_url': t.metadata.get('token_image_url'),
            'dex_url': t.metadata.get('dexscreener_url'),
            'age': ((t.last_event_at - t.created_at).total_seconds() if t.created_at and t.last_event_at else None),
            'mc': t.market_cap_usd,
            'liquidity': t.liquidity_usd,
            'buyers': len(t.buyers),
            'genesis_score': features.get('genesis_score'),
            'genesis_prob': probs.get('genesis_prob'),
            'p_x2': probs.get('p_x2_60m'),
            'p_x5': probs.get('p_x5_60m'),
            'model_status': features.get('genesis_model_status'),
            'fusion_score': features.get('fusion_research_score'),
            'fusion_confidence': features.get('fusion_confidence'),
            'fusion_status': features.get('fusion_status'),
            'smart_consensus': features.get('weighted_smart_capital_consensus'),
            'effective_wallets': features.get('effective_wallet_count'),
            'accumulation': features.get('accumulation_score'),
            'early_formation_score': features.get('early_formation_score'),
            'early_formation_status': features.get('early_formation_status'),
            'early_formation_headroom': features.get('early_formation_entry_headroom'),
            'persistence': features.get('runner_persistence'),
            'distribution': features.get('distribution_score'),
            'launch_integrity': features.get('launch_integrity_score'),
            'manipulation_risk': features.get('manipulation_risk'),
            'entry_validity': features.get('entry_validity'),
            'smart_state': features.get('smart_capital_state'),
            'top_trader_wave': features.get('top_trader_wave_score'),
            'top_trader_count': features.get('top_trader_count'),
            'top_trader_effective_count': features.get('top_trader_effective_count'),
            'new_top_traders_60s': features.get('new_top_traders_60s'),
            'mirofish_status': features.get('mirofish_status'),
            'mirofish_persistence': features.get('mirofish_persistence_frequency'),
            'mirofish_collapse': features.get('mirofish_collapse_frequency'),
            'action': d.action if d else None,
            'position': engine.portfolio.account.positions.get(mint).cost_basis_eur if mint in engine.portfolio.account.positions else 0.0,
        })
    return rows


@app.get('/api/token/{mint}')
def token_detail(mint: str):
    t = engine.store.tokens.get(mint)
    if not t:
        raise HTTPException(404, 'token not found')
    decisions = [d.model_dump(mode='json') for d in engine.decisions if d.token_mint == mint][-100:]
    fills = [f.__dict__ for f in engine.portfolio.fills if f.token_mint == mint]
    smart_positions = [engine.smart.position_snapshot(w, m, t.last_event_at or datetime.now(timezone.utc)) for (w, m) in engine.smart.positions if m == mint]
    transitions = [x.__dict__ for x in engine.smart.transitions if x.token_mint == mint][-100:]
    return {
        'token': mint,
        'state': t.__dict__ | {'buyers': list(t.buyers), 'sellers': list(t.sellers), 'events': []},
        'decisions': decisions,
        'fills': fills,
        'smart_positions': smart_positions,
        'transitions': transitions,
        'fomo': engine.fomo.recent(mint),
    }


@app.get('/api/paper/profile')
def paper_profile():
    return build_paper_profile(engine, timezone_name=settings.paper_timezone)


@app.get('/api/account')
def account():
    a = engine.portfolio.account
    return {
        'starting_cash_eur': a.starting_cash_eur,
        'cash_eur': a.cash_eur,
        'equity_eur': a.equity_eur,
        'realized_pnl_eur': a.realized_pnl_eur,
        'daily_spend_eur': a.daily_spend_eur,
        'daily_realized_pnl_eur': a.daily_realized_pnl_eur,
        'accounting_day_utc': a.accounting_day_utc,
        'positions': {k: v.__dict__ for k, v in a.positions.items()},
        'pending_orders': {
            k: {
                'action': v.proposal.action.value,
                'signal_time': v.signal_time,
                'due_time': v.due_time,
                'amount_eur': v.proposal.amount_eur,
            }
            for k, v in engine.pending_orders.items()
        },
    }


@app.get('/api/smart-capital/wallets')
def smart_wallets(limit: int = 100):
    """TRUE_SMART_CAPITAL_30D: on-chain-qualified ranking, not a Pump PnL list."""
    now = max((t.last_event_at for t in engine.store.tokens.values() if t.last_event_at), default=datetime.now(timezone.utc))
    wallets = sorted(set(engine.store.wallets) | set(engine.discovery.wallet_sources))
    return engine.smart.true_smart_capital_30d(
        wallets,
        now,
        engine.store,
        limit=max(1, min(limit, 1000)),
    )


@app.get('/api/smart-capital/tokens')
def smart_tokens(limit: int = 100):
    now = max((t.last_event_at for t in engine.store.tokens.values() if t.last_event_at), default=datetime.now(timezone.utc))
    rows = engine.smart.active_token_rows(now, engine.store, engine.actor)
    rows.sort(key=lambda x: float(x.get('weighted_smart_capital_consensus') or 0.0), reverse=True)
    return rows[: max(1, min(limit, 1000))]


@app.get('/api/paper/swings')
def paper_swings():
    out = []
    last = {d.token_mint: d for d in engine.decisions}
    for mint, p in engine.portfolio.account.positions.items():
        t = engine.store.token(mint)
        d = last.get(mint)
        current = float(t.price_usd or p.avg_entry_price)
        out.append({
            'token': mint,
            'entry_price': p.avg_entry_price,
            'current_price': current,
            'pnl_pct': current / p.avg_entry_price - 1.0 if p.avg_entry_price > 0 else None,
            'opened_at': p.opened_at,
            'hold_seconds': max(0.0, ((t.last_event_at or p.last_updated_at) - p.opened_at).total_seconds()),
            'persistence': d.features.get('runner_persistence') if d else None,
            'distribution': d.features.get('distribution_score') if d else None,
            'action': d.action if d else None,
        })
    return out


@app.post('/api/discovery/pump/leaderboard')
def ingest_pump_leaderboard(payload: dict):
    rows = payload.get('rows') or []
    at = payload.get('observed_at')
    if isinstance(at, str):
        at = datetime.fromisoformat(at.replace('Z', '+00:00'))
    at = at or datetime.now(timezone.utc)
    source = str(payload.get('source') or 'PUMP_OFFICIAL')
    n = engine.discovery.ingest_leaderboard(rows, observed_at=at, source=source)
    if engine.repository:
        for snap in engine.discovery.snapshots[-n:] if n else []:
            engine.repository.record_leaderboard(snap.__dict__)
    return {'accepted': n, 'source': source, 'observed_at': at}


@app.post('/api/discovery/wallet')
def register_discovery_wallet(payload: dict):
    engine.discovery.register_wallet(payload)
    return {'ok': True}


@app.get('/api/discovery/pump/leaderboard')
def latest_pump_leaderboard(limit: int = 100):
    return engine.discovery.latest_snapshots(limit=max(1, min(limit, 1000)))


@app.post('/api/discovery/fomo')
def ingest_fomo(payload: dict):
    if 'token_mint' not in payload:
        raise HTTPException(400, 'token_mint required')
    obs = engine.fomo.ingest(payload)
    if obs is None:
        return {'ok': True, 'duplicate': True}
    if engine.repository:
        engine.repository.record_discovery({
            'token_mint': obs.token_mint,
            'wallet_address': None,
            'observed_at': obs.timestamp,
            'source': obs.source,
            'kind': obs.kind,
            'confidence': obs.confidence,
            'actor_key': obs.actor_key,
        })
    return {'ok': True, 'duplicate': False, 'observation': obs.__dict__}


@app.get('/api/discovery/fomo/{mint}')
def fomo_for_token(mint: str):
    now = engine.store.tokens.get(mint).last_event_at if mint in engine.store.tokens else datetime.now(timezone.utc)
    return {'features': engine.fomo.features(mint, now), 'observations': engine.fomo.recent(mint)}


@app.get('/api/state-transitions')
def state_transitions(limit: int = 200):
    return [x.__dict__ for x in engine.smart.transitions[-max(1, min(limit, 1000)):]]


@app.get('/api/alerts')
def alerts(limit: int = 200):
    return engine.alerts.recent(max(1, min(limit, 1000)))


@app.get('/api/research/status')
def research_status():
    return research_sync.status()


@app.post('/api/research/sync')
async def research_sync_once(max_wallets: int | None = None):
    return await research_sync.sync_once(max_wallets=max_wallets)


@app.post('/api/research/backfill/wallet/{wallet}')
async def research_backfill_wallet(wallet: str, max_pages: int | None = None):
    if not settings.helius_history.enabled:
        raise HTTPException(409, 'helius history backfill disabled')
    if not settings.helius_api_key:
        raise HTTPException(503, 'HELIUS_API_KEY not configured')
    client = HeliusWalletHistoryClient(settings.helius_api_key)
    service = WalletResearchBackfillService(client, repository=engine.repository, min_funding_sol=settings.helius_history.min_funding_sol)
    result = await service.backfill_wallet(
        wallet,
        engine.store,
        engine.actor,
        smart=engine.smart,
        limit=settings.helius_history.page_limit,
        max_pages=max_pages or settings.helius_history.bootstrap_max_pages,
        stop_before_time=datetime.now(timezone.utc) - timedelta(
            days=max(1, int(settings.helius_history.lookback_days))
        ),
        state_lock=engine.state_lock,
    )
    return result.__dict__


@app.get('/api/discovery/cohorts')
def discovery_cohorts(limit: int = 100, min_size: int = 2):
    now = max((t.last_event_at for t in engine.store.tokens.values() if t.last_event_at), default=datetime.now(timezone.utc))
    wallets = sorted(set(engine.store.wallets) | set(engine.discovery.wallet_sources))
    metrics = {w: engine.smart.wallet_metrics(w, now, engine.store) for w in wallets}
    return engine.cohorts.discover(
        engine.actor,
        metrics,
        now,
        min_size=max(2, min(int(min_size), 50)),
        limit=max(1, min(int(limit), 1000)),
    )

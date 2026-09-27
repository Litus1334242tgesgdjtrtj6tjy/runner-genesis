# Data Sources

## Helius / Solana
Existing Parsed Streams/Webhook/RPC adapters feed normalized on-chain events. Exact mint identity and swap direction are mandatory.

Environment variables:
- `HELIUS_API_KEY`
- `HELIUS_WEBHOOK_SECRET` (optional shared secret)
- `SOLANA_RPC_HTTP`
- `SOLANA_RPC_WS`
- `RUNNER_API_URL` for the shadow process to reach the PAPER API.

## DEX Screener
Existing enrichment uses exact Solana base-token mint matching. Symbol fallback is forbidden.

## Pump/KOL/community discovery
v0.2 provides internal snapshot/registry APIs and provider interfaces. No unstable external endpoint is fabricated. External adapters must preserve `observed_at`, source, rank/window and mapping confidence.

## FOMO/social
Optional observations may be posted to `/api/discovery/fomo`. Core operation does not require Twitter/X or any social service.

## MiroFish
No external service/API key is required. Current implementation is a local experimental MiroFish-style rollout engine.

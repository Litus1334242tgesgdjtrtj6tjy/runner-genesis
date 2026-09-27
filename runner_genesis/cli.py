from __future__ import annotations
import argparse, json, os
from pathlib import Path
from .config import load_settings
from .orchestrator import RunnerGenesisOmega
from .backtest import Backtester
from .demo import make_demo

def main():
    ap=argparse.ArgumentParser(prog='runner-genesis')
    ap.add_argument('--config',default='config/default.yaml')
    sub=ap.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('demo'); s.add_argument('--out',default='data/demo/demo_events.jsonl')
    s=sub.add_parser('backtest'); s.add_argument('file')
    s=sub.add_parser('ablation'); s.add_argument('file')
    s=sub.add_parser('replay'); s.add_argument('file')
    s=sub.add_parser('flywire-preprocess'); s.add_argument('connections'); s.add_argument('--out',default='artifacts/flywire'); s.add_argument('--max-nodes',type=int,default=20000); s.add_argument('--min-syn-count',type=int,default=2)
    s=sub.add_parser('serve'); s.add_argument('--host',default='127.0.0.1'); s.add_argument('--port',type=int,default=8000)
    sub.add_parser('doctor')
    s=sub.add_parser('shadow'); s.add_argument('--program',action='append',default=[])
    args=ap.parse_args()
    if args.cmd=='demo': print(make_demo(args.out)); return
    if args.cmd=='flywire-preprocess':
        from .flywire.preprocess import preprocess_connections
        print(json.dumps(preprocess_connections(args.connections,args.out,args.max_nodes,args.min_syn_count),indent=2)); return
    if args.cmd=='serve':
        import uvicorn; uvicorn.run('runner_genesis.api.app:app',host=args.host,port=args.port,reload=False); return
    if args.cmd=='doctor':
        from .diagnostics import doctor_json
        settings=load_settings(args.config)
        print(doctor_json(settings)); return
    if args.cmd=='shadow':
        import asyncio
        from .shadow import run_shadow
        settings=load_settings(args.config); settings.mode='LIVE_SHADOW'; settings.live_trading=False
        asyncio.run(run_shadow(settings,args.program or None)); return
    if args.cmd=='ablation':
        from .experiments import AblationRunner
        settings=load_settings(args.config)
        print(json.dumps(AblationRunner(settings).run(args.file), indent=2, default=str)); return
    settings=load_settings(args.config); engine=RunnerGenesisOmega(settings)
    metrics=Backtester(engine).run(args.file)
    print(json.dumps(metrics.__dict__,indent=2))

if __name__=='__main__': main()

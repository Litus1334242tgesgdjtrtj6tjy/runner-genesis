import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API='http://127.0.0.1:8000';
const fmt=(x,d=2)=>x==null||Number.isNaN(Number(x))?'—':Number(x).toLocaleString(undefined,{maximumFractionDigits:d});
const pct=(x,d=1)=>x==null?'UNTRAINED':`${fmt(Number(x)*100,d)}%`;
const short=(x)=>!x?'—':String(x).length>18?`${String(x).slice(0,8)}…${String(x).slice(-6)}`:x;

function App(){
 const [rows,setRows]=useState([]),[acct,setAcct]=useState(null),[wallets,setWallets]=useState([]),[smart,setSmart]=useState([]),[swings,setSwings]=useState([]),[health,setHealth]=useState(null),[err,setErr]=useState('');
 const refresh=async()=>{try{
   const [r,a,w,s,p,h]=await Promise.all([
     fetch(`${API}/api/tokens`),fetch(`${API}/api/account`),fetch(`${API}/api/smart-capital/wallets?limit=20`),fetch(`${API}/api/smart-capital/tokens?limit=20`),fetch(`${API}/api/paper/swings`),fetch(`${API}/health`)
   ]);
   setRows(await r.json());setAcct(await a.json());setWallets(await w.json());setSmart(await s.json());setSwings(await p.json());setHealth(await h.json());setErr('');
 }catch(e){setErr(String(e))}};
 useEffect(()=>{refresh();const id=setInterval(refresh,2500);return()=>clearInterval(id)},[]);
 return <main>
  <header><div><h1>RUNNER GENESIS Ω</h1><p>ON-CHAIN FIRST · PAPER ONLY · SMART CAPITAL v0.2</p></div><div className="account"><b>Equity €{fmt(acct?.equity_eur)}</b><span>Cash €{fmt(acct?.cash_eur)}</span><span>PnL €{fmt(acct?.realized_pnl_eur)}</span><span>Pending {health?.pending_paper_orders??0}</span></div></header>
  {err&&<div className="error">{err}</div>}
  <div className="statusbar"><span>Genesis: <b>{health?.genesis_model_status||'—'}</b></span><span>World: <b>{health?.world_model_status||'—'}</b></span><span>MiroFish: <b>{health?.mirofish_enabled?'ON':'OFF'}</b></span><span>FOMO: <b>{health?.fomo_enabled?'ON':'OFF'}</b></span><span>LIVE: <b>{health?.live_trading?'ON':'OFF'}</b></span></div>

  <h2>Candidate tokens</h2>
  <section className="panel"><table><thead><tr><th>TOKEN</th><th>AGE</th><th>MC</th><th>LIQUIDITY</th><th>BUYERS</th><th>GENESIS SCORE</th><th>P_X2</th><th>P_X5</th><th>CONSENSUS</th><th>EFF.W</th><th>PERSIST</th><th>DISTRIB</th><th>LAUNCH</th><th>ENTRY</th><th>AI ACTION</th><th>PAPER €</th></tr></thead><tbody>{rows.map(r=><tr key={r.token}><td className="mint" title={r.token}>{short(r.token)}</td><td>{r.age==null?'UNKNOWN':`${fmt(r.age,0)}s`}</td><td>{r.mc==null?'—':`$${fmt(r.mc,0)}`}</td><td>{r.liquidity==null?'—':`$${fmt(r.liquidity,0)}`}</td><td>{r.buyers}</td><td>{pct(r.genesis_score)}</td><td className={r.p_x2==null?'muted':''}>{pct(r.p_x2)}</td><td className={r.p_x5==null?'muted':''}>{pct(r.p_x5)}</td><td>{pct(r.smart_consensus)}</td><td>{fmt(r.effective_wallets,1)}</td><td>{pct(r.persistence)}</td><td>{pct(r.distribution)}</td><td>{pct(r.launch_integrity)}</td><td>{r.entry_validity||'—'}</td><td><span className={'pill '+String(r.action).toLowerCase()}>{r.action||'—'}</span></td><td>{fmt(r.position)}</td></tr>)}</tbody></table></section>

  <h2>Top smart wallets</h2>
  <section className="panel"><table><thead><tr><th>WALLET</th><th>QUALITY</th><th>STYLE</th><th>SAMPLE</th><th>WIN RATE</th><th>PROFIT FACTOR</th><th>CONSISTENCY</th><th>RUNNER</th><th>SWING</th><th>HOLD</th><th>PUMP RANK</th></tr></thead><tbody>{wallets.map(w=><tr key={w.wallet_address}><td className="mint" title={w.wallet_address}>{short(w.wallet_address)}</td><td>{pct(w.wallet_quality_score)}</td><td>{w.wallet_style}</td><td>{w.sample_size}</td><td>{pct(w.win_rate)}</td><td>{fmt(w.profit_factor,2)}</td><td>{pct(w.consistency_score)}</td><td>{pct(w.runner_score)}</td><td>{pct(w.swing_score)}</td><td>{pct(w.hold_score)}</td><td>{fmt(w.pump_rank,0)}</td></tr>)}</tbody></table></section>

  <h2>Smart capital tokens</h2>
  <section className="panel"><table><thead><tr><th>TOKEN</th><th>RAW W</th><th>EFFECTIVE W</th><th>CAPITAL $</th><th>CONSENSUS</th><th>ACCUM</th><th>CONVICTION</th><th>ENTRY DIST</th><th>RETENTION</th><th>DISTRIB</th><th>STATE</th><th>ENTRY VALIDITY</th></tr></thead><tbody>{smart.map(r=><tr key={r.token}><td className="mint" title={r.token}>{short(r.token)}</td><td>{fmt(r.raw_wallet_count,0)}</td><td>{fmt(r.effective_wallet_count,1)}</td><td>{fmt(r.total_smart_capital_usd,0)}</td><td>{pct(r.weighted_smart_capital_consensus)}</td><td>{pct(r.accumulation_score)}</td><td>{pct(r.conviction_score)}</td><td>{r.entry_distance_price==null?'—':`${fmt(r.entry_distance_price*100,1)}%`}</td><td>{pct(r.smart_capital_retention)}</td><td>{pct(r.smart_distribution_score)}</td><td>{r.smart_capital_state}</td><td>{r.entry_validity}</td></tr>)}</tbody></table></section>

  <h2>Open paper swings</h2>
  <section className="panel"><table><thead><tr><th>TOKEN</th><th>ENTRY</th><th>CURRENT</th><th>PNL</th><th>HOLD</th><th>PERSISTENCE</th><th>DISTRIBUTION</th><th>ACTION</th></tr></thead><tbody>{swings.length?swings.map(r=><tr key={r.token}><td className="mint">{short(r.token)}</td><td>{fmt(r.entry_price,8)}</td><td>{fmt(r.current_price,8)}</td><td>{pct(r.pnl_pct)}</td><td>{fmt(r.hold_seconds/3600,1)}h</td><td>{pct(r.persistence)}</td><td>{pct(r.distribution)}</td><td>{r.action}</td></tr>):<tr><td colSpan="8" className="empty">No open PAPER swing positions</td></tr>}</tbody></table></section>

  <footer>LIVE_TRADING remains OFF. UNTRAINED means no calibrated probability is available. MiroFish outputs, when enabled, are model simulations and not guaranteed outcomes.</footer>
 </main>
}
createRoot(document.getElementById('root')).render(<App/>);

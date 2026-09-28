import React,{useEffect,useMemo,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API=import.meta.env.VITE_API_URL||'http://127.0.0.1:8000';
const eur=(x,d=2)=>x==null||Number.isNaN(Number(x))?'—':Number(x).toLocaleString('es-ES',{style:'currency',currency:'EUR',minimumFractionDigits:d,maximumFractionDigits:d});
const num=(x,d=2)=>x==null||Number.isNaN(Number(x))?'—':Number(x).toLocaleString('es-ES',{maximumFractionDigits:d});
const pct=(x,d=1)=>x==null||Number.isNaN(Number(x))?'—':`${Number(x*100).toLocaleString('es-ES',{maximumFractionDigits:d})}%`;
const price=(x)=>x==null?'—':Number(x).toLocaleString('en-US',{maximumSignificantDigits:8});
const short=(x)=>!x?'—':String(x).length>18?`${String(x).slice(0,7)}…${String(x).slice(-5)}`:x;
const dateTime=(x)=>!x?'—':new Date(x).toLocaleString('es-ES',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
const duration=(s)=>{
  if(s==null)return '—';
  const n=Math.max(0,Number(s));
  if(n<60)return `${Math.round(n)}s`;
  if(n<3600)return `${Math.floor(n/60)}m`;
  if(n<86400)return `${num(n/3600,1)}h`;
  return `${num(n/86400,1)}d`;
};

function Pnl({value,percentValue,large=false}){
 const v=Number(value||0);
 return <span className={`pnl ${v>0?'positive':v<0?'negative':'neutral'} ${large?'large':''}`}>
   {v>0?'+':''}{eur(v)}{percentValue!=null&&<small>{Number(percentValue)>0?'+':''}{pct(percentValue)}</small>}
 </span>;
}

function TokenAvatar({row,size='md'}){
 const [failed,setFailed]=useState(false);
 const label=(row?.symbol||row?.name||row?.token||'?').slice(0,2).toUpperCase();
 return <span className={`token-avatar ${size}`}>
   {row?.image_url&&!failed?<img src={row.image_url} alt="" loading="lazy" onError={()=>setFailed(true)}/>:<span>{label}</span>}
 </span>;
}

function TokenIdentity({row,sub=true}){
 const inner=<div className="token-id">
   <TokenAvatar row={row}/>
   <div><strong>{row.symbol||short(row.token)}</strong><span>{row.name||'Solana token'}</span>{sub&&<small>{short(row.token)}</small>}</div>
 </div>;
 return row.dex_url?<a className="token-link" href={row.dex_url} target="_blank" rel="noreferrer">{inner}</a>:inner;
}

function Metric({label,value,sub,accent=false}){
 return <div className={`metric ${accent?'accent':''}`}><span>{label}</span><strong>{value}</strong>{sub&&<small>{sub}</small>}</div>;
}

function EquityChart({points=[]}){
 const data=points.filter(p=>Number.isFinite(Number(p.equity_eur)));
 if(data.length<2)return <div className="chart-empty">La curva de equity aparecerá cuando empiecen a llegar eventos PAPER.</div>;
 const values=data.map(p=>Number(p.equity_eur));
 const min=Math.min(...values),max=Math.max(...values),span=Math.max(max-min,0.01);
 const coords=data.map((p,i)=>{
   const x=(i/(data.length-1))*100;
   const y=96-((Number(p.equity_eur)-min)/span)*82;
   return `${x},${y}`;
 }).join(' ');
 const last=values[values.length-1],first=values[0];
 return <div className="equity-chart">
   <div className="chart-head"><div><span>Equity</span><strong>{eur(last)}</strong></div><Pnl value={last-first}/></div>
   <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Curva de equity">
    <defs><linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="currentColor" stopOpacity=".28"/><stop offset="100%" stopColor="currentColor" stopOpacity="0"/></linearGradient></defs>
    <polygon points={`0,100 ${coords} 100,100`} fill="url(#equityFill)"/>
    <polyline points={coords} fill="none" vectorEffect="non-scaling-stroke"/>
   </svg>
   <div className="chart-range"><span>{eur(min)}</span><span>{eur(max)}</span></div>
  </div>;
}

function Empty({children}){return <div className="empty-state">{children}</div>}

function OpenPositions({rows=[]}){
 if(!rows.length)return <Empty>No hay posiciones PAPER abiertas todavía.</Empty>;
 return <div className="position-grid">{rows.map(r=><article className="position-card" key={r.token}>
   <div className="position-top"><TokenIdentity row={r}/><span className="network-dot">SOL</span></div>
   <div className="position-value"><span>Valor actual</span><strong>{eur(r.market_value_eur)}</strong><Pnl value={r.unrealized_pnl_eur} percentValue={r.pnl_pct}/></div>
   <div className="position-stats">
    <div><span>Invertido</span><b>{eur(r.invested_eur)}</b></div>
    <div><span>Entrada</span><b>{price(r.avg_entry_price)}</b></div>
    <div><span>Actual</span><b>{price(r.current_price)}</b></div>
    <div><span>Tiempo</span><b>{duration(r.hold_seconds)}</b></div>
   </div>
   <div className="signal-row"><span className={`action ${String(r.action||'hold').toLowerCase()}`}>{r.action||'HOLD'}</span><span>Persist. {pct(r.persistence)}</span><span>Distrib. {pct(r.distribution)}</span></div>
  </article>)}</div>;
}

function ClosedPositions({rows=[]}){
 if(!rows.length)return <Empty>Aún no hay ciclos PAPER cerrados.</Empty>;
 return <div className="table-wrap"><table className="profile-table"><thead><tr><th>Token</th><th>Resultado</th><th>Invertido</th><th>Salida</th><th>Entrada</th><th>Precio salida</th><th>Fees</th><th>Duración</th><th>Cierre</th></tr></thead>
 <tbody>{rows.map((r,i)=><tr key={`${r.token}-${r.closed_at}-${i}`}><td><TokenIdentity row={r} sub={false}/></td><td><Pnl value={r.realized_pnl_eur} percentValue={r.return_pct}/></td><td>{eur(r.invested_eur)}</td><td>{eur(r.proceeds_eur)}</td><td>{price(r.avg_entry_price)}</td><td>{price(r.avg_exit_price)}</td><td>{eur(r.fees_eur)}</td><td>{duration(r.hold_seconds)}</td><td>{dateTime(r.closed_at)}</td></tr>)}</tbody></table></div>;
}

function Activity({rows=[]}){
 if(!rows.length)return <Empty>Las compras y ventas simuladas aparecerán aquí.</Empty>;
 return <div className="activity-list">{rows.map((r,i)=><div className="activity-row" key={`${r.token}-${r.timestamp}-${i}`}>
  <TokenAvatar row={r}/><div className="activity-main"><strong>{r.failed?'Fallo simulado':r.side==='BUY'?'Compra PAPER':'Venta PAPER'} · {r.symbol||short(r.token)}</strong><span>{dateTime(r.timestamp)} · {r.proposal_action||r.side}</span></div>
  <div className="activity-money"><strong>{eur(r.filled_eur)}</strong><span>fees {eur(r.fees_eur)}</span></div>
 </div>)}</div>;
}

function Pending({rows=[]}){
 if(!rows.length)return null;
 return <section className="section"><div className="section-title"><div><span>Órdenes pendientes</span><h2>Esperando ejecución simulada</h2></div><span className="count">{rows.length}</span></div>
 <div className="pending-list">{rows.map(r=><div className="pending-row" key={r.token}><TokenIdentity row={r} sub={false}/><span className="action pending">{r.action}</span><b>{eur(r.amount_eur)}</b><span>ejecución ≥ {dateTime(r.due_time)}</span></div>)}</div></section>;
}

function Radar({rows=[]}){
 const ranked=useMemo(()=>[...rows].sort((a,b)=>Number(b.fusion_score||b.genesis_score||0)-Number(a.fusion_score||a.genesis_score||0)),[rows]);
 if(!ranked.length)return <Empty>Esperando candidatos Solana desde el feed.</Empty>;
 return <div className="table-wrap"><table className="profile-table radar"><thead><tr><th>Token</th><th>Market cap</th><th>Liquidez</th><th>Genesis</th><th>Fusion</th><th>Smart</th><th>Formación</th><th>Persist.</th><th>Distrib.</th><th>Acción</th></tr></thead>
 <tbody>{ranked.map(r=><tr key={r.token}><td><TokenIdentity row={r}/></td><td>{r.mc==null?'—':`$${num(r.mc,0)}`}</td><td>{r.liquidity==null?'—':`$${num(r.liquidity,0)}`}</td><td>{pct(r.genesis_score)}</td><td>{pct(r.fusion_score)}</td><td>{pct(r.smart_consensus)}</td><td>{pct(r.early_formation_score)}</td><td>{pct(r.persistence)}</td><td>{pct(r.distribution)}</td><td><span className={`action ${String(r.action||'watch').toLowerCase()}`}>{r.action||'—'}</span></td></tr>)}</tbody></table></div>;
}

function SystemPanel({health,research}){
 return <div className="system-grid">
  <Metric label="Red" value="Solana" sub="Bloqueada a una sola chain" accent/>
  <Metric label="Modo" value="PAPER" sub="LIVE_TRADING = OFF"/>
  <Metric label="Capital inicial" value={eur(health?.paper_starting_capital_eur??300)} sub="Cuenta simulada"/>
  <Metric label="Genesis" value={health?.genesis_model_status||'—'}/>
  <Metric label="World Model" value={health?.world_model_status||'—'}/>
  <Metric label="MiroFish" value={health?.mirofish_enabled?'ON':'OFF'}/>
  <Metric label="FlyWire" value={health?.flywire_enabled?'ON':'OFF'}/>
  <Metric label="Helius" value={research?.helius_configured?'READY':'WAITING KEY'}/>
 </div>;
}

function App(){
 const [profile,setProfile]=useState(null);
 const [tokens,setTokens]=useState([]);
 const [health,setHealth]=useState(null);
 const [research,setResearch]=useState(null);
 const [tab,setTab]=useState('portfolio');
 const [err,setErr]=useState('');

 const refresh=async()=>{
  try{
   const [p,t,h,r]=await Promise.all([
    fetch(`${API}/api/paper/profile`),fetch(`${API}/api/tokens`),fetch(`${API}/health`),fetch(`${API}/api/research/status`)
   ]);
   if(!p.ok||!t.ok||!h.ok||!r.ok)throw new Error('API no disponible');
   setProfile(await p.json());setTokens(await t.json());setHealth(await h.json());setResearch(await r.json());setErr('');
  }catch(e){setErr(String(e?.message||e))}
 };
 useEffect(()=>{refresh();const id=setInterval(refresh,2500);return()=>clearInterval(id)},[]);

 const s=profile?.summary||{};
 const p=profile?.profile||{};
 const tabs=[['portfolio','Portfolio'],['closed','Cerradas'],['activity','Actividad'],['radar','Radar'],['system','Sistema']];

 return <main className="app-shell">
  <header className="profile-header">
   <div className="profile-avatar">RG<span>Ω</span></div>
   <div className="profile-copy"><div className="profile-title"><h1>{p.display_name||'RUNNER GENESIS PAPER'}</h1><span className="paper-badge">PAPER</span><span className="solana-badge">◎ Solana</span></div><p>{p.handle||'@runner.genesis'} · cuenta simulada · capital inicial {eur(s.starting_balance_eur??300)}</p></div>
   <div className="header-balance"><span>Portfolio</span><strong>{eur(s.equity_eur)}</strong><Pnl value={s.total_pnl_eur} percentValue={s.total_pnl_pct}/></div>
  </header>

  {err&&<div className="error-banner">No puedo actualizar el perfil: {err}</div>}

  <nav className="tabs">{tabs.map(([id,label])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{label}{id==='portfolio'&&s.open_positions>0?<em>{s.open_positions}</em>:null}</button>)}</nav>

  {tab==='portfolio'&&<>
   <section className="hero-grid">
    <div className="balance-card">
     <span className="eyebrow">Equity total</span>
     <strong className="hero-balance">{eur(s.equity_eur)}</strong>
     <Pnl value={s.total_pnl_eur} percentValue={s.total_pnl_pct} large/>
     <div className="balance-split"><div><span>Disponible</span><b>{eur(s.cash_eur)}</b></div><div><span>En posiciones</span><b>{eur(s.position_value_eur)}</b></div><div><span>No realizado</span><b><Pnl value={s.unrealized_pnl_eur}/></b></div><div><span>Realizado</span><b><Pnl value={s.realized_pnl_eur}/></b></div></div>
    </div>
    <EquityChart points={profile?.equity_curve||[]}/>
   </section>

   <section className="metrics-grid">
    <Metric label="Hoy" value={<Pnl value={s.day_pnl_eur}/>} sub="PnL del día"/>
    <Metric label="7 días" value={<Pnl value={s.week_pnl_eur}/>} sub="Semana actual"/>
    <Metric label="30 días" value={<Pnl value={s.month_pnl_eur}/>} sub="Mes actual"/>
    <Metric label="Win rate" value={pct(s.win_rate)} sub={`${s.wins||0} W · ${s.losses||0} L`}/>
    <Metric label="Cerradas" value={num(s.closed_positions,0)} sub="Ciclos completos"/>
    <Metric label="Fees" value={eur(s.fees_eur)} sub="Entrada + salida"/>
   </section>

   <Pending rows={profile?.pending_orders||[]}/>
   <section className="section"><div className="section-title"><div><span>Portfolio</span><h2>Posiciones activas</h2></div><span className="count">{s.open_positions||0}</span></div><OpenPositions rows={profile?.open_positions||[]}/></section>
  </>}

  {tab==='closed'&&<section className="section tab-section"><div className="section-title"><div><span>Historial</span><h2>Posiciones cerradas</h2></div><span className="count">{s.closed_positions||0}</span></div><ClosedPositions rows={profile?.closed_positions||[]}/></section>}
  {tab==='activity'&&<section className="section tab-section"><div className="section-title"><div><span>Ledger</span><h2>Actividad PAPER</h2></div></div><Activity rows={profile?.activity||[]}/></section>}
  {tab==='radar'&&<section className="section tab-section"><div className="section-title"><div><span>Research engine</span><h2>Radar Solana</h2></div><span className="live-dot">LIVE DATA</span></div><Radar rows={tokens}/></section>}
  {tab==='system'&&<section className="section tab-section"><div className="section-title"><div><span>Runtime</span><h2>Estado del sistema</h2></div></div><SystemPanel health={health} research={research}/></section>}

  <footer className="app-footer"><span>RUNNER GENESIS Ω · Solana PAPER account</span><span>Sin claves privadas · sin envío de transacciones reales · LIVE_TRADING OFF</span></footer>
 </main>;
}
createRoot(document.getElementById('root')).render(<App/>);

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.getenv("SHADOW_DB_PATH", ROOT / "data" / "desk.db"))
HEARTBEAT = ROOT / "data" / "scheduler_heartbeat.json"
LOGO = ROOT / "assets" / "everythingailogo.png"
SPRITESHEET = ROOT / "assets" / "everythingai-trading-desk-spritesheet.png"
sys.path.insert(0, str(ROOT / "src"))
from desk.binance_demo import BinanceDemoClient, DemoTradingError

_BINANCE_CACHE: tuple[float, dict] = (0.0, {})
_BINANCE_CACHE_LOCK = threading.Lock()

HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Desk Shadow</title><style>
:root{font:14px system-ui;background:#0d1117;color:#e6edf3}body{max-width:1400px;margin:0 auto;padding:28px}h1{margin:0 0 5px;font-size:28px}small,.muted{color:#8b949e}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0}.card,section{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px}.value{font-size:25px;font-weight:700;margin-top:6px}.ok{color:#3fb950}.bad{color:#f85149}.warn{color:#d29922}.wide{grid-column:1/-1}.binance{border-color:#f0b90b}.binance-grid,.activity-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.binance-grid .item,.activity-grid .item{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px}.label{color:#8b949e;font-size:12px}.datum{font-size:17px;font-weight:650;margin-top:5px}.hint{line-height:1.5;color:#c9d1d9}.legend{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.legend span{padding:5px 9px;border-radius:99px;background:#30363d}.ok-bg{border-color:#238636!important}.bad-bg{border-color:#da3633!important}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid #30363d;white-space:nowrap}th{color:#8b949e;font-weight:500}.scroll{overflow:auto}button{background:#238636;color:white;border:0;border-radius:6px;padding:8px 12px;cursor:pointer}.pill{padding:3px 7px;border-radius:999px;background:#30363d}.entry{color:#ff7b72}.watch{color:#d29922}.win{color:#3fb950}.loss{color:#f85149}.first td{background:#1f6feb22!important;color:#58a6ff!important}.first td b{color:#58a6ff}@media(max-width:900px){.grid,.binance-grid,.activity-grid{grid-template-columns:repeat(2,1fr)}body{padding:16px}.wide{grid-column:1/-1}}
</style></head><body><header><h1>Trading Desk Shadow</h1><div class="muted">Modo paper/shadow · solo lectura · actualización cada 10 segundos</div></header>
<div id="summary" class="grid"></div><section class="wide"><h2>¿Está trabajando?</h2><div id="activity" class="activity-grid"></div><p class="hint">El escáner amplio crea nuevas oportunidades cada hora. Los monitores revisan las señales abiertas cada 5 minutos y la protección Binance cada 15 segundos.</p></section><section class="wide binance"><h2>Binance Futures Demo · conexión y protección</h2><div id="binance" class="binance-grid"></div></section><section class="wide"><h2>Trading Desk · Top 100</h2><p class="hint">Mínimo 30 trades cerrados. Ranking por expectancy R (ventana ALL). <span id="assetRefreshed" class="muted"></span></p><div id="assets" class="scroll"></div></section><section class="wide"><h2>Horas · Mejores y peores horas de entrada</h2><p class="hint">Hora de ENTRADA en UTC (el sistema trabaja en UTC). Referencia ET: UTC-4 en verano / UTC-5 en invierno. Tier: <span class="pill win">PREFERRED</span> wins &ge;50% y R+ &nbsp;·&nbsp; <span class="pill bad">AVOID</span> wins &lt;35% o R negativa &nbsp;·&nbsp; <span class="pill">NEUTRAL</span> lo demás. Mínimo 250 cerrados para clasificar. <span id="hourRefreshed" class="muted"></span></p><div id="hours" class="scroll"></div></section><section class="wide"><h2>Seguimiento de órdenes</h2><div id="orders" class="scroll"></div></section><section class="wide"><h2>Incidencias y activos bloqueados</h2><div id="errors" class="scroll"></div></section><section class="wide"><h2>Cómo leer los estados</h2><div class="legend"><span><b>WATCH</b> = observando</span><span><b>PRE_ENTRY</b> = preparando entrada</span><span><b>ENTRY_READY</b> = señal lista para replicar</span><span><b>CLOSED_WIN</b> = objetivo alcanzado</span><span><b>INVALIDATED</b> = stop/invalida</span><span><b>PASS</b> = no cumple filtros</span></div></section><section class="wide"><h2>Entradas y oportunidades recientes</h2><div class="scroll"><table><thead><tr><th>Hora</th><th>Símbolo</th><th>Estado</th><th>Setup</th><th>Score</th><th>Entry</th><th>Stop</th><th>TP1</th><th>TP2</th><th>Primary</th><th>R:R</th><th>Resultado</th><th>IA</th><th>Derivados</th></tr></thead><tbody id="opps"></tbody></table></div></section>
<section class="wide"><h2>Eventos recientes</h2><div class="scroll"><table><thead><tr><th>Hora</th><th>Tipo</th><th>Símbolo</th><th>Resumen</th></tr></thead><tbody id="events"></tbody></table></div></section>
<script>
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=x=>x==null?'N/A':Number(x).toFixed(4);
async function load(){const d=await fetch('/api/state').then(r=>r.json());
 document.getElementById('summary').innerHTML=[['Runtime',d.runtime,'ok'],['Oportunidades',d.metrics.opportunities,''],['Planes',d.metrics.plans,''],['Abiertas',d.metrics.open,'warn'],['Win rate',d.metrics.win_rate+'%','']].map(x=>`<div class="card"><div class="muted">${x[0]}</div><div class="value ${x[2]}">${esc(x[1])}</div></div>`).join('');
 const b=d.binance_demo||{};document.getElementById('binance').innerHTML=[['Conexión',b.connected?'CONECTADO':'ERROR',b.connected?'ok':'bad'],['Endpoint',b.endpoint||'N/A',''],['Balance',b.wallet_balance==null?'N/A':b.wallet_balance+' USDT',''],['Disponible',b.available_balance==null?'N/A':b.available_balance+' USDT',''],['Posición',b.position?b.position.symbol+' '+b.position.amount:'Sin posición',''],['Modo',b.symbol_config?b.symbol_config.margin_type+' '+b.symbol_config.leverage+'x':'N/A',''],['SL nativo',b.stop?b.stop.trigger_price+' · '+b.stop.status:'N/A',b.stop?'ok':'warn'],['TP nativo',b.take_profit?b.take_profit.trigger_price+' · '+b.take_profit.status:'N/A',b.take_profit?'ok':'warn']].map(x=>`<div class="item"><div class="label">${esc(x[0])}</div><div class="datum ${x[2]}">${esc(x[1])}</div></div>`).join('');
 const a=d.activity||{};document.getElementById('activity').innerHTML=[['Scheduler',a.scheduler_state||'N/A',a.scheduler_state==='ok'?'ok':'bad'],['Último trabajo',a.last_job||'N/A',''],['Último evento',a.last_event||'N/A',''],['Último escaneo',a.last_scan||'N/A','']].map(x=>`<div class="item"><div class="label">${esc(x[0])}</div><div class="datum ${x[2]}">${esc(x[1])}</div></div>`).join('');
 const _fr=(d.asset_winners&&d.asset_winners[0])||(d.asset_losers&&d.asset_losers[0]);document.getElementById('assetRefreshed').innerHTML=_fr?`· Ranking actualizado ${esc(_fr.refreshed_at)} UTC`:'';
 const assetRows=(title,rows,rank)=>`<h3>${title}</h3><table><thead><tr><th>#</th><th>Asset</th><th>Trades</th><th>Wins</th><th>Losses</th><th>Win %</th><th>Expectancy</th><th>Total R</th><th>PF</th></tr></thead><tbody>${rows.map(x=>`<tr class="${x[rank]===1?'first':''}"><td>${esc(x[rank])}</td><td><b>${esc(x.symbol)}</b></td><td>${esc(x.closed_trades)}</td><td>${esc(x.wins)}</td><td>${esc(x.losses)}</td><td>${fmt(x.win_rate_pct)}%</td><td>${fmt(x.expectancy_r)}R</td><td>${fmt(x.total_r)}R</td><td>${fmt(x.profit_factor)}</td></tr>`).join('')}</tbody></table>`;document.getElementById('assets').innerHTML=assetRows('Mejores',d.asset_winners||[],'winner_rank')+assetRows('Peores',d.asset_losers||[],'loser_rank');
  const _hr=d.hour_tiers&&d.hour_tiers.ALL&&d.hour_tiers.ALL[0];document.getElementById('hourRefreshed').innerHTML=_hr?`· Actualizado ${esc(_hr.refreshed_at)} UTC`:'';
  const hourRows=(rows)=>`<table><thead><tr><th>Hora UTC</th><th>Hora ET</th><th>Tier</th><th>Trades</th><th>Wins</th><th>Losses</th><th>Win %</th><th>Expectancy</th><th>Total R</th><th>PF</th></tr></thead><tbody>${[...(rows||[])].sort((a,b)=>({PREFERRED:0,NEUTRAL:1,AVOID:2}[a.tier]-{PREFERRED:0,NEUTRAL:1,AVOID:2}[b.tier])||b.total_r-a.total_r).map(x=>`<tr><td><b>${esc(x.hour_utc)}:00 UTC</b></td><td>${esc(((x.hour_utc-4+24)%24))}:00 ET</td><td><span class="pill ${x.tier==='PREFERRED'?'win':x.tier==='AVOID'?'loss':''}">${esc(x.tier)}</span></td><td>${esc(x.closed_trades)}</td><td>${esc(x.wins)}</td><td>${esc(x.losses)}</td><td>${fmt(x.win_rate_pct)}%</td><td>${fmt(x.expectancy_r)}R</td><td>${fmt(x.total_r)}R</td><td>${fmt(x.profit_factor)}</td></tr>`).join('')}</tbody></table>`;document.getElementById('hours').innerHTML=hourRows(d.hour_tiers&&d.hour_tiers.ALL);
 const er=d.demo_errors||[];document.getElementById('errors').innerHTML=er.length?`<table><thead><tr><th>Hora</th><th>Activo</th><th>Causa</th><th>Opportunity</th><th>Order ID</th><th>Acción</th><th>Bloqueado</th></tr></thead><tbody>${er.map(x=>`<tr><td>${esc(x.created_at)}</td><td><b>${esc(x.symbol)}</b></td><td>${esc(x.error_message)}</td><td>${esc(x.opportunity_id||'N/A')}</td><td>${esc(x.exchange_order_id||'N/A')}</td><td>${esc(x.action_taken)}</td><td class="bad">${x.asset_blocked?'SI':'NO'}</td></tr>`).join('')}</tbody></table>`:'<p class="hint">Sin incidencias registradas.</p>';
 const os=d.demo_orders||[];document.getElementById('orders').innerHTML=os.length?`<table><thead><tr><th>Hora</th><th>Activo</th><th>Opportunity</th><th>Estado</th><th>Client ID</th><th>Exchange ID</th><th>Notional</th></tr></thead><tbody>${os.map(x=>`<tr><td>${esc(x.created_at)}</td><td><b>${esc(x.symbol)}</b></td><td>${esc(x.opportunity_id)}</td><td>${esc(x.status)}</td><td>${esc(x.client_order_id||'N/A')}</td><td>${esc(x.exchange_order_id||'N/A')}</td><td>${esc(x.notional_usdt||'N/A')} USDT</td></tr>`).join('')}</tbody></table>`:'<p class="hint">Sin intents registrados.</p>';
  document.getElementById('opps').innerHTML=d.opportunities.map(o=>`<tr><td>${esc(o.detected_at)}</td><td><b>${esc(o.symbol)}</b></td><td class="${o.state.includes('ENTRY')?'entry':o.state==='WATCH'?'watch':''}">${esc(o.state)}</td><td>${esc(o.setup_type)}</td><td>${fmt(o.score)}</td><td>${fmt(o.entry)}</td><td>${fmt(o.stop_loss)}</td><td>${fmt(o.tp1)}</td><td>${fmt(o.tp2)}</td><td>${fmt(o.primary_tp)}</td><td>${fmt(o.rr_to_primary)}</td><td class="${o.result_status==='WON'?'win':o.result_status==='STOPPED'?'loss':''}">${esc(o.result_status||'PENDING')}</td><td>${esc(o.ai_recommendation||o.ai_status||'N/A')}</td><td>${esc(o.derivatives_status)}</td></tr>`).join('');
 document.getElementById('events').innerHTML=d.events.map(e=>`<tr><td>${esc(e.timestamp)}</td><td>${esc(e.event_type)}</td><td>${esc(e.symbol)}</td><td>${esc(e.summary)}</td></tr>`).join('');
}
load();setInterval(load,10000);
</script></body></html>"""


WATERFALL_PANEL = '''<section class="wide"><h2>Waterfall v2 Forward Shadow</h2><p class="hint">SHORT virtual causal · v1 invalidada por lookahead · no envía órdenes Binance.</p><div id="waterfall" class="activity-grid"></div><div id="waterfallEvents" class="scroll"></div><div id="waterfallLegs" class="scroll"></div></section>'''
REVERSE_WATERFALL_PANEL = '''<section class="wide"><h2>Reverse Waterfall Forward Shadow</h2><p class="hint">LONG virtual · short capitulation momentum · no envía órdenes Binance.</p><div id="reverseWaterfall" class="activity-grid"></div></section>'''
WATERFALL_SCRIPT = '''<script>
async function loadWaterfall(){const w=(await fetch('/api/state').then(r=>r.json())).waterfall||{},f=x=>x==null?'N/A':Number(x).toFixed(4),t=x=>x?new Date(Number(x)).toISOString():'N/A',s=x=>x||'Sin evento';
document.getElementById('waterfall').innerHTML=[['Modo','FORWARD_SHADOW','ok'],['Config',w.version||'N/A',''],['Feed',w.cutoff_ms?'ACTIVO':'ESPERANDO',w.cutoff_ms?'ok':'warn'],['Último corte',t(w.cutoff_ms),''],['Estado',s(w.state),w.state?'warn':''],['Eventos',w.event_count||0,''],['Legs abiertas',w.open_legs||0,''],['Net R',f(w.net_r)+'R',Number(w.net_r)>=0?'ok':'bad'],['Fee drag',f(w.fees_r)+'R','warn']].map(x=>`<div class="item"><div class="label">${esc(x[0])}</div><div class="datum ${x[2]}">${esc(x[1])}</div></div>`).join('');
const e=w.events||[],l=w.legs||[];document.getElementById('waterfallEvents').innerHTML=e.length?`<h3>Eventos recientes</h3><table><thead><tr><th>Inicio</th><th>Estado</th><th>Señales</th></tr></thead><tbody>${e.map(x=>`<tr><td>${esc(x.started_at||x.created_at||'N/A')}</td><td>${esc(x.state)}</td><td>${esc(x.signal_count||0)}</td></tr>`).join('')}</tbody></table>`:'<p class="hint">Esperando condiciones BTC/1000PEPE.</p>';
document.getElementById('waterfallLegs').innerHTML=l.length?`<h3>Legs recientes</h3><table><thead><tr><th>Variante</th><th>Estado</th><th>Entry</th><th>Stop</th><th>TP</th><th>Net R</th></tr></thead><tbody>${l.map(x=>`<tr><td>${esc(x.variant_id||'N/A')}</td><td>${esc(x.status)}</td><td>${f(x.entry_price)}</td><td>${f(x.stop_price)}</td><td>${f(x.tp_price)}</td><td class="${Number(x.pnl_net_r)>=0?'ok':'bad'}">${f(x.pnl_net_r)}R</td></tr>`).join('')}</tbody></table>`:'';
}loadWaterfall();setInterval(loadWaterfall,10000);</script>'''
HTML = HTML.replace('<section class="wide"><h2>Trading Desk · Top 100</h2>', REVERSE_WATERFALL_PANEL + WATERFALL_PANEL + '<section class="wide"><h2>Trading Desk · Top 100</h2>').replace('</body></html>', WATERFALL_SCRIPT + '</body></html>')

STRATEGY_PANEL = '''<section class="wide"><h2>Strategy Registry</h2><p class="hint">Versiones y entornos congelados. Shadow no envía órdenes.</p><div id="strategies" class="scroll"></div><h3>Pedro Ultra · Scalping Forward Shadow</h3><div id="pedro" class="activity-grid"></div><h3>Pete · Panic Dip Forward Shadow</h3><div id="pete" class="activity-grid"></div></section>'''
STRATEGY_SCRIPT = '''<script>async function loadStrategies(){const d=await fetch('/api/state').then(r=>r.json()),rows=d.strategies||[],pu=d.pedro_ultra||{},pt=d.pete||{};document.getElementById('strategies').innerHTML=`<table><thead><tr><th>Estrategia</th><th>Version</th><th>Owner</th><th>Entorno</th><th>Estado</th><th>Hash</th></tr></thead><tbody>${rows.map(x=>`<tr><td><b>${esc(x.strategy_id)}</b></td><td>${esc(x.version)}</td><td>${esc(x.owner_agent_id)}</td><td>${esc(x.environment)}</td><td>${esc(x.promotion_state)}</td><td>${esc(x.config_hash.slice(0,10))}</td></tr>`).join('')}</tbody></table>`;document.getElementById('pedro').innerHTML=[['Version',pu.version||'N/A'],['Trades',pu.trades||0],['Abiertos',pu.open||0],['Net PnL',fmt(pu.net_pnl)+' USDT']].map(x=>`<div class="item"><div class="label">${x[0]}</div><div class="datum">${esc(x[1])}</div></div>`).join('');document.getElementById('pete').innerHTML=[['Version',pt.version||'N/A'],['Analisis',pt.analyses||0],['Candidatas',pt.candidates||0],['Tramos Shadow',pt.tranches||0]].map(x=>`<div class="item"><div class="label">${x[0]}</div><div class="datum">${esc(x[1])}</div></div>`).join('')}loadStrategies();setInterval(loadStrategies,10000);</script>'''
HTML = HTML.replace(WATERFALL_PANEL, STRATEGY_PANEL + WATERFALL_PANEL).replace('</body></html>', STRATEGY_SCRIPT + '</body></html>')

LUMEN_PANEL = '''<section class="wide"><h2>Lumen · Data Freshness</h2><p class="hint">FRESH ≤30s · DEGRADED 31-60s · STALE &gt;60s</p><div id="lumen" class="activity-grid"></div></section>'''
LUMEN_SCRIPT = '''<script>async function loadLumen(){const d=await fetch('/api/state').then(r=>r.json());document.getElementById('lumen').innerHTML=(d.feed_health||[]).map(x=>`<div class="item"><div class="label">${esc(x.feed_name)}</div><div class="datum ${x.status==='FRESH'?'ok':x.status==='STALE'?'bad':'warn'}">${esc(x.status)}</div><small>edad ${Number(x.age_seconds||0).toFixed(1)}s · atraso ${Number(x.delay_seconds||0).toFixed(1)}s</small></div>`).join('')}loadLumen();setInterval(loadLumen,10000);</script>'''
HTML = HTML.replace(STRATEGY_PANEL, LUMEN_PANEL + STRATEGY_PANEL).replace('</body></html>', LUMEN_SCRIPT + '</body></html>')

REVERSE_WATERFALL_SCRIPT = '''<script>async function loadReverseWaterfall(){const d=await fetch('/api/state').then(r=>r.json()),w=d.reverse_waterfall||{},v=w.validation||{};document.getElementById('reverseWaterfall').innerHTML=[['Version Shadow',w.version||'N/A'],['Version Demo',w.demo_version||'N/A'],['Estado',w.state||'NORMAL'],['Validación',v.status||'N/A'],['Demo',w.demo_execution||'BLOQUEADO'],['Eventos',w.events||0],['Señales',w.signals||0],['Legs abiertas',w.open_legs||0],['Legs cerradas',w.closed_legs||0],['Net PnL',fmt(w.net_pnl)+' USD']].map(x=>`<div class="item"><div class="label">${esc(x[0])}</div><div class="datum ${x[0]==='Validación'&&x[1]!=='PASS'||x[0]==='Demo'&&x[1]==='BLOQUEADO'?'bad':''}">${esc(x[1])}</div></div>`).join('')}loadReverseWaterfall();setInterval(loadReverseWaterfall,10000);</script>'''
HTML = HTML.replace('</body></html>', REVERSE_WATERFALL_SCRIPT + '</body></html>')

DEMO_PERFORMANCE_PANEL = '''<section class="wide binance"><h2>Binance Demo · Rendimiento realizado</h2><p class="hint">Solo ciclos cerrados con entrada y salida atribuidas. Ciclos incompletos no entran en estadísticas.</p><div id="demoPerformance" class="activity-grid"></div><div id="demoCycles" class="scroll"></div></section>'''
DEMO_PERFORMANCE_SCRIPT = '''<script>async function loadDemoPerformance(){const d=await fetch('/api/state').then(r=>r.json()),p=d.demo_performance||{},rows=d.demo_recent_cycles||[];document.getElementById('demoPerformance').innerHTML=[['Cierres confiables',p.trusted_closed||0],['Wins',p.wins||0],['Losses',p.losses||0],['Win rate',fmt(p.win_rate_pct)+'%'],['Realized',fmt(p.realized_pnl)+' USDT'],['Comisión',fmt(p.commission)+' USDT'],['Funding',fmt(p.funding)+' USDT'],['Neto',fmt(p.net_pnl)+' USDT'],['PF',fmt(p.profit_factor)],['Sin atribuir',p.unattributed||0]].map(x=>`<div class="item"><div class="label">${esc(x[0])}</div><div class="datum ${x[0]==='Neto'?(Number(p.net_pnl)>=0?'ok':'bad'):''}">${esc(x[1])}</div></div>`).join('');document.getElementById('demoCycles').innerHTML=rows.length?`<table><thead><tr><th>Ciclo</th><th>Activo</th><th>Resultado</th><th>Realized</th><th>Fees</th><th>Funding</th><th>Neto</th><th>Estrategia</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.position_cycle_id)}</td><td><b>${esc(x.symbol)}</b></td><td class="${x.result==='WIN'?'ok':x.result==='LOSS'?'bad':''}">${esc(x.result)}</td><td>${fmt(x.realized_pnl)}</td><td>${fmt(x.commission)}</td><td>${fmt(x.funding)}</td><td>${fmt(x.net_pnl)}</td><td>${esc(x.strategy_version||'N/A')}</td></tr>`).join('')}</tbody></table>`:''}loadDemoPerformance();setInterval(loadDemoPerformance,10000);</script>'''
HTML = HTML.replace('<section class="wide binance"><h2>Binance Futures Demo · conexión y protección</h2>', DEMO_PERFORMANCE_PANEL + '<section class="wide binance"><h2>Binance Futures Demo · conexión y protección</h2>').replace('</body></html>', DEMO_PERFORMANCE_SCRIPT + '</body></html>')

DEMO_ACCOUNT_PANEL = '''<section class="wide binance"><h2>Binance Demo · Balance ledger</h2><p class="hint">Historial de snapshots de cuenta demo. Sirve para reconciliar cambios de wallet contra fills, funding y ciclos atribuidos.</p><div id="demoAccount" class="activity-grid"></div></section>'''
DEMO_ACCOUNT_SCRIPT = '''<script>async function loadDemoAccount(){const d=await fetch('/api/state').then(r=>r.json()),a=d.demo_account||{},l=a.latest||{},p=a.previous||{},delta=a.wallet_delta;document.getElementById('demoAccount').innerHTML=[['Estado',a.status||'N/A',a.status==='OK'?'ok':'warn'],['Snapshots',a.snapshots||0,''],['Última captura',l.captured_at||'N/A',''],['Wallet ledger',l.total_wallet_balance==null?'N/A':fmt(l.total_wallet_balance)+' USDT',''],['Disponible ledger',l.available_balance==null?'N/A':fmt(l.available_balance)+' USDT',''],['Delta vs previa',delta==null?'N/A':fmt(delta)+' USDT',Number(delta)>=0?'ok':'bad'],['Previo',p.total_wallet_balance==null?'N/A':fmt(p.total_wallet_balance)+' USDT',''],['Unrealized',l.total_unrealized_pnl==null?'N/A':fmt(l.total_unrealized_pnl)+' USDT',Number(l.total_unrealized_pnl)>=0?'ok':'bad']].map(x=>`<div class="item"><div class="label">${esc(x[0])}</div><div class="datum ${x[2]}">${esc(x[1])}</div></div>`).join('')}loadDemoAccount();setInterval(loadDemoAccount,10000);</script>'''
HTML = HTML.replace(DEMO_PERFORMANCE_PANEL, DEMO_ACCOUNT_PANEL + DEMO_PERFORMANCE_PANEL).replace('</body></html>', DEMO_ACCOUNT_SCRIPT + '</body></html>')

AGENT_PANEL = '''<section class="wide agent-floor"><div class="desk-brand"><img src="/assets/everythingailogo.png" alt="EverythingAI logo"><div><div class="kicker">OPERATIONS FLOOR</div><h2>EVERYTHINGAI TRADING DESK</h2><p class="hint">Piso de operaciones. Estados LIVE reflejan jobs existentes; DESIGN son roles aún no automatizados.</p></div></div><div class="office"><div class="city"><i></i><i></i><i></i><i></i><i></i></div><div class="office-sign">MARKET OPERATIONS</div><div id="agents" class="agent-grid"></div></div></section>'''
AGENT_STYLE = '''<style>.desk-brand{display:flex;align-items:center;gap:16px;margin-bottom:18px}.desk-brand img{width:76px;max-height:54px;object-fit:contain;background:#fff;border-radius:6px;padding:4px}.desk-brand h2{margin:2px 0;font-size:22px;letter-spacing:.04em}.kicker{color:#f0b90b;font-size:11px;font-weight:700;letter-spacing:.15em}.agent-floor{border-color:#5865f2;background:linear-gradient(135deg,#161b22,#121829)}.office{position:relative;overflow:hidden;padding:50px 16px 16px;background:linear-gradient(#202b4d 0 52%,#142034 52% 56%,#6b4e3d 56% 100%);border:4px solid #0b1020;box-shadow:inset 0 0 0 3px #5865f2}.city{position:absolute;inset:8px 8px auto;display:flex;gap:4px;height:35px;align-items:end;background:#0d1830;border:3px solid #7893c7;padding:3px}.city i{display:block;background:#253b67;width:16%;height:var(--h,55%);box-shadow:inset 3px 3px #f0b90b}.city i:nth-child(2){--h:90%}.city i:nth-child(3){--h:70%}.city i:nth-child(4){--h:100%}.city i:nth-child(5){--h:50%}.office-sign{position:absolute;top:54px;right:13px;color:#f0b90b;font:700 10px monospace;letter-spacing:.1em}.agent-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;position:relative}.agent{position:relative;background:#263242;border:3px solid #0b1020;border-radius:3px;padding:8px 8px 9px;min-height:142px;box-shadow:4px 4px 0 #09101d}.agent:before{content:'';position:absolute;left:12%;right:12%;bottom:27px;height:23px;background:#5d3f2e;border:3px solid #26170f;box-shadow:inset 0 4px #9b7050}.agent:after{content:'';position:absolute;left:40%;bottom:48px;width:36px;height:22px;background:#111;border:3px solid #9ea7bd;box-shadow:inset 0 0 0 3px #264d67}.agent-top{display:flex;align-items:center;gap:9px;position:relative;z-index:1}.sprite{width:45px;height:45px;background-image:url('/assets/everythingai-trading-desk-spritesheet.png');background-size:400% 400%;background-position:var(--x) var(--y);border:3px solid #ffe8a3;box-shadow:3px 3px 0 #5865f2;image-rendering:pixelated}.agent-name{font-weight:700}.agent-role{font-size:11px;color:#b6c5e2}.agent-task{font-size:12px;line-height:1.3;margin:9px 0 26px;position:relative;z-index:1}.agent-state{font:700 10px monospace;letter-spacing:.08em;position:absolute;bottom:8px;right:9px;z-index:2}.agent-state.live{color:#62e58c}.agent-state.design{color:#ffd166}@media(max-width:900px){.agent-grid{grid-template-columns:repeat(2,1fr)}.desk-brand{align-items:flex-start}.office{padding:50px 10px 10px}}</style>'''
AGENT_SCRIPT = '''<script>async function loadAgents(){const d=await fetch('/api/state').then(r=>r.json()),p=i=>`${-(i%4)*100}% ${-Math.floor(i/4)*100}%`,roles=d.agents||[];document.getElementById('agents').innerHTML=roles.map((x,i)=>`<article class="agent"><div class="agent-top"><div class="sprite" style="--x:${p(i).split(' ')[0]};--y:${p(i).split(' ')[1]}"></div><div><div class="agent-name">${x.name}</div><div class="agent-role">${x.role}</div></div></div><div class="agent-task">${x.task}</div><div class="agent-state ${['ACTIVE','WATCHING','READY','RESEARCH'].includes(x.status)?'live':'design'}">${x.status}</div></article>`).join('')}loadAgents();setInterval(loadAgents,10000);</script>'''
HTML = HTML.replace('</style></head>', AGENT_STYLE + '</style></head>').replace('<div id="summary" class="grid"></div>', AGENT_PANEL + '<div id="summary" class="grid"></div>').replace('</body></html>', AGENT_SCRIPT + '</body></html>')


def query(sql: str, args: tuple = ()) -> list[dict]:
    if not DB.exists():
        return []
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        return [dict(row) for row in c.execute(sql, args)]


def table_exists(name: str) -> bool:
    if not DB.exists():
        return False
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        row = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        return row is not None


def demo_account_ledger() -> dict:
    if not table_exists("demo_account_snapshots"):
        return {"status": "NO_LEDGER", "snapshots": 0, "latest": None, "previous": None, "wallet_delta": None}
    rows = query(
        """SELECT id,total_wallet_balance,available_balance,total_margin_balance,total_unrealized_pnl,
                  total_position_initial_margin,total_open_order_initial_margin,asset,captured_at
           FROM demo_account_snapshots ORDER BY id DESC LIMIT 2"""
    )
    latest = rows[0] if rows else None
    previous = rows[1] if len(rows) > 1 else None
    return {
        "status": "OK" if latest else "EMPTY",
        "snapshots": query("SELECT COUNT(*) AS n FROM demo_account_snapshots")[0]["n"] if latest else 0,
        "latest": latest,
        "previous": previous,
        "wallet_delta": (latest["total_wallet_balance"] - previous["total_wallet_balance"]) if latest and previous else None,
        "available_delta": (latest["available_balance"] - previous["available_balance"]) if latest and previous else None,
    }


def state() -> dict:
    rows = query("""
      SELECT o.id,o.detected_at,o.symbol,o.state,o.setup_type,o.score,
             tp.entry,tp.stop_loss,tp.tp1,tp.tp2,tp.primary_tp,tp.rr_to_primary,
             sr.status AS result_status,ar.status AS ai_status,
             ar.shadow_recommendation AS ai_recommendation,ar.confidence AS ai_confidence,
             ar.reviewed_at AS ai_reviewed_at
       FROM opportunities o JOIN trade_plans tp ON tp.opportunity_id=o.id
       LEFT JOIN shadow_trade_results sr ON sr.opportunity_id=o.id
       LEFT JOIN shadow_ai_reviews ar ON ar.opportunity_id=o.id
      ORDER BY o.id DESC LIMIT 100
    """)
    events = query("SELECT timestamp,event_type,symbol,payload_json FROM event_log ORDER BY id DESC LIMIT 50")
    for event in events:
        try:
            payload = json.loads(event.pop("payload_json"))
            event["summary"] = payload.get("alert", {}).get("headline", event["event_type"])
        except (TypeError, ValueError):
            event["summary"] = event["event_type"]
    results = query("SELECT status,COUNT(*) AS n FROM shadow_trade_results GROUP BY status")
    counts = {r["status"]: r["n"] for r in results}
    closed = counts.get("WON", 0) + counts.get("STOPPED", 0)
    heartbeat = json.loads(HEARTBEAT.read_text()) if HEARTBEAT.exists() else {}
    last_event = query("SELECT timestamp,event_type FROM event_log ORDER BY id DESC LIMIT 1")
    last_scan = query("SELECT detected_at FROM opportunities ORDER BY id DESC LIMIT 1")
    waterfall_events = query("SELECT e.*,COUNT(s.id) AS signal_count FROM waterfall_v2_events e LEFT JOIN waterfall_v2_signals s ON s.event_id=e.id GROUP BY e.id ORDER BY e.id DESC LIMIT 20")
    waterfall_legs = query("SELECT * FROM waterfall_v2_legs ORDER BY id DESC LIMIT 50")
    waterfall_totals = query("SELECT COALESCE(SUM(status='OPEN'),0) AS open_legs,COALESCE(SUM(pnl_net_r),0) AS net_r,COALESCE(SUM(pnl_gross_r-pnl_net_r),0) AS fees_r FROM waterfall_v2_legs")
    waterfall = dict(waterfall_totals[0]) if waterfall_totals else {}
    waterfall.update({'event_count': query('SELECT COUNT(*) n FROM waterfall_v2_events')[0]['n'],
                      'cutoff_ms': query('SELECT MAX(last_close_ms) n FROM waterfall_v2_cursors')[0]['n'],
                      'state': 'COLLECTING', 'version': 'waterfall-forward-v2'})
    waterfall.update({'events': waterfall_events, 'legs': waterfall_legs})
    pedro = query("SELECT COUNT(*) AS trades,COALESCE(SUM(status='OPEN'),0) AS open,COALESCE(SUM(net_pnl),0) AS net_pnl FROM pedro_ultra_trades")[0]
    pedro_version = query("SELECT version FROM pedro_ultra_config_versions ORDER BY created_at DESC LIMIT 1")
    pedro['version'] = pedro_version[0]['version'] if pedro_version else None
    pete = query("SELECT COUNT(*) AS analyses,COALESCE(SUM(signal='CAPITULATION_CANDIDATE'),0) AS candidates FROM pete_daily_analyses")[0]
    pete_tranches = query("SELECT COUNT(*) AS n FROM pete_shadow_tranches")[0]['n']
    pete_version = query("SELECT version FROM pete_config_versions ORDER BY created_at DESC LIMIT 1")
    pete.update({'tranches': pete_tranches, 'version': pete_version[0]['version'] if pete_version else None})
    reverse_runtime = query("SELECT state FROM reverse_waterfall_runtime WHERE symbol='BTCUSDT'")
    reverse_totals = query("""SELECT COALESCE(SUM(status!='OPEN'),0) AS closed_legs,
      COALESCE(SUM(status='OPEN'),0) AS open_legs,COALESCE(SUM(net_pnl),0) AS net_pnl
      FROM reverse_waterfall_legs""")[0]
    reverse_totals.update({'state': reverse_runtime[0]['state'] if reverse_runtime else 'NORMAL',
                           'events': query('SELECT COUNT(*) n FROM reverse_waterfall_events')[0]['n'],
                           'signals': query("SELECT COUNT(*) n FROM reverse_waterfall_signals WHERE action NOT IN ('NONE','BASELINE_ONLY')")[0]['n'],
                           'version': 'reverse-waterfall-forward-v1'})
    validation_path = ROOT / 'data' / 'reports' / 'reverse-waterfall' / 'validation-latest.json'
    reverse_totals['validation'] = json.loads(validation_path.read_text()) if validation_path.exists() else {}
    rollout_path = ROOT / 'config' / 'demo_strategy_rollout.json'
    rollout = json.loads(rollout_path.read_text()) if rollout_path.exists() else {}
    reverse_demo = rollout.get('strategies', {}).get('reverse-waterfall', {})
    override = reverse_demo.get('demo_validation_override', {})
    reverse_totals['demo_version'] = reverse_demo.get('version')
    reverse_totals['demo_execution'] = (
        'AUTORIZADO_OVERRIDE'
        if reverse_demo.get('enabled') and override.get('authorized') is True and override.get('environment') == 'BINANCE_DEMO'
        else 'BLOQUEADO'
    )
    demo_rows = query("SELECT * FROM demo_cycle_performance ORDER BY position_cycle_id")
    trusted = [row for row in demo_rows if row['result'] in ('WIN', 'LOSS', 'FLAT') and row['attribution_complete']]
    gains = sum(row['net_pnl'] for row in trusted if row['net_pnl'] > 0)
    losses = abs(sum(row['net_pnl'] for row in trusted if row['net_pnl'] < 0))
    demo_performance = {'trusted_closed': len(trusted), 'wins': sum(row['result'] == 'WIN' for row in trusted),
      'losses': sum(row['result'] == 'LOSS' for row in trusted), 'flats': sum(row['result'] == 'FLAT' for row in trusted),
      'unattributed': sum(row['result'] == 'UNATTRIBUTED' for row in demo_rows),
      'win_rate_pct': 100 * sum(row['result'] == 'WIN' for row in trusted) / len(trusted) if trusted else None,
      'realized_pnl': sum(row['realized_pnl'] for row in trusted), 'commission': sum(row['commission'] for row in trusted),
      'funding': sum(row['funding'] for row in trusted), 'net_pnl': sum(row['net_pnl'] for row in trusted),
      'profit_factor': gains / losses if losses else None}
    opportunity_count = query("SELECT COUNT(*) AS n FROM opportunities")[0]["n"]
    plan_count = query("SELECT COUNT(*) AS n FROM trade_plans")[0]["n"]
    return {"runtime": "ACTIVO", "metrics": {"opportunities": opportunity_count, "plans": plan_count, "open": counts.get("OPEN", 0), "win_rate": round(counts.get("WON", 0) / closed * 100, 2) if closed else 0}, "activity": {"scheduler_state": heartbeat.get("scheduler_state", "N/A"), "last_job": heartbeat.get("last_job", "N/A"), "last_event": f"{last_event[0]['timestamp']} · {last_event[0]['event_type']}" if last_event else "N/A", "last_scan": last_scan[0]["detected_at"] if last_scan else "N/A"}, "agents": query("SELECT agent_id,name,role,task,mode,status,updated_at FROM desk_agents ORDER BY rowid"), "feed_health": query("SELECT feed_name,status,age_seconds,delay_seconds,checked_at FROM data_feed_health ORDER BY feed_name"), "strategies": query("SELECT strategy_id,version,config_hash,owner_agent_id,environment,promotion_state,updated_at FROM strategy_registry ORDER BY strategy_id"), "pedro_ultra": pedro, "pete": pete, "reverse_waterfall": reverse_totals, "waterfall": waterfall, "demo_account": demo_account_ledger(), "demo_performance": demo_performance, "demo_recent_cycles": list(reversed(trusted[-30:])), "asset_winners": query("SELECT * FROM shadow_asset_top_100_winners LIMIT 100"), "asset_losers": query("SELECT * FROM shadow_asset_top_100_losers LIMIT 100"), "hour_tiers": {w: query("SELECT * FROM shadow_hour_performance WHERE window=? ORDER BY hour_utc", (w,)) for w in ("ALL", "30D", "7D")}, "opportunities": rows, "events": events, "heartbeat": heartbeat, "binance_demo": binance_state(), "demo_errors": query("SELECT * FROM demo_order_errors ORDER BY id DESC LIMIT 30"), "demo_orders": query("SELECT * FROM demo_order_intents ORDER BY id DESC LIMIT 50")}


def binance_state() -> dict:
    global _BINANCE_CACHE
    with _BINANCE_CACHE_LOCK:
        cached_at, cached = _BINANCE_CACHE
        if time.monotonic() - cached_at < 10:
            return cached
    try:
        client = BinanceDemoClient(timeout=8)
        account = client.account()
        symbol = "BTCUSDT"
        config_rows = client.symbol_config(symbol)
        positions = [p for p in account.get("positions", []) if p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0]
        algos = client.open_algo_orders(symbol)
        stop = next((o for o in algos if o.get("orderType") == "STOP_MARKET"), None)
        take_profit = next((o for o in algos if o.get("orderType") == "TAKE_PROFIT_MARKET"), None)
        config = config_rows[0] if config_rows else {}
        position = positions[0] if positions else None
        result = {
            "connected": True,
            "endpoint": client.base_url,
            "wallet_balance": account.get("totalWalletBalance"),
            "available_balance": account.get("availableBalance"),
            "symbol_config": {"margin_type": config.get("marginType"), "leverage": config.get("leverage")},
            "position": None if not position else {"symbol": symbol, "amount": position.get("positionAmt"), "entry_price": position.get("entryPrice"), "unrealized_pnl": position.get("unrealizedProfit")},
            "stop": None if not stop else {"algo_id": stop.get("algoId"), "trigger_price": stop.get("triggerPrice"), "status": stop.get("algoStatus")},
            "take_profit": None if not take_profit else {"algo_id": take_profit.get("algoId"), "trigger_price": take_profit.get("triggerPrice"), "status": take_profit.get("algoStatus")},
        }
        with _BINANCE_CACHE_LOCK:
            _BINANCE_CACHE = (time.monotonic(), result)
        return result
    except (DemoTradingError, KeyError, TypeError, ValueError) as exc:
        result = {"connected": False, "error": str(exc)}
        with _BINANCE_CACHE_LOCK:
            _BINANCE_CACHE = (time.monotonic(), result)
        return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/healthz":
            body = b'{"ok":true}'
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path == "/assets/everythingailogo.png" and LOGO.exists():
            body = LOGO.read_bytes()
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Cache-Control", "public, max-age=86400"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path == "/assets/everythingai-trading-desk-spritesheet.png" and SPRITESHEET.exists():
            body = SPRITESHEET.read_bytes()
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Cache-Control", "public, max-age=86400"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path == "/api/state":
            body = json.dumps(state(), ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        body = HTML.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass


if __name__ == "__main__":
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "8890"))
    print(f"Trading Desk dashboard: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

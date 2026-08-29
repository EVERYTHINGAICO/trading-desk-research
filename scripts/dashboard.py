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
sys.path.insert(0, str(ROOT / "src"))
from desk.binance_demo import BinanceDemoClient, DemoTradingError

_BINANCE_CACHE: tuple[float, dict] = (0.0, {})
_BINANCE_CACHE_LOCK = threading.Lock()

HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trading Desk Shadow</title><style>
:root{font:14px system-ui;background:#0d1117;color:#e6edf3}body{max-width:1400px;margin:0 auto;padding:28px}h1{margin:0 0 5px;font-size:28px}small,.muted{color:#8b949e}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0}.card,section{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px}.value{font-size:25px;font-weight:700;margin-top:6px}.ok{color:#3fb950}.bad{color:#f85149}.warn{color:#d29922}.wide{grid-column:1/-1}.binance{border-color:#f0b90b}.binance-grid,.activity-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.binance-grid .item,.activity-grid .item{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:12px}.label{color:#8b949e;font-size:12px}.datum{font-size:17px;font-weight:650;margin-top:5px}.hint{line-height:1.5;color:#c9d1d9}.legend{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.legend span{padding:5px 9px;border-radius:99px;background:#30363d}.ok-bg{border-color:#238636!important}.bad-bg{border-color:#da3633!important}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px;border-bottom:1px solid #30363d;white-space:nowrap}th{color:#8b949e;font-weight:500}.scroll{overflow:auto}button{background:#238636;color:white;border:0;border-radius:6px;padding:8px 12px;cursor:pointer}.pill{padding:3px 7px;border-radius:999px;background:#30363d}.entry{color:#ff7b72}.watch{color:#d29922}.win{color:#3fb950}.loss{color:#f85149}.first td{background:#1f6feb22!important;color:#58a6ff!important}.first td b{color:#58a6ff}@media(max-width:900px){.grid,.binance-grid,.activity-grid{grid-template-columns:repeat(2,1fr)}body{padding:16px}.wide{grid-column:1/-1}}
</style></head><body><header><h1>Trading Desk Shadow</h1><div class="muted">Modo paper/shadow · solo lectura · actualización cada 10 segundos</div></header>
<div id="summary" class="grid"></div><section class="wide"><h2>¿Está trabajando?</h2><div id="activity" class="activity-grid"></div><p class="hint">El escáner amplio crea nuevas oportunidades cada hora. Los monitores revisan las señales abiertas cada 5 minutos y la protección Binance cada 15 segundos.</p></section><section class="wide binance"><h2>Binance Futures Demo · conexión y protección</h2><div id="binance" class="binance-grid"></div></section><section class="wide"><h2>Trading Desk · Top 100</h2><p class="hint">Mínimo 30 trades cerrados. Ranking por expectancy R (ventana ALL). <span id="assetRefreshed" class="muted"></span></p><div id="assets" class="scroll"></div></section><section class="wide"><h2>Seguimiento de órdenes</h2><div id="orders" class="scroll"></div></section><section class="wide"><h2>Incidencias y activos bloqueados</h2><div id="errors" class="scroll"></div></section><section class="wide"><h2>Cómo leer los estados</h2><div class="legend"><span><b>WATCH</b> = observando</span><span><b>PRE_ENTRY</b> = preparando entrada</span><span><b>ENTRY_READY</b> = señal lista para replicar</span><span><b>CLOSED_WIN</b> = objetivo alcanzado</span><span><b>INVALIDATED</b> = stop/invalida</span><span><b>PASS</b> = no cumple filtros</span></div></section><section class="wide"><h2>Entradas y oportunidades recientes</h2><div class="scroll"><table><thead><tr><th>Hora</th><th>Símbolo</th><th>Estado</th><th>Setup</th><th>Score</th><th>Entry</th><th>Stop</th><th>TP1</th><th>TP2</th><th>Primary</th><th>R:R</th><th>Resultado</th><th>IA</th><th>Derivados</th></tr></thead><tbody id="opps"></tbody></table></div></section>
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
 const er=d.demo_errors||[];document.getElementById('errors').innerHTML=er.length?`<table><thead><tr><th>Hora</th><th>Activo</th><th>Causa</th><th>Opportunity</th><th>Order ID</th><th>Acción</th><th>Bloqueado</th></tr></thead><tbody>${er.map(x=>`<tr><td>${esc(x.created_at)}</td><td><b>${esc(x.symbol)}</b></td><td>${esc(x.error_message)}</td><td>${esc(x.opportunity_id||'N/A')}</td><td>${esc(x.exchange_order_id||'N/A')}</td><td>${esc(x.action_taken)}</td><td class="bad">${x.asset_blocked?'SI':'NO'}</td></tr>`).join('')}</tbody></table>`:'<p class="hint">Sin incidencias registradas.</p>';
 const os=d.demo_orders||[];document.getElementById('orders').innerHTML=os.length?`<table><thead><tr><th>Hora</th><th>Activo</th><th>Opportunity</th><th>Estado</th><th>Client ID</th><th>Exchange ID</th><th>Notional</th></tr></thead><tbody>${os.map(x=>`<tr><td>${esc(x.created_at)}</td><td><b>${esc(x.symbol)}</b></td><td>${esc(x.opportunity_id)}</td><td>${esc(x.status)}</td><td>${esc(x.client_order_id||'N/A')}</td><td>${esc(x.exchange_order_id||'N/A')}</td><td>${esc(x.notional_usdt||'N/A')} USDT</td></tr>`).join('')}</tbody></table>`:'<p class="hint">Sin intents registrados.</p>';
  document.getElementById('opps').innerHTML=d.opportunities.map(o=>`<tr><td>${esc(o.detected_at)}</td><td><b>${esc(o.symbol)}</b></td><td class="${o.state.includes('ENTRY')?'entry':o.state==='WATCH'?'watch':''}">${esc(o.state)}</td><td>${esc(o.setup_type)}</td><td>${fmt(o.score)}</td><td>${fmt(o.entry)}</td><td>${fmt(o.stop_loss)}</td><td>${fmt(o.tp1)}</td><td>${fmt(o.tp2)}</td><td>${fmt(o.primary_tp)}</td><td>${fmt(o.rr_to_primary)}</td><td class="${o.result_status==='WON'?'win':o.result_status==='STOPPED'?'loss':''}">${esc(o.result_status||'PENDING')}</td><td>${esc(o.ai_recommendation||o.ai_status||'N/A')}</td><td>${esc(o.derivatives_status)}</td></tr>`).join('');
 document.getElementById('events').innerHTML=d.events.map(e=>`<tr><td>${esc(e.timestamp)}</td><td>${esc(e.event_type)}</td><td>${esc(e.symbol)}</td><td>${esc(e.summary)}</td></tr>`).join('');
}
load();setInterval(load,10000);
</script></body></html>"""


def query(sql: str, args: tuple = ()) -> list[dict]:
    if not DB.exists():
        return []
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        return [dict(row) for row in c.execute(sql, args)]


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
    return {"runtime": "ACTIVO", "metrics": {"opportunities": len(query("SELECT id FROM opportunities")), "plans": len(query("SELECT id FROM trade_plans")), "open": counts.get("OPEN", 0), "win_rate": round(counts.get("WON", 0) / closed * 100, 2) if closed else 0}, "activity": {"scheduler_state": heartbeat.get("scheduler_state", "N/A"), "last_job": heartbeat.get("last_job", "N/A"), "last_event": f"{last_event[0]['timestamp']} · {last_event[0]['event_type']}" if last_event else "N/A", "last_scan": last_scan[0]["detected_at"] if last_scan else "N/A"}, "asset_winners": query("SELECT * FROM shadow_asset_top_100_winners LIMIT 100"), "asset_losers": query("SELECT * FROM shadow_asset_top_100_losers LIMIT 100"), "opportunities": rows, "events": events, "heartbeat": heartbeat, "binance_demo": binance_state(), "demo_errors": query("SELECT * FROM demo_order_errors ORDER BY id DESC LIMIT 30"), "demo_orders": query("SELECT * FROM demo_order_intents ORDER BY id DESC LIMIT 50")}


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
        if path == "/api/state":
            body = json.dumps(state(), ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        body = HTML.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8890), Handler).serve_forever()

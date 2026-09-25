# WATERFALL — PHASE 0 REPORT (Inspección + Plan de integración)

**Fecha:** 2026-08-31 · **Modo:** solo inspección, sin cambios de código.
**Fuente de spec:** `docs/WATERFALL_SHADOW_PROJECT_BIG_PICKLE_v5_UNLIMITED_LEGS.md`.

Instrucción recibida: producir el informe de Phase 0 y esperar aprobación. Nada del repositorio fue modificado por esta inspección.

---

## 1. Resumen ejecutivo

El sistema actual es una estrategia **LONG shadow** de una sola "pierna" por oportunidad, basada en vela 15m cerrada:
`scan (15m) -> opportunities + trade_plans -> resolver (live-forward) -> shadow_trade_results -> shadow_asset_performance -> reportes/dashboard/demo`.

El Waterfall pide: **régimen global BTC → evento por vehículo → legs SHORT ilimitados** (con re-arm), vela 5m cerrada, kit de salida fijo, resolver determinista, R dual (flat + gap-stress), fees por leg, performance por símbolo y trazabilidad alerta→event→leg→resultado.

Conclusión de la pregunta central de la spec (§Phase 0 / §14):

> **¿Puede `regime_event -> asset_event -> unlimited legs` reutilizar el pipeline LONG?**

Respuesta: **reutilizar las CONVENCIONES y los motores (resolver-core, dedupe/alertas, inserción, performance-aggregation, daily report) SÍ. Reutilizar las tablas genericas (`opportunities`/`trade_plans`/`shadow_trade_results`) DIRECTAS, NO es posible sin cirugía del schema** porque (a) la semántica SHORT invierte TP/SL, (b) una oportunidad LONG es única por símbolo/ciclo y el estado aquí es multi-leg por símbolo y por evento con re-arm, (c) hacen falta campos que no existen (dual R, fees, event_ids, config_version, max_hold, reclaim, exit-request). Diseño recomendado: tablas `waterfall_*` nuevas que **espejan las columnas núcleo LONG**, más un resolver-core compartido parametrizado por `direction` (LONG/SHORT) si se refactoriza con bajo riesgo; si no, un `waterfall_resolver` que re-use las mismas reglas (STOP_FIRST, gaps, MFE/MAE), sin tocar el código LONG existente.

Lo más importante: **el sistema LONG no guarda velas crudas, no persiste derivados, no tiene config_version, ni fees, ni dual-R, ni backtest/replay histórico.** Todo eso es trabajo nuevo de Fase 1+, no simple reuso.

---

## 2. Arquitectura encontrada

```
/shadow                            (repo, bind mount host: research/trading-desk-shadow)
  config/settings.json             config única (sin config_version)
  src/desk/
    scanner.py        analiza símbolo (15m, limit 120): score/estado/plan     [LONG]
    risk.py           risk gate (flags manuales, ATR/vol/estructura)
    state_machine.py  decide_state(score, rebound, quality) -> PASS/WATCH/PRE_ENTRY/ENTRY_READY
    context.py        btc_context (15m/1h/4h/1d vs EMA20) en close (regime simple)
    market.py         fetch_klines (mapea SOLO OHLCV+quote_volume+close_time; la API trae trade_count[8] y taker_buy[9/10] que NO se mapean)
    derivatives.py    snapshot() on-demand: mark, index, funding_rate, premium_basis, open_interest (status ok/error)
    resolver.py       resolve_shadow_trade: entry trigger (limit/stop/range), status WON/STOPPED/MISSED/OPEN, r_multiple (flat), mfe/mae, STOP_FIRST en barras ambiguas
    asset_performance.py  refresh: ventanas ALL/24H/7D/30D -> winner/loser rank, WR, expectancy, PF, avg win/loss R
    hour_performance.py   performance por hora UTC
    monitor.py        trigger_monitor + stateful_open_monitor (re-escanean oportunidades abiertas)
    alerts.py         dedupe (fingerprint+cooldown) -> jsonl por día
    events.py         payloads con alert (severity/headline/dedupe_key), schema_version="shadow_event_v1" (evento, no config)
    telegram_alerts.py solo notify_error (errores demo), no señales proactivas
    db.py             SCHEMA + migraciones por ADD COLUMN (dict migrations) + connect WAL/busy_timeout
    types.py          Candle (sin trade_count/taker), Opportunity, TradePlan
  scripts/
    run_shadow_once.py             scan masivo (ThreadPool 8): BTC context + derivados(on-demand) -> opportunities/plans/events
    run_shadow_cycle.py            init_db + run_shadow_once + resolve_shadow_open_trades
    resolve_shadow_open_trades.py  resuelve oportunidades OPEN con velas re-fetch (NO persistidas)
    run_scheduler_loop.py          build_jobs(): broad_scan, pre_ny/*, quality_stock_dip/*, trigger/stateful monitors, shadow_resolver, asset/hour perf refresh, demo executor/monitor/reconcile/protection
    dashboard.py                   servidor HTTP estático que lee la DB (paneles: summary/assets/hours/orders/errors/opps/events)
    generate_daily_report.py       reporte diario MD (states/setups/resolutions: WR, expectancy, PF, R avg)
    generate_trades_report.py      reporte trades + assets (latest md/json)
    run_binance_demo_once.py       ejecutor demo: gate BINANCE_PAUSED_LOW_AVAILABLE_BALANCE; abre SOLO oportunidades ENTRY_READY cuyo símbolo esté en shadow_asset_performance window=ALL y winner_rank<=251
    (quality_stock_dip_* / pre_ny_*) estrategias paralelas shadow con planes/tranches/results propios
  tests/
    unittest, 39 tests en 9 archivos (indicators, asset/hour performance, demo, fixtrades, ai_review, pre_ny, quality_stock_dip). SIN test de resolver ni de state_machine.
  data/
    desk.db (solo persistencia real), events/ alerts/ journals/ reports/
```

---

## 3. Componentes a reutilizar (sin duplicar)

| Componente | Cómo se reutiliza |
|---|---|
| `market.fetch_klines` | Extender `Candle` con `trade_count`, `taker_buy_base`, `taker_buy_quote` (indices 8/9/10 ya presentes en la API) → fuente cruda de Fase 1 y proxy de taker-flow |
| `derivatives.py` | Snapshot actual (mark/index/funding/OI/basis); extender con `takerBuyRatio`, `globalLong/short ratio`, `topTrader` ratios y esquema de persistencia |
| `resolver.py` | Reglas reutilizables: trigger con gaps (`limit_gap_through_entry`/`stop_gap_through_entry`), `STOP_FIRST_AMBIGUOUS_BAR`, MFE/MAE en R, `r_multiple` flat. Refactorizar núcleo a `direction` param o duplicar el patrón en `waterfall_resolver.py` |
| `db.py` | Patrón SCHEMA + dict `migrations` (ADD COLUMN) + `connect` (WAL, busy_timeout) y estilo `insert_event/insert_transition` |
| `alerts.py`/`events.py` | Reutilizar `evaluate_alert_emission` + `append_alert_jsonl` y construir payloads waterfall con dedupe_key por (regime/asset/leg) |
| `asset_performance.py` + `hour_performance.py` | Mismo SQL de agregación (WR, expectancy, PF, ranks) aplicado a `waterfall_leg` por vehículo |
| `generate_daily_report.py` / `dashboard.py` | Añadir secciones waterfall (eventos/legs por activo, resultados) respetando el formato existente |
| `run_scheduler_loop.py` | Registrar jobs `waterfall_capture` (~60s) y `waterfall_engine`/`waterfall_resolver` en `build_jobs()` |
| `tests/` | Convención unittest; añadir tests nuevos con el mismo estilo |
| Logos de señales | `journal.py` (append_jsonl/markdown) para legabilidad alerta/leg |

---

## 4. Pipeline LONG en detalle (referencia de convenciones)

1. **Scan:** `run_shadow_once` descubre universo (`discover_futures_symbols`, quote_volume≥1M), BTC regime label de context (15m/1h/4h/1d vs EMA20), y por símbolo: quality A/B/C, risk gate, classify_setup, score; estado por `decide_state` + cap por setup; plan con `atr_stop_multiple=1.2` de stop y TPs `tp1=1.0R / tp2=1.75R / primary=2.5R`.
2. **Resolver live-forward:** re-fetch de velas; trigger types limit/stop/range con semántica de gaps; estado `WON/STOPPED/MISSED/OPEN`; `r_multiple = (exit-entry)/risk` **flat** (el stop se resuelve exacto en `stop_loss`, nunca a MAE). `mae/mfe` en R se guardan por separado (esto es lo que permite calcular gap-stress fuera del pipeline).
3. **Performance:** `shadow_asset_performance` ventanas ALL/24H/7D/30D (WR, expectancy_r, total_r, avg win/loss R, PF, ranks winner/loser, min 30 cerrados). Top-251 winners alimenta al ejecutor demo.
4. **Reportes/dashboard:** daily MD + HTML con paneles.

**Nota: la estrategia LONG NO tiene fórmula de gap-stress/dual-R en código.** El análisis de crashes hecho antes de esta inspección (R plano −1.0R vs R a MAE, +14,046R → +3,207R) fue un estudio ad-hoc con `desk.db`, no un componente del sistema. El Waterfall debe introducir `r_flat_gross / r_flat_net / r_gap_stress` como **nuevas columnas del módulo** (no tocar el LONG).

---

## 5. Data gaps críticos (verificado en código y DB)

| Gap | Estado actual | Implicación Waterfall |
|---|---|---|
| Velas crudas persistidas | NO hay tabla; `fetch_klines` devuelve y se descarta (solo sobreviven fragments en diagnostics) | Sin tabla de velas 1m/5m no hay replay ni backtest ni resolución reproducible. Es la base de Fase 1 |
| Derivados persistidos | `derivatives_snapshot` va a `diagnostics_json` del scan (efímero); NO hay historial OI/funding/ratios | Fase 1: tabla `derivatives_snapshots` continua |
| taker buy/sell ratio | La API de klines lo trae (idx 9/10) pero `Candle` no lo mapea; endpoints `/futures/data/globalLongShortAccountRatio`, `topLongShortPositionRatio`, `topLongShortAccountRatio`, `takerlongshortRatio` → NO se usan | Extender `market.py` + `derivatives.py`; proxy `is_proxy` cuando se derive |
| config_version | No existe; `settings.json` es un archivo sin versión ni razón de cambio | Añadir `config_version` a config waterfall (y a cada row/leg/event) + tabla `config_versions` |
| fee model | No existe (la demo usa filtros de Binance, no modelo de fees para R) | Modelo maker/taker configurable tras los múltiples legs |
| Dual R (flat/gap-stress) | No existe en código | Columnas nuevas en `waterfall_leg` |
| Backtest/replay histórico | NO existe; el "replay" más cercano es `resolve_quality_stock_dip` que **re-fetcha** klines y resuelve planes guardados | Construir engine determinista local + archivo de velas crudas |
| Event lifecycle multi-leg | No existe (oportunidad única por scan) | Tablas de evento + re-arm + event-end bulk close |
| Timestamps manuales | Sin verificar contra Binance (tz provisional Tijuana) | Verificación en Fase 1 |
| Estado/máquina de régimen BTC | `context.py` solo da supportive/neutral/hostile por EMA20 en 4 TF; sin máquina de estados ni 5m/1m | Motor waterfall: NORMAL→...→EXHAUSTION sobre 1m/5m |

---

## 6. Matriz de backfill (borrador a verificar en tiempo de implementación)

Ver políticas §5.1/§5.2 del spec. Previsión Binance al momento de esta inspección (verificar límites reales):

| Familia | Historial nativo | Política de backtest |
|---|---|---|
| klines 1m/5m (OHLCV + quote_vol + trade_count + taker_buy) | Profundo (limit de páginas, sujeto a listing del símbolo) | Fuente primaria histórica |
| OI history (`openInterestHist`), basis (`basis`), long/short ratios (`*Ratio`) | ~últimos 30 días (según docs actuales) | Directo dentro del horizonte; excluir/proxy fuera |
| funding history | Serie de eventos (8h/4h según régimen) | Alinear último evento a grilla 5m y marcar método |
| Order book | Sin archivado = sin backtest | Live-forward únicamente |
| 1000PEPEUSDT et al. | Disponible desde su listing | La ventana de backtest queda limitada por listing del vehículo |

Feature tiers: `TIER_A_FULL_NATIVE` (30d con OI/ratios/taker directo) · `TIER_B_NATIVE_PLUS_PROXY` (taker proxy por klines, sin OI) · `TIER_C_PRICE_VOLUME_ONLY`. Todo reporte debe desglosar por tier.

---

## 7. Cambios propuestos (mínimo, por artefacto)

**Nuevos archivos**
- `src/desk/waterfall/` (paquete aislado):
  - `capture.py` — captura continua 1m/5m + derivados (idempotente, INSERT OR IGNORE por PK)
  - `features.py` — indicadores base + velocity/persistence/deceleration/failed-recovery/cross-asset
  - `scores.py` — cascade/pullback/exhaustion (config externa versionada)
  - `state.py` — máquina de estados + lifecycle de régimen/asset/leg + event-end
  - `leg.py` — generación de legs (re-arm, closed-5m) + kit de salida (SL 1×ATR14(5m), TP 1.5R, max_hold 60m, reclaim)
  - `resolver.py` — resolución determinista (TP/SL/TIME/RECLAIM/EVENT_END/AMBIGUOUS) sobre velas crudas guardadas
  - `performance.py` — agregación leg/event/símbolo/portfolio (reusa SQL-patrón LONG)
- `scripts/waterfall_backfill.py` — backfill paginado histórico + matriz de backtest persistida
- `scripts/waterfall_capture_once.py` — job del scheduler (~60s)
- `scripts/waterfall_engine_once.py` — features+scores+state+legs (~60s, vela cerrada)
- `scripts/waterfall_resolve_once.py` — resolver (~60s) y event-end
- `scripts/waterfall_performance_refresh.py` — agregados (~1h)
- `scripts/import_manual_trades_2026_08_30.py` — seed manuales + match legs
- `tests/test_waterfall_capture.py`, `test_waterfall_resolver.py`, `test_waterfall_state.py`, `test_waterfall_scores.py`

**Extensiones a existentes (mínimas)**
- `src/desk/market.py` + `types.py`: mapear `trade_count`, `taker_buy_base`, `taker_buy_quote` en `Candle`
- `src/desk/derivatives.py`: añadir taker/ratios y `is_proxy`/`freshness`
- `src/desk/db.py`: nuevas tablas via SCHEMA (no tocar las LONG)
- `config/settings.json`: sección `waterfall` con `config_version`, universo, thresholds y kit
- `scripts/run_scheduler_loop.py`: registrar los 5 jobs nuevos en `build_jobs()`
- `scripts/dashboard.py` + `generate_daily_report.py`: secciones waterfall
- `docs/ROADMAP.md`: enlistar hitos waterfall con gates

**Tablas nuevas (prefijo `waterfall_`)**
- `waterfall_config_versions`
- `waterfall_raw_klines` (symbol, interval, open_time PK, OHLCV, quote_vol, trades, taker_buy, source, ingested_at)
- `waterfall_derivatives_snapshots` (symbol, ts, funding, oi, mark, index, basis, taker, ratios, is_proxy, freshness)
- `waterfall_backfill_matrix` (feature, native_horizon, policy, tier, verified_at)
- `waterfall_regime_event` / `waterfall_asset_event` / `waterfall_leg` (core columns espejo LONG + event/fees/dual-R per §14.4)
- `waterfall_event_labels`, `waterfall_manual_trades` (UTC + local + tz_source + matched_leg_id)
- vistas `waterfall_*_performance`

**Regla de no-tocar:** el pipeline LONG, demo y scheduler actual no se modifican; los jobs waterfall se añaden como jobs nuevos. El ejecutor demo sigue filtrado por top-251 del LONG (sin acoplar).

---

## 8. Plan de Fase 1 (exacto), con gate

1. **Verificar timestamps manuales** contra export/API de Binance (hará falta confirmar la ventana exacta local→UTC; provisional America/Tijuana UTC−7). Persistir `ts_local/ts_utc/tz_source/timestamp_verified/source_reference`.
2. **Schema:** tablas `waterfall_*` + `config_versions` (`config_version="waterfall_v1"`), PKs y `INSERT OR IGNORE`.
3. **Captura continua:** extender `market.py`/`types.py`; `waterfall_capture_once` con grilla 1m+5m para el universo inicial (BTC, 1000PEPE, ENA, WLD, SUI, DOGE, TRUMP, HEMI, ETH, SOL) + derivados cada ~60s. `is_proxy`/`freshness`/`gaps` por fila.
4. **Backfill histórico:** `waterfall_backfill.py` paginado (1m/5m; alcance limitado por listing y por los 30d nativos de derivados) + persistir `waterfall_backfill_matrix` por familia y tier.
5. **Calidad/frescura:** tabla/job de gaps y stale por símbolo; bloqueo de estados fuertes si datos faltan (regla 11 spec).
6. **Tests:** idempotencia (velas duplicadas), normalización UTC, stale/missing, integridad de PK.
7. **Gate:** `timestamps verificados` + `captura continua demostrada en ~60s por 60+ min` + `matriz de backfill persists y reproducible`.

Fases siguientes (resumen): 2 screening de vehículos + features · 3 scores · 4 estado/eventos · 5 legs ilimitados · 6 kit + resolver · 7 alertas · 8 manuales + match · 9 replay · 10 performance · 11 backtest (naive vs filtered, walk-forward) · 12 calibración · 13 demo gate (fuera de alcance sin aprobación).

---

## 9. Riesgos / incertidumbres

- **Horizonte histórico real de `/futures/data/*`** y límites actuales de rate-limit Binance: se verificará en Fase 1; la matriz puede ajustar tier de los backtests.
- **1000PEPEUSDT y vehículos**: backtest limitado por fecha de listing (serverTime vs listing). PEPE (listing 2024-12) no es el problema; monedas nuevas son el problema.
- **Timestamps manuales**: sin confirmar exactamente la conversión (el doc asume America/Tijuana); riesgo de desfase ≤ horas en el match `matched_leg_id`.
- **universo de vehículos**: la elegibilidad (amplif≥2, corr≥0.5, RVOL≥5) usa definiciones que el LONG no tiene — se define como config `waterfall` inicial, no se toca el screening LONG.
- **Reuse del resolver-core**: refactorizar `resolve_shadow_trade` para `direction` param es opcional y con `ponytail`-costo; la v1 puede tener `waterfall_resolver.py` propio que copie el patrón STOP_FIRST/gaps sin tocar el LONG (difícil equivocarse con el LONG intacto).
- **Dashboard**: el HTML es un archivo estático grande; añadir panel waterfall sin romper el existente (sección extra + query nueva).

---

## 10. Checklist espec v5 (§19) — estatus Phase 0

| Punto | Estatus |
|---|---|
| 1 · Estrategia shadow definida (closed-5m SHORT, kit fijo, dual R) | Especificado; resolver/kit pendientes Fases 5-6 |
| 2 · Legs ilimitados + re-arm + event-end | Especificado; lifecycle pendiente Fase 4 |
| 3 · Universo multi-activo + elegibilidad + ranking | Pre-screening hecho (leaderboard): ENA/4/HEMI/1000PEPE/WLD/SUI/DOGE; la elegibilidad configurable en Fase 2, ranking real tras backtest |
| 4 · Matriz backfill + tiers | Borrador §6; materializa en Fase 1 |
| 5 · Timezone manuales + `matched_leg_id` | Regla Fase 1 |
| 6 · Modelo de resultados completo (WR/PF/expectancy/net R/DD, fees) | Especificado; tablas/agregación en Fases 6/10 |
| 7 · Validación estrategia (naive vs filtered) | Especificado; se ejecuta en Fase 11 |
| 8 · Paridad LONG + trazabilidad alerta→event→leg→resultado | Diseño §3/§7; se implementa en Fases 7/10 |

**Conclusión:** el módulo debe ir como paquete aislado `src/desk/waterfall/` que **comparte infraestructura** (scheduler, alertas, DB, dashboard, tests, config) y **espeja convenciones LONG**, pero con schema de eventos/legs propio. Es la opción de mínimo cambio con riesgo cero para el sistema LONG activo.
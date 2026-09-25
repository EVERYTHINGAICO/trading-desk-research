# Roadmap

## Phase 0 — Authority lock
- Keep the shared PDF as source of truth.
- Record every implementation gap against authority.

## Phase 1 — Shadow MVP
- Binance public market data via REST.
- Deterministic features: returns, volume spike, ATR, EMA.
- Simple state machine.
- Freeze plan + write SQLite, JSONL, Markdown.
- No real execution.

## Phase 2 — Trigger monitor
- Split broad screener and high-frequency monitor.
- Re-evaluate WATCH / PRE_ENTRY opportunities every 1-5 minutes.
- Detect MISSED / INVALIDATED / ENTRY_READY transitions.
- Current implementation now includes a scheduled trigger-monitor script and a scheduler loop scaffold; next step is stateful re-checking against existing open opportunities instead of stateless rescans.

## Phase 3 — Shadow resolver
- Determine whether entry triggered.
- Resolve stop / TP1 / TP2 / PRIMARY TP.
- Handle ambiguous bars with conservative STOP FIRST.
- Compute MFE / MAE and R-multiple.

## Phase 4 — Context and risk gates
- BTC regime filter.
- Structural event/news risk gate.
- Data quality grading A/B/C.
- Spread/liquidity filters.

## Phase 5 — Alerts and review
- Telegram / Discord alerts on material state changes only.
- Daily / weekly journal summaries.
- Expectancy and performance review by setup and session.

## Phase 6 — Semi-automatic desk
- Human approval required before any external execution module.

---

## Backlog — Planes pendientes de implementar (shadow primero)

### P1. Reporte gap-stress (expectancy doble columna: −1R vs MAE)
- **Problema detectado:** el resolver acredita cada pérdida en −1.0R plano, ignorando el gap intrabar. Simulación con datos: total 8d = +14,046R a −1R vs **+3,207R** si los stops se liquidan al MAE real (−77% del edge). Solo el 26-08: −200R vs **−3,510R**.
- **Objetivo:** reporte solo-lectura (`scripts/report_gap_stress.py`) que emita `data/reports/gap_stress_YYYYMMDD.md` con R, delta y slippage promedio por pérdida, por día, por btc_context, por setup, y por símbolo top-251 con su expectancy bajo estrés de gap.
- **No toca:** ranking, executor ni demo. Solo lee `shadow_trade_results`.
- **Criterio de salida:** decisión informada sobre el freno, con números.

### P2. Freno de crash (risk-off / pause)
- **Problema detectado:** no existe detector de crash. El único pause es por balance bajo. Contexto `hostile` solo resta 6 puntos de score; no bloquea.
- **Diseño propuesto:** umbral definido con datos (ej. BTC < −4% en <6h, o drawdown acumulado >Z) que corta `run_binance_demo_once` con estado tipo `BINANCE_PAUSED_FLASH` y suprime nuevas aperturas ENTRY_READY hasta que el contexto se recupera.
- **Método de decisión:** backtest del umbral contra el histórico (R salvada por evitar gaps vs R buena perdida por pausar) usando la columna MAE del P1.
- **Gate:** solo ejecutar si el P1 muestra delta grande en ventanas recientes. Autoridad: requiere aprobación humana explícita.

### P3. (Propuesta en evaluación) Alternativas de estrategia sobre datos shadow
- Exploración offline / solo-lectura de variantes (mirror-short, filtro de horas, score bands) usando el histórico shadow.
- Restricción dura: nada de esto alimenta el ranking ni el executor sin aprobación.
- Riesgo señalado: muestras cortas (≈8 días de datos cerrados) → alto riesgo de overfitting; validar por ventana y con mínimo de trades.

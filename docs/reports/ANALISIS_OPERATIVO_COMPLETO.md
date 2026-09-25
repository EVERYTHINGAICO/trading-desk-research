# Analisis operativo completo

## Fecha y alcance

Este informe describe el funcionamiento real del repositorio `trading-desk-shadow` y lo contrasta con `docs/Trading_Desk_Clone_Specification_V2_2026-08-23.pdf`.

Se revisaron scanner, indicadores, contexto BTC, riesgo, estados, resolver, scheduler, ejecucion Binance Demo, reconciliacion, proteccion manual, dashboard, alertas, AI y busqueda web. No se cambiaron reglas ni parametros como parte del informe.

## Resumen ejecutivo

El sistema actual tiene tres capas:

1. **Desk shadow determinista:** analiza mercado, calcula indicadores, clasifica setups, genera niveles y guarda un plan congelado.
2. **Ejecucion opcional Binance Futures Demo:** envia entradas long LIMIT y protecciones nativas cuando las variables de entorno estan habilitadas.
3. **Operacion y observabilidad:** scheduler, reconciliacion, monitor de protecciones, base SQLite, eventos, journals, dashboard y Telegram.

La decision numerica no la toma el modelo de lenguaje. La toma codigo Python con reglas y formulas reproducibles. El contexto BTC, derivados y risk gate se incorporan como datos estructurados. El AI tiene contrato y fallback seguro, pero el scanner Python actual no llama automaticamente a un proveedor LLM ni a web search; cuando no estan conectados registra `N/A` y una recomendacion conservadora.

## 1. Arquitectura real

```text
Binance Futures REST
        |
        v
Velas cerradas 15m + BTC 15m/1h/4h/1d
        |
        v
Calidad de datos + indicadores + derivados + risk gate
        |
        v
Scanner de setups + score determinista
        |
        v
PASS / WATCH / PRE_ENTRY / ENTRY_READY
        |
        v
Plan congelado: entry, invalidacion, stop, TP1, TP2, PRIMARY TP, R:R
        |
        +--> SQLite + JSONL + journal Markdown + alert dedupe
        |
        +--> Executor Demo opcional
        |       entrada LIMIT -> fill -> SL/TP nativos
        |
        +--> Reconciliador y watcher de proteccion
```

El scheduler local ejecuta ocho trabajos: scanner amplio, trigger monitor, monitor estatal, resolver shadow, executor Demo, monitor Demo, reconciliador y watcher manual.

Referencias principales:

- `scripts/run_scheduler_loop.py:30-73`
- `config/settings.json:1-54`
- `docker-compose.yml:1-28`

## 2. Datos que utiliza

### Mercado

`src/desk/market.py` consulta Binance Futures USD-M mediante REST. Con `symbols: ["*"]` descubre perpetuos USDT en estado `TRADING`, filtra por volumen minimo de aproximadamente 1,000,000 USDT y devuelve el universo ordenado.

El intervalo principal es `15m` y se solicitan 120 velas. La vela aun abierta se descarta usando `close_time`, por lo que el scanner trabaja con velas cerradas.

### Contexto BTC

`src/desk/context.py` descarga BTC en 15m, 1h, 4h y 1d. Para cada marco calcula EMA20 y clasifica:

- debajo de EMA20 por al menos 0.5%: `hostile`;
- encima de EMA20: `supportive`;
- entre ambos: `neutral`.

El contexto global es `hostile` con al menos dos marcos hostiles y `supportive` con al menos tres favorables. Si no hay datos queda `N/A`.

### Derivados

`src/desk/derivatives.py` obtiene puntualmente:

- funding rate;
- mark price;
- index price;
- basis o premium relativo;
- open interest.

No obtiene aun de forma completa delta de OI historico, liquidaciones, taker buy/sell, order book, spread, ratios long/short o cadena de opciones.

## 3. Matematicas e indicadores

El sistema es principalmente matematico y determinista. Los mismos datos producen los mismos resultados.

### EMA

```text
k = 2 / (periodo + 1)
EMA_t = precio_t * k + EMA_(t-1) * (1-k)
```

Se calculan EMA7, EMA25 y EMA99. El scanner tambien usa EMA20 para algunas decisiones.

### Bollinger

```text
middle = media de 21 cierres
upper = middle + 2 * desviacion estandar
lower = middle - 2 * desviacion estandar
bandwidth = (upper - lower) / middle
```

### MACD

```text
DIF = EMA12 - EMA26
DEA = EMA9(DIF)
histogram = DIF - DEA
```

### RSI

Usa la media de ganancias y perdidas recientes para RSI6, RSI12 y RSI24. Es una implementacion simple, no el suavizado Wilder completo.

### VWAP

```text
precio_tipico = (high + low + close) / 3
VWAP = suma(precio_tipico * volumen) / suma(volumen)
```

### ATR

```text
TR = max(high-low, abs(high-cierre_anterior), abs(low-cierre_anterior))
ATR14 = media de los ultimos 14 TR
```

El ATR actual usa media simple.

Referencias:

- `src/desk/indicators.py`
- `src/desk/scanner.py:28-43`

## 4. Calidad de datos y riesgo

La calidad revisa cantidad de velas, volumen, intervalos irregulares, velas invalidas y volumen cero. Clasifica A, B o C y penaliza el score.

El risk gate calcula:

```text
range_vs_atr = (high-low) / ATR
abs_candle_change_pct = abs((close / close_anterior - 1) * 100)
quote_volume_multiple = volumen_actual / media_volumen_20
```

Bloquea por flag manual o cuando al menos dos senales estructurales superan limites. El archivo manual activo puede no existir; en ese caso se registra `N/A:no_manual_risk_file`.

Esto significa que el sistema detecta anomalías de precio/volumen, pero no conoce automaticamente la causa externa de un shock, como hack, unlock, delisting, regulacion o earnings, porque el pipeline web/news no esta conectado directamente al scanner.

## 5. Estrategia efectiva

El scanner actual busca principalmente estructuras alcistas de capitulacion, reclaim y continuacion. Tiene seis familias:

1. `capitulation_flush_reclaim`
2. `capitulation_probe`
3. `failed_breakdown_reclaim_watch`
4. `breakout_retest_hold_watch`
5. `trend_pullback_reclaim_watch`
6. `dislocated_bounce_watch`

Estas familias son setups analiticos, no seis estrategias independientes completas. La logica esta concentrada en `classify_setup()` y no en modulos separados.

El patron general es:

```text
caida o dislocacion
-> volumen/rebote
-> reclaim o retest
-> confirmacion estructural
-> entrada candidata
```

La ruta de ejecucion actual solo implementa longs:

```text
entrada = BUY LIMIT
protecciones = SELL STOP_MARKET + SELL TAKE_PROFIT_MARKET
```

El PDF define tambien LONG, SHORT y NONE, con formulas inversas para short, pero el repositorio actual no tiene `direction` en `Opportunity` ni `TradePlan`, ni `submit_short_limit()`. Por tanto, la metodologia documentada es multi-direccion, pero la ejecucion Demo vigente es long-only.

## 6. Score y estados

El score parte de 50 y suma o resta por reglas como:

- caida suficiente: +18;
- volumen spike: +16;
- debajo de EMA20: +8;
- sobre EMA99: +4;
- rebote suficiente: +14;
- calidad A: +8;
- calidad B: +2;
- BTC supportive: +6;
- BTC hostile: -6.

La maquina base usa:

```text
calidad insuficiente -> PASS
score >= 85 y rebote -> ENTRY_READY
score >= 75 -> PRE_ENTRY
score >= 60 -> WATCH
resto -> PASS
```

Luego el scanner aplica un limite especifico por setup y el risk gate puede devolver `PASS`. Tambien existe una regla `MISSED - DO NOT CHASE` cuando el precio se aleja o el R:R restante se deteriora.

Importante: `ENTRY_READY` es una oportunidad lista para replicar, no confirma que se haya enviado una orden.

Referencias:

- `src/desk/state_machine.py:4-13`
- `src/desk/scanner.py:611-734`
- `src/desk/monitor.py:134-175`

## 7. Planes y journal

Cada plan guarda entry, invalidacion, stop, TP1, TP2, PRIMARY TP, R:R y tipo de trigger.

La tabla `trade_plans` tiene triggers SQLite que bloquean update y delete. Esto conserva los niveles originales y evita hindsight.

El resolver shadow determina posteriormente:

- `MISSED`;
- `OPEN`;
- `STOPPED`;
- `WON`;
- avance TP1/TP2/PRIMARY.

Aplica `STOP FIRST` si una vela ambigua puede haber tocado stop y objetivo. El fill shadow usa el precio congelado y no simula slippage, comisiones ni ejecuciones parciales reales.

## 8. Uso de AI y contexto externo

### Lo que define el PDF

El PDF exige que el desk use un orquestador para interpretar contexto, noticias, macro y contradicciones, sin sustituir calculos numericos ni persistencia. Pide tambien web search, fuentes primarias, timestamps, freshness y hard gate antes de `ENTRY_READY`.

### Lo que hace el repositorio

`src/desk/ai_review.py` construye un paquete estructurado con:

- estado;
- setup;
- score;
- calidad;
- BTC;
- riesgo;
- diagnosticos;
- plan;
- derivados.

Tambien impone que el AI no invente datos, no cambie niveles y no autorice trading real.

Pero el scanner y el trigger monitor actualmente asignan directamente `unavailable_review()`. No llaman desde Python a OpenAI, ChatGPT, web search o web fetch. El resultado queda como:

```text
status = N/A
shadow_recommendation = NO_TRADE_UNTIL_AI_REVIEW_AVAILABLE
confidence = 0.0
```

OpenClaw si tiene capacidad general de modelos, subagentes, Telegram y web tools, pero la integracion automatica con el scanner trading no esta implementada como una llamada local verificable.

## 9. Ejecucion Binance Demo

El executor separado se habilita solo si son verdaderas:

```text
BINANCE_DEMO_TRADING_ENABLED
BINANCE_DEMO_ALLOW_ORDERS
```

Usa endpoint Demo, firma HMAC-SHA256 y notional configurado de 50 USDT con margen `ISOLATED` y leverage 1x.

Flujo:

```text
ENTRY_READY
-> crear intent CREATED
-> preflight
-> BUY LIMIT GTC
-> guardar orderId
-> esperar fill hasta 30 s
-> si NEW: conservar SUBMITTED
-> si FILLED: leer posicion
-> crear STOP_MARKET y TAKE_PROFIT_MARKET nativos
-> confirmar ambos
-> PROTECTED
```

La proteccion nativa usa `closePosition=true`, por lo que en One-way protege la posicion agregada del simbolo. TP1 y TP2 quedan como niveles del plan; el TP nativo es PRIMARY TP.

## 10. Reconciliacion y watcher manual

El reconciliador corre cada 15 segundos. Lee posiciones, ordenes abiertas y algos, actualiza snapshots y puede cancelar una LIMIT si el setup esta `INVALIDATED`, `MISSED` o `CLOSED_WIN`.

Si una entrada filled no tiene proteccion completa, intenta crear solo los algos faltantes y deja `PROTECTION_REQUIRED` si falla.

El watcher manual tambien corre cada 15 segundos. Solo debe actuar cuando falta proteccion nativa y el mark price ya cruza stop o PRIMARY TP. Para long usa SELL MARKET; para short usa BUY MARKET. Usa `reduceOnly=true`, confirma la posicion y registra el evento en SQLite.

El watcher es automatico, aunque su nombre contenga “manual”. No es una proteccion paralela para operaciones correctamente protegidas.

## 11. Persistencia y observabilidad

SQLite concentra oportunidades, planes, transiciones, intents, exchange orders, fills, snapshots, protecciones, errores, bloqueos, reconciliaciones, eventos del watcher y entregas Telegram.

Tambien existen JSONL y Markdown para eventos/journals historicos. El dashboard es de lectura y muestra actualmente resumen shadow, actividad, Binance principalmente en BTCUSDT, intents, errores, oportunidades y eventos.

El principal problema de claridad del dashboard es que mezcla estados tecnicos y no muestra de forma prioritaria:

- esperando fill;
- filled protegido;
- filled sin proteccion;
- capacidad de stop agotada;
- margen libre;
- vista multi-activo completa.

## 12. Comparacion con el PDF

### Implementado

- pipeline deterministicamente reproducible;
- velas cerradas;
- contexto BTC;
- indicadores OHLCV;
- calidad de datos;
- risk gate estructural/manual;
- setups deterministas;
- estados y no-chase;
- planes congelados;
- journal y resolver;
- scheduler;
- dashboard;
- derivados basicos;
- ejecucion Demo separada;
- reconciliacion;
- proteccion nativa;
- fallback manual de proteccion.

### Parcial

- setups especificos del PDF;
- derivados avanzados;
- trigger event-driven;
- news gate;
- AI review;
- dashboard multi-activo;
- metricas por estrategia y direccion;
- fills y parciales;
- versionado operativo.

### Ausente

- direction LONG/SHORT/NONE en el modelo central;
- ejecucion short;
- cliente LLM conectado al scanner;
- web search automatico del scanner;
- feed de noticias/macro/eventos conectado al risk gate;
- WebSocket continuo;
- order book y spread integrados;
- liquidaciones y flujo taker;
- backtest/replay completo reutilizando exactamente el live pipeline.

## Veredicto

El bot no es una caja negra: su decision principal es una cadena determinista de datos, formulas, condiciones y estados que queda persistida. El AI, cuando esta conectado externamente, esta pensado como interprete de contexto y no como autoridad numerica; en la implementacion actual local, esa conexion automatica no esta activa. Binance Demo es una capa separada y opcional que si puede enviar ordenes cuando se habilita explicitamente.

La descripcion exacta del sistema es:

> Desk shadow determinista con ejecucion opcional en Binance Futures Demo, reconciliacion, proteccion nativa y watcher de respaldo; el analisis AI/web esta documentado y parcialmente preparado, pero aun no esta conectado de forma automatica al scanner Python.

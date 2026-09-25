# WATERFALL SHADOW PROJECT — BIG PICKLE MASTER DOCUMENT

**Purpose:** Single-file handoff for integrating the complete Waterfall / Liquidation Cascade project into the EXISTING Shadow Trading System.

**Instruction:** This file is the master project specification. Big Pickle must inspect the repository first, map these requirements to what already exists, create a phased implementation plan, and only then implement after approval.

**Absolute constraints:** SHADOW MODE ONLY. No real trades. No demo orders in this initial module. No trading permissions. No parallel replacement of existing Shadow infrastructure. Exhaustion is not a long signal.

---

# AGENTS.md

## Project intent
This repository already contains a SHADOW trading system. Do not rebuild it from scratch.

Your task is to integrate a new experimental module for detecting bearish waterfall / liquidation-cascade regimes in Binance Futures, with BTCUSDT as the market-regime reference and 1000PEPEUSDT as the initial high-beta trade vehicle.

## Non-negotiable rules
1. SHADOW MODE ONLY.
2. Do not place real trades.
3. Do not add auto-entry or auto-execution.
4. Do not request or require Binance trading permissions for this module.
5. Inspect the existing repo, DB, collectors, scheduler, alerts, dashboard, config and backtest framework before changing code.
6. Reuse existing services when practical; do not create parallel architecture unnecessarily.
7. Store raw market data separately from derived features.
8. No lookahead bias.
9. Closed-candle features and intrabar/pre-alert features must be distinguished.
10. All decisions must be auditable with reason_codes and config_version.
11. Missing or stale BTC/OI/taker data must reduce confidence or block strong states; never invent values.
12. Exhaustion is NOT a long signal.
13. Supertrend must never be the sole entry or exit condition.
14. Thresholds in this spec are initial hypotheses only; never optimize on one day.
15. Live/shadow and backtest must use the same feature/state logic.
16. The Waterfall module must include a complete SHADOW STRATEGY model, not only a detector: canonical closed-5m SHORT signal, fixed/versioned exit kit, deterministic resolver, R metrics and per-symbol performance.
17. Reuse the existing LONG opportunities/resolver/performance conventions and core columns wherever they already exist. Prefer a strategy discriminator/view over parallel infrastructure.
18. Every alert must be traceable to a signal candidate or existing signal via `alert_id`/`signal_id`.
19. Vehicle eligibility and performance are multi-asset. BTC is the global regime reference; trade vehicles are screened/ranked independently.
20. A Waterfall event may generate **as many distinct legs as valid continuation conditions persist**. Do not impose an arbitrary 2/3-leg cap.
21. A new leg requires a new validated continuation/re-arm condition; do not open one leg on every candle.
22. When the event reaches confirmed `EXHAUSTION` / `NO_NEW_SHORTS` / terminal `COOLDOWN`, stop generating legs and force-resolve/close every still-open shadow leg using the canonical event-end price rule.
23. Each leg has exactly **one TP** in v1. Fees and net-R must be measured per leg and per event.

## Required workflow
Before coding:
- Read `docs/WATERFALL_SHADOW_SPEC.md`
- Read `docs/WATERFALL_IMPLEMENTATION_PLAN.md`
- Read `docs/HANDOFF_BIG_PICKLE.md`
- Inspect the current project architecture.
- Report where this module should integrate with the fewest changes.

Then implement one phase at a time and stop at the requested gate.

## Required tests
- indicator calculations
- timestamp/timezone correctness
- stale/missing data
- idempotency / duplicate candle handling
- state transitions and hysteresis
- PAUSE -> SECOND_LEG
- EXHAUSTION_TRUE / EXHAUSTION_FALSE
- no-lookahead
- config-version reproducibility

## Safety gate
Do not move from shadow to paper/demo/live execution unless explicitly requested in a later project phase.


---

# Waterfall Shadow Module — Technical Specification v5 — Event + Unlimited Legs Strategy

## 1. Purpose

Add a specialized module to the EXISTING Shadow System that separates **detection** from **strategy resolution**.

The module must answer four different questions:

1. **Regime / Waterfall Engine**  
   Is the market in an exceptional bearish cascade?

2. **Pullback Quality Engine**  
   If a waterfall exists, is the current location structurally compatible with continuation, or is price too extended / being chased?

3. **Exhaustion Engine**  
   Is the cascade still clean, or has downside expansion deteriorated enough that new shorts should stop being considered?

4. **Shadow Signal & Performance Model**  
   When does a detected regime become a canonical shadow SHORT signal, how is that signal resolved with a fixed/versioned risk kit, and how are WON/STOPPED, R, WR, expectancy, PF, net R and drawdown reported by vehicle and globally?

The system does **not** execute orders. It does, however, create deterministic shadow strategy signals and resolves them exactly the same way in historical replay and live Shadow operation.

The module therefore must support the full chain:

```text
market data
-> regime detection
-> vehicle eligibility
-> signal candidate
-> tradeable shadow signal
-> fixed exit kit
-> deterministic resolution
-> R / MFE / MAE
-> per-symbol and portfolio performance
-> alert/result traceability
```

Detector metrics and strategy metrics are both required.

---

## 2. Empirical context

During a strong 1000PEPEUSDT selloff on 2026-08-30, the user manually identified a period where:
- bearish impulses persisted,
- pullbacks were weak,
- lower highs/lower lows continued,
- several manual shorts were profitable.

Later, the user noticed that the selloff stopped behaving like a waterfall:
- new lows stopped expanding cleanly,
- green/recovery candles appeared,
- buyer aggression improved,
- the cascade was no longer worth chasing even though slow trend indicators could remain bearish.

Binance review of the event showed BTC falling at the same time, consistent with a coordinated deleveraging / liquidation-cascade regime rather than a PEPE-only event.

Observed working hypotheses from the event:
- PEPE main impulse: approximately -5.95%
- BTC main impulse: approximately -1.73%
- PEPE 5m peak volume roughly 6.7x prior average
- BTC 5m peak volume roughly 10.2x prior average
- PEPE OI flush roughly 3% during the cascade
- taker flow later flipped toward buyers
- OI later stabilized/recovered
- 5m Supertrend remained bearish after the clean waterfall phase had already degraded

These values are examples, not final thresholds.

---

## 3. State machine

Suggested state flow:

NORMAL
-> DISTRIBUTION_REVERSAL
-> PREALERT
-> CASCADE_ARMED
-> WATERFALL_ACTIVE
-> PAUSE_POSSIBLE_SECOND_LEG
-> EXHAUSTION
-> COOLDOWN
-> NORMAL

Transitions may skip intermediate states when evidence is very strong, but all transitions must be logged.

### PAUSE is important
A green candle is not enough to declare exhaustion.

The system must be able to go:
WATERFALL_ACTIVE -> PAUSE_POSSIBLE_SECOND_LEG -> WATERFALL_ACTIVE

without forcing a trip through NORMAL.

### EXHAUSTION is not reversal
Exhaustion only means:
- `NO_NEW_SHORTS`
- `COOLDOWN`
- `WATERFALL_DEGRADED`

It must never automatically mean LONG.

If long/reversal detection is ever added, it belongs in a separate future `REVERSAL_CONFIRMATION` engine.

---

## 4. Markets, regime reference, vehicle universe and timeframes

### 4.1 Global regime reference

The **global regime symbol is BTCUSDT only**.

BTC determines whether the broader market environment is compatible with a systemic bearish cascade.

Do not average several assets into the global regime in v1.

### 4.2 Initial vehicle universe

The initial observation/signal universe should be explicit and configurable:

- `BTCUSDT`
- `1000PEPEUSDT`
- `ENAUSDT`
- `WLDUSDT`
- `SUIUSDT`
- `DOGEUSDT`
- `TRUMPUSDT`
- `HEMIUSDT`
- `ETHUSDT`
- `SOLUSDT`

At startup, resolve the actual Binance USDⓈ-M symbol and contract availability. If a configured symbol does not exist or is not active, mark it unavailable rather than silently substituting another instrument.

The architecture must allow the universe to grow without rewriting the engines.

### 4.3 Vehicle eligibility screening

A vehicle may be continuously recorded and scored yet remain **ineligible to emit tradeable shadow signals**.

For non-BTC vehicles, initial screening hypotheses are:

- amplification vs BTC `>= 2.0x`
- rolling BTC correlation `>= 0.50`
- event RVOL `>= 5.0x`

These are fixed research defaults for v1, not optimized thresholds.

If the existing Shadow System already has a screening engine and definitions for amplification/correlation/RVOL, reuse those exact definitions. Otherwise use documented, versioned formulas and never change them silently.

Suggested fallback definitions if no existing convention exists:

```text
amplification =
abs(vehicle_return_window) /
max(abs(btc_return_same_window), configured_btc_return_floor)

corr_btc =
rolling Pearson correlation of closed 5m returns over configured window

rvol =
current closed-5m volume /
baseline volume statistic over prior closed 5m candles
```

All formulas/window lengths must live in config and be stored with `config_version`.

BTC is a special case if it is also evaluated as a vehicle: amplification-to-itself is mathematically 1.0 and therefore cannot use the non-BTC `>=2.0x` rule. Either treat BTC as benchmark-only or define a separate explicit BTC-vehicle eligibility rule.

Assets that fail eligibility:

- remain in raw data,
- remain in research features,
- remain in screening reports,
- **do not create tradeable waterfall signals**.

### 4.4 Ranking objective

Maintain performance by vehicle so the system can answer:

> Which assets actually convert the BTC waterfall regime into the best shadow SHORT expectancy?

Rank vehicles using out-of-sample strategy metrics, not only detector scores.

### 4.5 Timeframes

- 1m: structure, detailed resolver sequencing, pullback quality, early exhaustion
- 5m: primary regime and **canonical signal trigger timeframe**
- 15m: context
- 1h: optional context only; should not independently block a valid 1m/5m event

Canonical shadow strategy signals must be generated only from **closed 5m candles** in v1.

Store UTC internally. Convert to user timezone only at presentation layer.

---

## 5. Continuous data capture and historical backfill matrix

Do not store only alert windows.

Capture continuously so true events can be compared to normal periods and so the strategy resolver is reproducible.

At minimum:
- OHLCV
- quote volume
- trade count
- taker buy volume
- mark price
- index price
- premium/basis
- open interest
- funding
- taker buy/sell ratio
- account long/short ratio
- top-trader account/position ratios

Optional/secondary:
- order-book spread
- bid/ask depth by distance bands
- order-book imbalance

Order book must never be a sole trigger because of spoofing/cancellation risk.

Track:
- data source
- source timestamp
- ingestion timestamp
- freshness
- gaps
- latency
- retry/error status
- `is_proxy`
- `proxy_method`
- `backfill_quality`

### 5.1 Historical backfill matrix — mandatory

Phase 1 must create and persist a machine-readable backfill matrix for every feature family.

Do not assume all features have equal historical depth.

Current Binance public API behavior must be verified at implementation time because exchange limits can change. As of the specification review on 2026-08-30, Binance's official Futures docs state that the `/futures/data/*` statistical series such as basis and long/short statistics expose only the **latest 30 days**; treat open-interest history and global/top-trader ratios as ~30-day-native unless the repository has already archived more. Funding is event history rather than a native 5m feature and should be aligned/forward-filled to the 5m grid when used. Historical klines contain taker-buy volume and can provide a clearly labeled order-flow proxy outside the direct statistical-series horizon.

The matrix must contain at least:

| Feature/source | Native historical status | Backtest policy |
|---|---|---|
| Futures OHLCV / quote volume / trade count / taker-buy volume | Deep paginated kline history subject to symbol/listing availability | Primary historical source |
| Direct taker buy/sell ratio statistical endpoint | Limited statistical-history horizon; verify exact current limit | Use direct data where available |
| Kline taker-flow proxy | Derivable wherever futures klines exist | `taker_buy = kline taker buy`; `taker_sell = total - taker_buy`; mark `is_proxy=true` |
| Open-interest history | Recent-history endpoint; initial expectation ~30d | Direct within horizon; older periods excluded or sourced from repository/archive/vendor, never fabricated |
| Global long/short ratio | Recent-history endpoint; initial expectation ~30d | Same |
| Top-trader account/position ratios | Recent-history endpoint; initial expectation ~30d | Same |
| Basis/premium statistical history | Official docs currently state latest 30d | Direct within horizon |
| Funding rate history | Event-based history; cadence can vary by symbol/regime | Align last-known event value to 5m feature grid and mark alignment method |
| Order book | No trustworthy deep historical replay unless already archived | Live-forward only unless repository has real snapshots |

### 5.2 Backtest feature tiers

Every historical run must declare its feature tier:

```text
TIER_A_FULL_NATIVE
TIER_B_NATIVE_PLUS_PROXY
TIER_C_PRICE_VOLUME_ONLY
```

Example:

- recent 30d with OI/ratios/direct taker = `TIER_A_FULL_NATIVE`
- older period using kline taker proxy and no historical OI = `TIER_B_NATIVE_PLUS_PROXY`
- old periods with only candles = `TIER_C_PRICE_VOLUME_ONLY`

Never compare tiers as if they contain identical information.

Reports must show performance and detector metrics by `feature_tier`.

### 5.3 Reproducibility rule

If a feature was unavailable historically:

- exclude it,
- use an explicitly documented proxy,
- or run a degraded configuration version.

Never backfill a missing derivatives feature with future/live values.

---

## 6. Base indicators/features

### Trend
- EMA 5/9/20/50/100/200
- SMA 20/50/200
- Supertrend 7,3
- Supertrend 10,3
- VWAP
- EMA slope
- EMA separation
- distance from EMA9 / EMA20 / VWAP

### Momentum
- RSI 7/14/21
- MACD 12/26/9
- MACD histogram slope
- ROC
- Stoch RSI
- Williams %R
- CCI

### Trend strength
- ADX14
- +DI
- -DI
- DI spread / ratio
- ADX slope

### Volatility
- ATR7
- ATR14
- ATR%
- Bollinger 20,2
- Bollinger bandwidth
- Keltner
- squeeze state
- candle range / ATR
- body / ATR
- wick/body

### Volume/flow
- RVOL
- volume z-score
- trade-count z-score
- taker buy/sell ratio
- approximate delta
- cumulative delta

### Derivatives
- OI
- delta OI 5/10/15/30m
- price x OI relationship
- funding
- premium/basis
- long/short crowding

### Structure
- lower-high counter
- lower-low counter
- new-low expansion
- support break
- distance from daily high/low
- returns 1/5/15/30/60m

Do not assume every calculated indicator belongs in the live score. Keep broad features for research, then use ablation/out-of-sample testing to remove redundancy.

---

## 7. New required features

### 7.1 Waterfall Velocity
Measure the speed of downside movement:
- percent per minute
- ATR units per minute
- 3m/5m/10m displacement
- price slope
- acceleration
- deceleration
- BTC velocity vs PEPE velocity

### 7.2 Persistence Score
Measure whether bearish continuation is persistent rather than just one candle:
- fraction of bearish candles
- closes near candle lows
- consecutive LH/LL
- time between new lows
- average pullback depth
- pullback duration
- percentage of prior impulse recovered

### 7.3 Pullback Quality
Only calculate when regime is ARMED/ACTIVE.

Useful signals:
- sufficiently large prior impulse relative to ATR
- retracement is limited, not a full reversal
- rebound volume < sell impulse volume
- taker buying is weak/fading
- rejection at EMA9/EMA20/VWAP/broken support
- lower high
- seller aggression resumes
- BTC does not strongly recover
- penalize if Exhaustion Score is already high

### 7.4 Waterfall Deceleration
Measure whether each bearish impulse is becoming weaker:
- reduced displacement per leg
- reduced new-low expansion
- falling seller delta magnitude
- MACD histogram becoming less negative
- falling ATR-normalized downside velocity
- increasing time required to create a new low

### 7.5 Failed Recovery Score
Pattern:
drop -> rebound -> failure to reclaim VWAP/EMA20/broken level -> lower high -> sellers return

### 7.6 Cross-asset features
- rolling BTC/PEPE correlation
- rolling beta
- PEPE excess return = PEPE return - beta * BTC return
- BTC regime confidence

---

## 8. Cascade Score v1

Treat these as configurable hypotheses, not truth.

Approximate initial components:
- 15 BTC bearish regime
- 15 PEPE bearish trend
- 15 PEPE seller aggression
- 10 BTC seller confirmation
- 10 abnormal volume/expansion
- 10 PEPE OI flush
- 10 ADX / -DI trend strength
- 10 bearish structure / failed recovery
- 5 acceleration / high-beta response

Initial candidate conditions:
- PEPE taker ratio < 0.80 prealert, < 0.70 strong
- BTC taker ratio < 0.85 prealert, < 0.75 strong
- PEPE ADX > 25; strong > 30 and rising
- PEPE OI drop >= 1.5% over ~10m is strong evidence
- volume > 1.5x normal prealert; >2-3x strong
- price < EMA9 < EMA20 and below VWAP in both assets as regime confirmation

Important:
`WATERFALL_ACTIVE` cannot be triggered merely because many correlated price indicators sum to a high score.

Require evidence from independent categories:
- regime
- order flow
- expansion/volatility
- structure
- derivatives when available

Use hysteresis/persistence to reduce state flicker.

---

## 9. Pullback Quality Score

A high score should mean:
- regime remains active
- price is not excessively extended
- rebound is weak
- buyers fail to reclaim key levels
- seller aggression is returning
- BTC remains supportive of downside
- Exhaustion remains low/moderate

A low score in an active waterfall should communicate:
`ACTIVE WATERFALL, BUT DO NOT CHASE`

This is separate from whether the regime itself is bearish.

---

## 10. Exhaustion Score

Do not wait for 5m Supertrend to turn green.

Evidence:
- new lows stop expanding
- downside velocity declines
- PEPE and BTC taker ratios flip/persist >1
- OI stops falling / rebounds after flush
- MACD histogram becomes less negative
- 1m higher low / higher high
- reclaim of EMA9/local broken level
- lower wicks / absorption
- extreme RSI with inability to extend lower

One green candle alone is insufficient.

If evidence is partial:
`PAUSE_POSSIBLE_SECOND_LEG`

If evidence is strong:
`EXHAUSTION / NO_NEW_SHORTS`

Again: exhaustion never directly generates LONG.

---


## 11. Shadow Event, Multi-Leg Signal & Performance Model — REQUIRED

This is the strategy layer that converts the detector into measurable Shadow performance.

The key model is:

```text
GLOBAL BTC REGIME EVENT
        |
        +-- VEHICLE EVENT: PEPE
        |      +-- LEG 1
        |      +-- LEG 2
        |      +-- LEG 3
        |      +-- ...
        |
        +-- VEHICLE EVENT: SUI
        |      +-- LEG 1
        |      +-- ...
        |
        +-- VEHICLE EVENT: ENA
               +-- ...
```

There is **no fixed maximum number of legs per vehicle event**.

A strong rare waterfall may produce many validated continuation legs.

A smaller event may produce only one or two.

The number of legs is determined by the persistence of the detected conditions, not by a hard-coded quota.

### 11.1 Three-level identity model

Use three linked IDs where practical:

#### `regime_event_id`

Global BTC-driven cascade context.

Created when the BTC/global regime enters the configured event-tracking state such as PREALERT/ARMED.

#### `asset_event_id`

Per-vehicle Waterfall event while the global BTC regime remains relevant and that vehicle is eligible/active.

Examples:

```text
regime_event_id = BTC_20260830_1540
asset_event_id  = PEPE_20260830_1549
```

#### `leg_id`

One independent Shadow SHORT opportunity inside an `asset_event_id`.

Every leg has its own:

- trigger,
- entry,
- SL,
- TP,
- risk,
- fees,
- R,
- MFE,
- MAE,
- resolver outcome.

### 11.2 When a vehicle event becomes tradeable

A vehicle event may be tracked before any leg exists.

A vehicle can generate legs only when:

```text
global BTC regime is valid
AND vehicle is eligible
AND vehicle state is WATERFALL_ACTIVE
AND Exhaustion does not block new shorts
AND data quality is acceptable
```

A `PAUSE_POSSIBLE_SECOND_LEG` state does **not** automatically terminate the event.

During PAUSE:

- keep the event open,
- do not generate a new leg merely because time passed,
- wait for either renewed valid downside continuation or confirmed exhaustion.

### 11.3 Leg generation — unlimited count, but distinct re-arm required

A new leg may be created whenever the event remains alive and a **new distinct continuation setup** is confirmed on a fully closed 5m candle.

Canonical v1 requirements:

```text
state = WATERFALL_ACTIVE
vehicle_eligible = true
exhaustion_block = false
pullback_quality passes configured threshold
new_continuation_cycle = true
trigger candle = CLOSED 5m
SIDE = SHORT
ENTRY = trigger 5m close
```

`new_continuation_cycle=true` must require a real reset/re-arm condition.

Examples:

- a pullback followed by failed recovery,
- a new lower high,
- rejection of EMA9/EMA20/VWAP/broken support,
- seller aggression returning after the pullback,
- PAUSE -> SECOND_LEG / ACTIVE transition,
- another explicitly versioned continuation pattern.

Do **not** create a new leg on every bearish 5m candle.

Do **not** impose `max_legs=3` or another arbitrary event-wide cap.

### 11.4 Leg sequencing and concurrency

The total number of legs across an event is unlimited while conditions persist.

Concurrency must be configurable because the existing Shadow/LONG risk engine may already define exposure rules.

Preferred v1 baseline:

```text
allow_unlimited_leg_count_over_event = true
max_concurrent_open_legs_per_asset_event = 1
```

This means:

- close/resolve one leg,
- wait for another distinct valid continuation setup,
- create another leg,
- repeat for as long as the Waterfall event remains valid.

This closely mirrors the observed manual behavior and reduces simultaneous risk.

However, the data model and resolver must support `max_concurrent_open_legs > 1` later without redesign.

If concurrency is increased in a later config, the event-end rule below must close **all** open legs.

### 11.5 One TP per leg

Remove single-TP splitting from the initial canonical strategy.

Every leg has exactly:

```text
one entry
one stop
one target
one max-hold
one reclaim rule
```

Initial fixed/versioned v1 baseline:

```text
ATR source = ATR14 on closed 5m candles

stop_distance = 1.0 * ATR14
SL = entry + stop_distance   # SHORT

R = stop_distance

TP = entry - 1.5R

max_hold = 60 minutes

reclaim_exit =
configured deterministic closed-5m reclaim rule
```

The `1.5R` target is a baseline, not a claim that it is optimal.

The implementing agent must reuse the existing LONG risk-kit/resolver abstraction if present.

### 11.6 Event-end override — mandatory

The Waterfall detector controls whether the strategy is still allowed to keep pursuing new legs.

When the vehicle event reaches a **confirmed terminal end condition**:

```text
EXHAUSTION
or
NO_NEW_SHORTS
or
terminal COOLDOWN
```

then, at the canonical confirmation timestamp:

1. stop generating new legs immediately;
2. mark the `asset_event_id` as ending/ended;
3. force-resolve **every still-open leg** in that asset event using `EVENT_END_EXIT`;
4. calculate fees, PNL, R, MFE and MAE normally;
5. preserve the reason code that caused the event-end exit.

Canonical v1 event-end execution reference:

```text
exit_reference =
close of the fully closed 5m candle that confirmed terminal event end
```

This keeps live Shadow and backtest identical.

If a future version uses confirmed 1m event-end exits, it must be a new config/version and use the exact same closed-1m rule in live and backtest.

### 11.7 PAUSE is not event end

`PAUSE_POSSIBLE_SECOND_LEG` means:

```text
no immediate new leg
event remains open
existing leg follows its own resolver unless another configured safety rule exits it
wait for:
  renewed WATERFALL_ACTIVE / SECOND_LEG
  OR confirmed EXHAUSTION
```

This is essential because a waterfall can pause and then resume.

### 11.8 Per-leg deterministic resolution

Minimum resolver reasons:

```text
OPEN
TP_EXIT
SL_EXIT
TIME_EXIT
RECLAIM_EXIT
EVENT_END_EXIT
AMBIGUOUS_BOTH_HIT
```

Use the smallest trustworthy historical bar available, preferably 1m, to determine post-entry sequencing.

If TP and SL are both touched inside the same smallest available bar and order is unknowable:

- preserve `AMBIGUOUS_BOTH_HIT=true`,
- reuse the existing LONG conservative collision rule,
- if none exists, resolve conservatively as SL for headline stop statistics.

### 11.9 Economic win/loss vs TP-hit outcome

Because an event-end/reclaim/time exit can close a leg profitably without touching TP, store **two distinct concepts**.

#### Resolver reason

```text
TP_EXIT
SL_EXIT
TIME_EXIT
RECLAIM_EXIT
EVENT_END_EXIT
```

#### Economic outcome

After fees:

```text
WON   if net_r_after_fees > configured_flat_epsilon
LOST  if net_r_after_fees < -configured_flat_epsilon
FLAT  otherwise
```

Dashboard `WR` should use economic `WON / (WON + LOST)`.

Also report:

```text
TP_HIT_RATE
STOP_HIT_RATE
EVENT_END_EXIT_RATE
```

so economic WR does not hide how the exit occurred.

### 11.10 Risk unit and dual R

For SHORT:

```text
risk_price = SL - entry
risk_price > 0
```

Required columns:

#### `r_flat_gross`

The clean theoretical strategy result before fees.

Examples:

```text
SL_EXIT = -1.0R
TP_EXIT = +1.5R
other exits = (entry - exit_reference) / risk_price
```

#### `r_flat_net`

Same result after modeled/actual fees.

#### `r_gap_stress`

Mirror the existing LONG/crash-stress resolver convention exactly if one exists.

Required intent:

- `r_flat_gross` = clean theoretical fixed-stop/exit result
- `r_flat_net` = economic result after fees
- `r_gap_stress` = adverse-reality stress result when MAE/gap exceeds the nominal clean stop model

If the existing LONG pipeline has a precise crash/gap formula, reuse it rather than inventing a second definition.

Always store:

```text
mfe_r
mae_r
```

independently.

### 11.11 Fees — mandatory because multi-leg events pay repeatedly

Every leg must track:

```text
entry_fee
exit_fee
total_fees
fee_model_version
gross_pnl
net_pnl
r_flat_gross
r_flat_net
```

Reuse the existing LONG/Binance fee model if present.

Do not hard-code a fee rate in business logic.

The model should support:

- maker/taker assumptions,
- symbol-specific fee treatment if necessary,
- fee schedule/config version.

The event aggregate must show:

```text
number_of_legs
gross_r
net_r_after_fees
total_fees
fee_drag_r
```

This is necessary to determine whether repeated smaller legs outperform one longer-held position after Binance fees.

### 11.12 Position sizing / risk per leg

Signal-quality evaluation in R is separate from capital sizing.

Each leg is normalized to its own `1R_leg`.

The Shadow system should also support a configurable capital risk size such as:

```text
risk_per_leg_pct
```

but should reuse the existing LONG position-sizing model when available.

Do not impose a finite number of legs merely to control risk.

Instead measure and control:

- per-leg risk,
- maximum simultaneous open risk,
- realized event drawdown,
- event-level loss streak,
- total fee drag.

Any future event-level circuit breaker should be versioned and tested separately from the Waterfall detection logic.

### 11.13 Strategy variants

From the same closed-5m continuation-cycle candidate stream, support:

#### `NAIVE_ACTIVE_SHORT`

Enter every eligible distinct continuation cycle while `WATERFALL_ACTIVE`, without Pullback Quality filtering.

#### `FILTERED_WATERFALL_SHORT`

Require the configured Pullback Quality / do-not-chase filter.

Both variants:

- may produce unlimited legs over a long event,
- use the same one-TP fixed exit kit,
- obey the same event-end override,
- include fees.

This is the mandatory baseline for testing whether Pullback Quality adds value.

### 11.14 Performance by leg, event, symbol and portfolio

The system must report at four levels.

#### Leg

```text
leg_id
entry
SL
TP
resolution_reason
economic_outcome
gross/net R
fees
MFE/MAE
hold time
```

#### Asset event

```text
asset_event_id
symbol
number_of_legs
wins
losses
gross_r
net_r
fees
event_max_drawdown_r
event_duration
event_end_reason
```

A large cascade might have many legs.

A small cascade might have only one.

#### Symbol

Required:

```text
event_count
leg_count
WR
TP hit rate
expectancy
avg R
PF
net R
fees
fee drag R
max drawdown
avg legs/event
median legs/event
avg event duration
```

#### Portfolio/global

Same metrics across all eligible vehicles.

### 11.15 Rare-event behavior is expected

Do not force the system to generate a minimum number of events or trades.

The working expectation is that high-quality Waterfall events may be relatively rare — potentially only several per month — while smaller valid events may generate only one or two legs.

This rarity is a feature to measure, not a defect to "fix" by loosening thresholds.

Required frequency metrics:

```text
regime_events_per_month
asset_events_per_symbol_per_month
legs_per_event
days_between_events
event_duration_distribution
```

Do not optimize for trade count.

The optimization target is robust out-of-sample expectancy after fees and drawdown.

---

## 12. Manual-trade ground truth

Real trades from 2026-08-30:

| Side | Open local | Close local | Entry | Exit | PNL USDT | ROI |
|---|---|---|---:|---:|---:|---:|
| SHORT | 15:49:46 | 16:05:10 | 0.0036087 | 0.0035734 | +152.50 | +0.91% |
| SHORT | 16:17:57 | 16:23:37 | 0.0035285 | 0.0034906 | +127.08 | +0.97% |
| SHORT | 16:34:31 | 16:36:14 | 0.0034458 | 0.0034117 | +73.13 | +0.92% |
| SHORT | 16:38:39 | 16:50:44 | 0.0034161 | 0.0034047 | +22.90 | +0.26% |
| LONG | 16:52:58 | 16:54:12 | 0.0034073 | 0.0033989 | -14.75 | -0.34% |

Important interpretation:
- The first profitable short at 15:49:46 occurred before the preliminary detector's ~16:05 PREALERT. Investigate 15:30-16:05 for earlier non-lookahead features.
- The 16:38:39 short remained profitable but produced much less ROI, consistent with a degrading waterfall.
- The losing long at 16:52:58 demonstrates that "waterfall exhausted" does not mean "reversal confirmed."

Also visible from the screenshots, but not part of the same Aug-30 cascade:
- 2026-08-29 00:48:41 -> 02:20:25 SHORT
- entry 0.0036212
- close 0.0036167
- PNL +0.51
- ROI +0.04%

### 12.1 Timezone rule — Phase 1 requirement

Every manual-trade row must store:

```text
ts_entry_local
ts_exit_local
ts_entry_utc
ts_exit_utc
tz_source
timestamp_verified
source_reference
```

Initial `tz_source` is `America/Tijuana` for the supplied screenshots.

The one-time verification against Binance export/API timestamps is a **Phase 1 acceptance requirement**, not a later manual-trade phase task.

Do not permanently treat converted UTC timestamps as verified until that check passes.

### 12.2 Link manual trades to canonical Waterfall signals

Add nullable linkage fields such as:

```text
matched_leg_id
match_method
match_time_delta_seconds
manual_label
```

The system should determine which `waterfall_leg` corresponds most closely to each manual SHORT.

The purpose is to answer:

- did the strategy emit a leg before/near the human entry?
- was the human entry earlier than the algorithm?
- was the algorithm's signal filtered out?
- what event state/scores existed at the human entry?

The losing manual LONG must **not** be mapped as a valid Waterfall SHORT signal. It remains evidence for the `EXHAUSTION != LONG` rule.

### 12.3 Snapshot reconstruction

For each manual trade, reconstruct:

```text
T-30
T-15
T-10
T-5
T0
T+5
T+10
T+20
```

The priority window remains 15:30-16:05.

---

## 13. Event labels

Required labels:
- TRUE_WATERFALL
- FALSE_ALERT
- SECOND_LEG
- PAUSE_ONLY
- EXHAUSTION_TRUE
- EXHAUSTION_FALSE
- LATE_SIGNAL

Manual correction/annotation should be possible.

---

## 14. Database integration and parity with the existing LONG pipeline

Adapt existing schema instead of duplicating it.

The Waterfall strategy must mirror the core LONG opportunity/resolver/performance pipeline wherever possible.

Before creating new tables, inspect whether the existing system already has logical equivalents such as:

```text
opportunities
signals
resolver
resolved_trades
asset_performance
daily_reports
weekly_reports
```

Preferred design:

- reuse the same generic signal/resolver/performance entities,
- add `strategy = WATERFALL_SHORT`,
- represent global/asset Waterfall event context through existing event abstractions or minimal extension tables,
- expose Waterfall-specific views only when needed.

Do **not** build a second resolver/performance architecture unless reuse is technically impossible.

### 14.1 Required hierarchy

Need logical equivalents of:

```text
waterfall_regime_event
    1 -> many waterfall_asset_event
        1 -> many waterfall_leg
```

There is no hard maximum leg count.

### 14.2 `waterfall_regime_event`

Minimum:

```text
regime_event_id
started_at
ended_at
btc_state
start_reason_codes
end_reason_codes
config_version
feature_tier
```

### 14.3 `waterfall_asset_event`

Minimum:

```text
asset_event_id
regime_event_id
symbol
started_at
tradeable_started_at
ended_at
event_end_reason
vehicle_eligible
eligibility_snapshot
number_of_legs
gross_r
net_r
total_fees
fee_drag_r
event_max_drawdown_r
config_version
```

### 14.4 Core leg fields — parity with LONG

Each `waterfall_leg` or reused generic opportunity row must have equivalents of:

```text
leg_id / signal_id
asset_event_id
regime_event_id
strategy = WATERFALL_SHORT
strategy_variant
symbol
side = SHORT

trigger_ts
entry
stop
tp
risk_price
risk_atr_multiple
max_hold_minutes
reclaim_rule

status
resolution_reason
economic_outcome
resolved_at
exit_reference

r_flat_gross
r_flat_net
r_gap_stress
gross_pnl
net_pnl

entry_fee
exit_fee
total_fees
fee_model_version

mfe
mae
mfe_r
mae_r

config_version
feature_tier
```

Waterfall-specific fields:

```text
state_from
state_to
cascade_score
pullback_quality_score
exhaustion_score
waterfall_velocity
persistence_score
vehicle_eligible
new_continuation_cycle
reason_codes
alert_id
leg_number
```

### 14.5 Event-end bulk resolution

The DB/resolver must support:

```text
asset_event_id -> all OPEN legs
```

and atomically/deterministically resolve every still-open leg with:

```text
resolution_reason = EVENT_END_EXIT
exit_reference = terminal event-end closed-5m price
```

when confirmed `EXHAUSTION/NO_NEW_SHORTS/COOLDOWN` ends the event.

### 14.6 Supporting data

Need equivalents of:
- raw_market_data / candles
- derivatives_snapshots
- orderflow
- features
- regime_scores
- manual_trades
- event_labels
- replay_events
- config_versions
- bot_runs / data_quality

### 14.7 Performance views/tables

Prefer generic existing LONG performance infrastructure filtered by:

```text
strategy = WATERFALL_SHORT
```

Need Waterfall views for:

```text
waterfall_leg_performance
waterfall_event_performance
waterfall_asset_performance
waterfall_portfolio_performance
```

Minimum asset metrics:

- event count
- leg count
- WR
- TP hit rate
- expectancy
- avg gross/net R
- PF
- net R
- total fees
- fee drag R
- max drawdown
- avg/median legs per event
- event frequency per month

### 14.8 Alert -> event -> leg -> result foreign keys

Required traceability:

```text
alert
 -> regime_event
 -> asset_event
 -> leg candidate/tradeable leg
 -> resolver outcome
 -> performance aggregation
```

Never leave ACTIVE/DO_NOT_CHASE/EXHAUSTION alerts untraceable.

Idempotency is mandatory.

---

## 15. Event replay

Build a replay that can reconstruct an event minute by minute with:
- PEPE price
- BTC price/regime
- Cascade Score
- Pullback Quality
- Exhaustion
- Velocity
- Persistence
- OI
- taker ratio
- volume
- state transitions
- manual entry/exit markers
- every generated leg entry/SL/TP
- open-leg count
- cumulative event gross/net R
- cumulative fees
- event-end forced-close markers

Replay must only use information available at each historical timestamp.

---

## 16. Full multi-leg strategy resolver and outcome evaluator

The resolver must operate at both **leg level** and **event level**.

### 16.1 Leg resolution

For every Waterfall leg determine:

- TP reached?
- SL reached?
- reclaim exit?
- time exit?
- event-end forced exit?
- ambiguous same-bar collision?
- resolved timestamp
- exit reference

Required resolution reasons:

```text
TP_EXIT
SL_EXIT
TIME_EXIT
RECLAIM_EXIT
EVENT_END_EXIT
AMBIGUOUS_BOTH_HIT
```

### 16.2 Economic outcome and WR

After fees:

```text
WON  = net_r > epsilon
LOST = net_r < -epsilon
FLAT = otherwise
```

Primary strategy WR:

```text
WON / (WON + LOST)
```

Also report separately:

```text
TP_HIT_RATE
SL_HIT_RATE
EVENT_END_EXIT_RATE
TIME_EXIT_RATE
RECLAIM_EXIT_RATE
```

### 16.3 R metrics

Required per leg:

```text
r_flat_gross
r_flat_net
r_gap_stress
mfe_r
mae_r
```

Reuse exact LONG/crash semantics where they already exist.

### 16.4 Event-level resolution

When the event terminal condition fires:

1. set `ended_at`,
2. record `event_end_reason`,
3. stop leg creation,
4. resolve all still-open legs as `EVENT_END_EXIT`,
5. aggregate event metrics.

Required event output:

```text
number_of_legs
wins
losses
flats
gross_r
net_r
total_fees
fee_drag_r
event_max_drawdown_r
event_duration
avg_leg_hold
```

### 16.5 Forward research metrics

Retain detector research diagnostics:

- return at 5/15/30/60m from each leg signal
- new low?
- time-to-low
- max rebound
- continuation / false / late classification
- second-leg occurrence

### 16.6 Aggregate strategy performance

Per symbol and portfolio:

```text
event_count
leg_count
WR
TP hit rate
expectancy R
average R
PF
net R
fees
fee drag R
max drawdown R
average MFE R
average MAE R
average legs/event
median legs/event
events/month
```

Produce daily, weekly and monthly reports.

---

## 17. Validation — detector AND strategy

Required:
- reproduce 2026-08-30
- then evaluate weeks/months
- walk-forward / out-of-sample
- ablation tests
- feature-tier reporting
- multi-vehicle reporting

### 17.1 Detector metrics

- waterfall precision
- waterfall recall
- false alerts/day
- PREALERT lead time
- late-signal rate
- Exhaustion precision
- EXHAUSTION_FALSE rate
- SECOND_LEG rate

### 17.2 Strategy metrics

Out-of-sample, report both **leg-level and event-level** performance.

Do not cap event legs for the primary strategy. The backtest determines how many distinct continuation cycles naturally occur.

Report:

```text
WR
PF
expectancy R
avg R
net R
max drawdown R
signal count
avg MFE R
avg MAE R
event_count
leg_count
avg legs/event
median legs/event
events/month
total fees
fee drag R
```

by:

- symbol,
- total portfolio,
- strategy variant,
- feature tier,
- config version,
- daily/weekly period.

### 17.3 Mandatory Pullback Quality baseline

Run two strategy variants over the same canonical closed-5m candidate stream:

#### Baseline

```text
NAIVE_ACTIVE_SHORT
```

Short every eligible `WATERFALL_ACTIVE` / `SECOND_LEG` candidate without Pullback Quality filtering.

#### Filtered

```text
FILTERED_WATERFALL_SHORT
```

Apply the configured Pullback Quality / do-not-chase rules.

Both variants may generate unlimited distinct legs while their events remain valid and both must include repeated Binance fee drag.

The Pullback Quality Engine is only justified if the filtered variant improves out-of-sample strategy quality, e.g.:

- expectancy,
- PF,
- drawdown,
- or MAE,

without an unacceptable collapse in sample size/opportunity count.

### 17.4 Other detector baselines

Compare against:
- Supertrend-only
- EMA+RSI
- BTC-only
- price/volume-only

### 17.5 Vehicle ranking

Rank vehicles using strategy performance, not detector accuracy alone.

Require adequate minimum sample size before promoting a new vehicle to the active universe.

The Aug-30 event is a test case, not proof of general validity.

---


## 18. Alert -> Event -> Leg -> Result traceability

Every relevant alert must be tied to the research/strategy ledger.

Required alert types include:

```text
PREALERT
CASCADE_ARMED
WATERFALL_ACTIVE
NEW_LEG
ACTIVE_BUT_DO_NOT_CHASE
PAUSE_POSSIBLE_SECOND_LEG
SECOND_LEG
EXHAUSTION
NO_NEW_SHORTS
EVENT_END
```

Rules:

- `PREALERT` references/creates the regime event context.
- vehicle `WATERFALL_ACTIVE` references/creates its `asset_event_id`.
- a distinct validated continuation cycle creates a `leg_id`.
- `ACTIVE_BUT_DO_NOT_CHASE` references the asset event/candidate and explains why no leg was opened.
- repeated valid cycles may create unlimited sequential legs while the event persists.
- `EXHAUSTION / NO_NEW_SHORTS / EVENT_END` references the asset event and every open leg closed by the event-end override.

Dashboard traversal:

```text
alert
-> regime event
-> asset event
-> leg(s)
-> entry / SL / TP
-> fees
-> resolution
-> gross/net R
-> event aggregate
-> symbol performance
```

This traceability is mandatory for debugging and for comparing human trades against model behavior.

---


## 19. Eight-point completeness checklist

The specification is incomplete unless all eight are true:

1. **Shadow strategy defined:** closed-5m SHORT legs + one fixed/versioned TP per leg + SL/time/reclaim/event-end exits + deterministic resolver + dual R.
2. **Unlimited event legs:** no arbitrary 2/3-leg cap; each new leg requires a distinct valid continuation cycle; event termination stops all new legs and closes every open leg.
3. **Multi-asset universe:** BTC global regime; explicit vehicle list; eligibility screen; per-vehicle ranking.
4. **Backfill matrix:** native horizons, proxies, exclusions and feature tiers are explicit.
5. **Manual-trade time model:** `ts_local`, `ts_utc`, `tz_source`, Phase-1 verification and `matched_leg_id`.
6. **Full outcome/performance model:** economic WR, TP/SL rates, gross/net R, gap-stress R, fees, MFE/MAE, PF, expectancy, net R and drawdown at leg/event/symbol/portfolio levels.
7. **Strategy validation:** out-of-sample performance plus `NAIVE_ACTIVE_SHORT` vs `FILTERED_WATERFALL_SHORT`, including repeated fee drag.
8. **LONG pipeline parity + traceability:** reuse/mirror existing opportunity/resolver/performance infrastructure and preserve alert -> event -> leg -> result links.

Summary requirement:

> One BTC regime event may contain multiple asset Waterfall events; each asset event may contain as many distinct SHORT legs as valid conditions persist. Every leg has one TP/SL, repeated fees are measured, and confirmed event exhaustion immediately blocks new legs and force-closes all remaining open legs.

---

# Waterfall Module — Implementation Plan

## Rule

This is an integration into an existing Shadow System.

Do not implement all phases in one uncontrolled pass.

The first architectural goal is parity with the existing LONG pipeline, especially opportunity/signal model, resolver, dual-R convention, fees, performance aggregation and reporting.

## Phase 0 — Inspect only

Deliver:
- current architecture map
- collectors/sources
- DB/schema
- scheduler
- existing LONG opportunities/signals
- LONG resolver and exact flat-R / crash-gap semantics
- fee model
- per-asset performance tables/views
- daily/weekly reports
- alert pipeline
- dashboard
- backtest/replay framework
- exact integration points
- minimal-change proposal
- risks / missing data

Explicitly answer:

> Can `regime_event -> asset_event -> unlimited legs` reuse the LONG signal/resolver/performance pipeline?

Do not write production code in Phase 0.

## Phase 1 — Time verification + schema + continuous capture + backfill matrix

- verify supplied manual-trade local timestamps against Binance export/API
- persist local/UTC/timezone/verification
- add only missing event/leg fields or minimal extension tables
- configure BTC regime + multi-vehicle universe
- ensure continuous 1m/5m storage
- add/verify OI, funding, taker flow, ratios
- create machine-readable backfill matrix
- implement feature tiers/proxy flags
- data quality/freshness
- UTC normalization
- idempotency tests

Gate:
timestamps verified; continuous data demonstrated; historical limitations reproducible.

## Phase 2 — Vehicle screening + Feature Engine

Implement/reuse:
- amplification
- BTC correlation
- RVOL
- eligibility
- base features
- Waterfall Velocity
- Persistence
- Failed Recovery
- Deceleration
- cross-asset features

Gate:
tests + eligibility report + no lookahead.

## Phase 3 — Three scoring engines

Implement:
- Cascade/Regime
- Pullback Quality
- Exhaustion

Config external/versioned.

Gate:
scores + reason codes for known timestamps/symbols.

## Phase 4 — State and event lifecycle

Implement/reuse:
- NORMAL
- DISTRIBUTION_REVERSAL
- PREALERT
- CASCADE_ARMED
- WATERFALL_ACTIVE
- PAUSE_POSSIBLE_SECOND_LEG
- EXHAUSTION
- COOLDOWN

Add:
- `regime_event_id`
- `asset_event_id`
- PAUSE -> SECOND_LEG / ACTIVE
- terminal event-end semantics

Gate:
state/event tests pass.

## Phase 5 — Unlimited multi-leg Shadow strategy

Implement canonical leg creation:

```text
SIDE = SHORT
ENTRY = closed 5m continuation-trigger close
one TP per leg
no hard maximum number of legs/event
new continuation cycle required before every new leg
```

Preferred v1:

```text
max_concurrent_open_legs_per_asset_event = 1
```

but the model must support >1 later.

Gate:
a long historical Waterfall may naturally produce N legs; a small event may produce 1-2; no arbitrary cap.

## Phase 6 — One-TP exit kit + resolver parity with LONG

Initial fixed kit:

```text
SL = entry + 1.0 * ATR14(5m)
TP = entry - 1.5R
max_hold = 60m
reclaim rule = deterministic configured closed-5m rule
```

Add terminal override:

```text
confirmed EXHAUSTION / NO_NEW_SHORTS / terminal COOLDOWN
-> stop new legs
-> close all OPEN legs at terminal confirmed 5m close
-> resolution = EVENT_END_EXIT
```

Store:
- gross/net R
- gap-stress R
- MFE/MAE
- fees per leg
- fees per event

Gate:
deterministic replay and LONG resolver parity.

## Phase 7 — Alert/event/leg traceability

Integrate:

```text
alert
-> regime_event
-> asset_event
-> leg(s)
-> resolver
-> event aggregate
```

Gate:
dashboard/API traverses full chain.

## Phase 8 — Manual trade import and leg matching

Seed supplied Aug-30 trades.

Generate T-30/T-15/T-10/T-5/T0/T+5/T+10/T+20.

Match manual SHORTs to the closest/appropriate generated `leg_id`.

Priority:
15:30-16:05.

Gate:
human-vs-algorithm timing report.

## Phase 9 — Event Replay

Show:
- BTC regime
- vehicle price
- three scores
- eligibility
- state/event lifecycle
- every leg entry/SL/TP
- open-leg count
- OI/taker/volume
- fees
- manual trades
- terminal event-end close-all marker

Gate:
Aug-30 replay without lookahead.

## Phase 10 — Performance pipeline

Reuse LONG performance.

Required at leg/event/symbol/portfolio level:

- WR
- TP/SL/event-end rates
- expectancy
- avg R
- PF
- net R
- fees
- fee drag
- max drawdown
- event count
- leg count
- avg/median legs per event
- event frequency/month

Gate:
aggregates reconcile exactly with underlying legs.

## Phase 11 — Historical backtest

Run weeks/months.

Required:
- walk-forward
- out-of-sample
- ablation
- detector baselines
- naive vs Pullback-filtered strategy
- multi-asset ranking
- feature-tier separated analysis
- repeated fee drag
- event frequency distribution

Do not force a minimum number of events.

## Phase 12 — Calibration

Only after historical evidence.

Calibrate:
- detector thresholds
- eligibility
- Pullback filter
- hysteresis/re-arm
- event-end conditions

Keep fixed v1 exit kit as baseline before optimizing it.

Do not optimize for trade count.

## Phase 13 — Paper/demo gate

OUT OF SCOPE until explicitly approved.

Acceptance before later advancement:
- stable data
- verified timestamps
- no lookahead
- deterministic events/legs/resolver
- dual-R and fees reproducible
- alert -> event -> leg -> result traceability
- Pullback filter improves OOS metrics vs naive
- Exhaustion/event-end reduces late pursuit
- repeated legs remain profitable after fees
- event frequency and sample size understood
- acceptable OOS PF/expectancy/net R/drawdown
- backfill/proxy limitations documented

---

# HANDOFF FOR BIG PICKLE

## Why this file exists
The prior OpenCode session is already long. Treat these repository files as the durable handoff instead of depending on a huge conversation transcript.

## Start here
1. Read `AGENTS.md`.
2. Read `docs/WATERFALL_SHADOW_SPEC.md`.
3. Read `docs/WATERFALL_IMPLEMENTATION_PLAN.md`.
4. Inspect the existing repo.
5. Do Phase 0 only unless the user explicitly asks you to proceed.

## Core insight
This system is not trying to predict every down candle.

It is trying to identify a rare regime:
- BTC establishes broad bearish conditions.
- 1000PEPE amplifies the move.
- seller aggression + volume + structure + derivatives align.
- after activation, weak pullbacks may offer continuation setups.
- eventually downside velocity and new-low expansion deteriorate.
- that exhaustion should stop new-short pursuit, but it is NOT a long signal.

## Most important empirical clue
A real profitable manual short began at 2026-08-30 15:49:46 local time, while the preliminary detector was only seeing PREALERT around 16:05.

The first research priority is therefore:
**What non-lookahead features were already changing from 15:30 to 15:49:46, and how many false alerts would those same conditions produce elsewhere?**

## Do not overfit
The manual trades are useful human ground truth, not the objective function.

## Required first response
Before coding, return:
- architecture you found
- existing components to reuse
- data gaps
- proposed file/schema changes
- which parts of this spec are already implemented
- exact Phase 1 plan
- how the existing LONG opportunity/resolver/performance pipeline will be reused
- exact canonical `waterfall_signal` schema and alert linkage
- proposed multi-asset vehicle screening integration
- backfill/proxy matrix
- uncertainties/questions that truly cannot be resolved from the repository


---

# FIRST INSTRUCTION TO BIG PICKLE

Read this entire master document.

This repository already has a Shadow System and a LONG strategy pipeline. Do not create a parallel bot or a parallel resolver/performance stack unless reuse is technically impossible.

For this first turn, perform **PHASE 0 ONLY**.

Inspect the repository and produce a detailed implementation plan mapping this specification to the existing code.

Your report must explicitly cover:

1. current collector/data pipeline,
2. database/schema,
3. scheduler/loop,
4. LONG opportunities/signals schema,
5. LONG resolver, including exact flat-R and gap/crash-stress-R semantics,
6. existing fee model,
7. existing per-asset performance, WR/expectancy/PF/net-R/max-DD reporting,
8. alerts/dashboard/backtest infrastructure,
9. BTC as single global regime reference,
10. configurable multi-asset vehicle universe and eligibility,
11. `regime_event -> asset_event -> unlimited distinct legs` data/lifecycle design,
12. closed-5m leg entry rule,
13. one-TP fixed/versioned exit kit,
14. how confirmed Exhaustion/Event End will block new legs and close every open leg,
15. repeated-fee accounting by leg and event,
16. alert -> event -> leg -> resolver -> performance traceability,
17. Binance historical backfill/proxy matrix and feature tiers,
18. manual-trade timezone verification and leg matching,
19. `NAIVE_ACTIVE_SHORT` vs `FILTERED_WATERFALL_SHORT`,
20. exact files/schema migrations required,
21. phased implementation plan with tests and a gate after every phase.

Do not implement the Waterfall module yet.
Do not place trades.
Do not add trading permissions.
Do not optimize thresholds, leg count, or exit parameters.
Do not force a target number of events/trades.
Do not guess about repository functionality that can be inspected directly.

Stop after the implementation plan and wait for approval.

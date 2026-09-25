# Waterfall SHORT Forward Shadow v2

Version: `waterfall-forward-v2`  
Mode: `FORWARD_SHADOW` only  
Vehicle: `1000PEPEUSDT`  
Regime: `BTCUSDT`

## Temporal Contract

- First run stores newest closed-bar cursor and emits no historical signal.
- Later runs process each newly closed vehicle bar once, oldest first.
- Asset and BTC 1m windows require aligned, contiguous one-minute bars ending at vehicle cutoff. BTC 5m bar requires five-minute alignment and a close no more than four minutes before cutoff. Missing, stale, gapped, or misaligned inputs fail closed.
- Signal decision timestamp is the later of signal-bar close and actual availability of every bar/OI input.
- Existing legs resolve before existing pending entries fill; new decisions happen last.
- Pending entries evaluate only closed bars whose `open_time` is strictly after decision. Immediate/taker fills use that bar open and timestamp, with adverse short slippage; no observed-time price is fabricated. Stop distance uses signal-time ATR, never fill-bar range.
- Limit entries may use that later bar high for touch detection, pay maker rate, and receive conservative `entry_ms=bar.close_time`.
- TP/SL evaluates only bars whose `open_time` is strictly after entry. This excludes all pre-entry movement and the full limit-touch bar. A valid post-fill bar touching both resolves stop first.
- Signals persist signal-bar open/close identity. Legs persist fill-bar and exit-bar open/close identity. DB checks enforce `entry_ms > decision_ms` and `exit_ms > entry_ms`; Nova independently verifies strict bar-open ordering and conservative limit timestamps.
- Runtime cursor requires every processed vehicle bar to begin exactly one millisecond after prior bar close. A gap records immutable `waterfall_v2_data_gaps` evidence, expires pending entries, and marks open legs `UNRESOLVED_DATA_GAP` without exit, price, or PnL. Post-gap OHLC never fills or resolves pre-gap state.

## Derivatives Contract

OI records retain exchange and local availability timestamps. Missing exchange time is stored as missing and never fabricated. As-of selection requires exchange timestamps at or before signal cutoff; local availability moves decision time forward. Current OI must be fresh, and prior OI must fall within configured tolerance around configured lookback. Five-minute OI confirmation fails closed without a valid pair. Funding rate, exchange timestamp, and source remain explicit; missing funding stays `missing` and is never replaced by another field.

Live Binance current-OI observations normally arrive after most recent candle cutoff, so conservative OI variant remains closed unless causal snapshots already exist. This is intentional.

## Isolation And Idempotency

All storage names start with `waterfall_v2_`; v1 schema and data are untouched. Signal-created events carry producer-native `event_id` links. Event clustering uses decision-time gaps from frozen `event_cluster_gap_ms`; no signal means no event. Unique keys cover bars, derivatives, events, snapshots, signals, pending entries, and variant legs. Persisted cursor prevents bar replay. Exact raw config bytes and SHA-256 are committed before network access for `waterfall-forward-v2`; later byte mutation raises an error. Configuration must match exact full semantics for all five variants: ID, entry mode, TP R, hold time, and OI requirement.

## Replay Evidence

`scripts/generate_waterfall_v2_replay_evidence.py` runs an offline semantic fixture through producer `process_bar`: actual `features()` no-signal control with contiguous aligned asset/BTC bars and causal OI, explicitly labeled forced semantic signal, ineligible wait bar, later fills, and still-later exits. It runs focused pytest and atomically writes `causal-tests.json`, `replay-control.json`, `nova-pre-helios.json`, and `evidence-manifest.json` under `data/reports/waterfall-v2` by default. Test evidence records command, exit code, generation time, current source hashes, payload hash, and exact-file hash reference. Generator never calls Binance, scheduler, registry, demo client, or order endpoints.

No scheduler or strategy-registry integration exists in v2.

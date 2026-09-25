# Reverse Waterfall Replay Report

Generated: 2026-09-05T12:22:06.405000Z  
Mode: research/shadow only. V0 seeds unchanged; no threshold optimization.

## Calibration Event

- Window: `['2026-09-03T12:00:00Z', '2026-09-03T16:30:00Z']` (UTC; requested PT interval converted to UTC)
- Status: `REPLAYED`
- Start / peak: `77948.8` / `81333.4`
- Event move: `4.342080955704253`%
- Move consumed before ACTIVE: `69.47349760680731`%
- Shadow legs: `5` at $50 each
- Net PnL: `-0.5951438884423015` USD, including 5 bps/side fees and 2 bps/side slippage
- Capture ratio: `-0.033015975890799444`
- Final state: `EVENT_END`

## Causal State Transitions

```json
[
  {
    "time": "2026-09-03T12:31:00Z",
    "from": "NORMAL",
    "to": "PRE_ALERT",
    "reasons": [
      "price_acceleration",
      "abnormal_volume",
      "taker_dominance",
      "hh_hl",
      "price_above_vwap",
      "ema9_gt_ema20",
      "oi_confirmation",
      "retail_short_divergence",
      "spot_confirmation"
    ],
    "close": 78184.6,
    "activation_score": 12
  },
  {
    "time": "2026-09-03T14:49:00Z",
    "from": "PRE_ALERT",
    "to": "ACTIVE",
    "reasons": [
      "price_acceleration",
      "abnormal_volume",
      "taker_dominance",
      "hh_hl",
      "price_above_vwap",
      "ema9_gt_ema20",
      "oi_confirmation",
      "retail_short_divergence",
      "spot_confirmation"
    ],
    "close": 80300.2,
    "activation_score": 12
  },
  {
    "time": "2026-09-03T14:52:00Z",
    "from": "ACTIVE",
    "to": "PAUSE",
    "reasons": [
      "three_bars_without_extreme_expansion"
    ],
    "close": 80143.3,
    "activation_score": 7
  },
  {
    "time": "2026-09-03T14:58:00Z",
    "from": "PAUSE",
    "to": "REVALIDATION",
    "reasons": [
      "score_recovered",
      "micro_high_broken"
    ],
    "close": 80251.9,
    "activation_score": 9
  },
  {
    "time": "2026-09-03T14:59:00Z",
    "from": "REVALIDATION",
    "to": "PAUSE",
    "reasons": [
      "three_bars_without_extreme_expansion"
    ],
    "close": 80405.6,
    "activation_score": 9
  },
  {
    "time": "2026-09-03T15:00:00Z",
    "from": "PAUSE",
    "to": "REVALIDATION",
    "reasons": [
      "score_recovered",
      "micro_high_broken"
    ],
    "close": 80508.4,
    "activation_score": 10
  },
  {
    "time": "2026-09-03T15:01:00Z",
    "from": "REVALIDATION",
    "to": "PAUSE",
    "reasons": [
      "three_bars_without_extreme_expansion"
    ],
    "close": 80520.2,
    "activation_score": 8
  },
  {
    "time": "2026-09-03T15:02:00Z",
    "from": "PAUSE",
    "to": "REVALIDATION",
    "reasons": [
      "score_recovered",
      "micro_high_broken"
    ],
    "close": 80687.7,
    "activation_score": 10
  },
  {
    "time": "2026-09-03T15:03:00Z",
    "from": "REVALIDATION",
    "to": "PAUSE",
    "reasons": [
      "three_bars_without_extreme_expansion"
    ],
    "close": 80789.0,
    "activation_score": 10
  },
  {
    "time": "2026-09-03T15:05:00Z",
    "from": "PAUSE",
    "to": "REVALIDATION",
    "reasons": [
      "score_recovered",
      "micro_high_broken"
    ],
    "close": 80774.1,
    "activation_score": 7
  },
  {
    "time": "2026-09-03T15:06:00Z",
    "from": "REVALIDATION",
    "to": "PAUSE",
    "reasons": [
      "three_bars_without_extreme_expansion"
    ],
    "close": 80816.2,
    "activation_score": 5
  },
  {
    "time": "2026-09-03T15:09:00Z",
    "from": "PAUSE",
    "to": "EXHAUSTION",
    "reasons": [
      "decay_signals=3"
    ],
    "close": 80645.1,
    "activation_score": 3
  },
  {
    "time": "2026-09-03T15:12:00Z",
    "from": "EXHAUSTION",
    "to": "EVENT_END",
    "reasons": [
      "close_below_ema20"
    ],
    "close": 80424.9,
    "activation_score": 3
  }
]
```

## Shadow Legs

```json
[
  {
    "entry_time": "2026-09-03T14:49:00Z",
    "entry_price": 80316.26004,
    "notional_usd": 50,
    "fee_rate": 0.0005,
    "slippage_bps": 2,
    "reason": "ACTIVE",
    "exit_price": 80408.81502,
    "gross_pnl_usd": 0.05761907984379847,
    "fees_usd": 0.050028809539921906,
    "net_pnl_usd": 0.007590270303876566
  },
  {
    "entry_time": "2026-09-03T14:58:00Z",
    "entry_price": 80267.95038,
    "notional_usd": 50,
    "fee_rate": 0.0005,
    "slippage_bps": 2,
    "reason": "REVALIDATION",
    "exit_price": 80408.81502,
    "gross_pnl_usd": 0.08774650363758285,
    "fees_usd": 0.05004387325181879,
    "net_pnl_usd": 0.03770263038576406
  },
  {
    "entry_time": "2026-09-03T15:00:00Z",
    "entry_price": 80524.50167999999,
    "notional_usd": 50,
    "fee_rate": 0.0005,
    "slippage_bps": 2,
    "reason": "REVALIDATION",
    "exit_price": 80408.81502,
    "gross_pnl_usd": -0.07183320454420485,
    "fees_usd": 0.0499640833977279,
    "net_pnl_usd": -0.12179728794193274
  },
  {
    "entry_time": "2026-09-03T15:02:00Z",
    "entry_price": 80703.83754,
    "notional_usd": 50,
    "fee_rate": 0.0005,
    "slippage_bps": 2,
    "reason": "REVALIDATION",
    "exit_price": 80408.81502,
    "gross_pnl_usd": -0.1827809736146524,
    "fees_usd": 0.049908609513192675,
    "net_pnl_usd": -0.23268958312784507
  },
  {
    "entry_time": "2026-09-03T15:05:00Z",
    "entry_price": 80790.25482,
    "notional_usd": 50,
    "fee_rate": 0.0005,
    "slippage_bps": 2,
    "reason": "REVALIDATION",
    "exit_price": 80408.81502,
    "gross_pnl_usd": -0.23606795203818332,
    "fees_usd": 0.049881966023980914,
    "net_pnl_usd": -0.28594991806216424
  }
]
```

## Similar Events And Normal Controls

```json
{
  "method": "non-overlapping 30m samples; ex-post 60m return P99 label",
  "p99_return_60m_pct": 1.3536646190014379,
  "similar_events": [
    {
      "start": "2026-08-19T15:00:00Z",
      "future_return_60m_pct": 3.9295347779966683
    },
    {
      "start": "2026-08-21T08:00:00Z",
      "future_return_60m_pct": 3.153841115986644
    },
    {
      "start": "2026-08-20T08:00:00Z",
      "future_return_60m_pct": 2.4651520014672856
    },
    {
      "start": "2026-09-03T14:00:00Z",
      "future_return_60m_pct": 2.351719395297569
    },
    {
      "start": "2026-08-21T01:00:00Z",
      "future_return_60m_pct": 1.8319916375928225
    },
    {
      "start": "2026-08-19T20:30:00Z",
      "future_return_60m_pct": 1.5386496210136436
    },
    {
      "start": "2026-08-20T14:30:00Z",
      "future_return_60m_pct": 1.496378780155827
    },
    {
      "start": "2026-08-18T13:30:00Z",
      "future_return_60m_pct": 1.3675013651610834
    },
    {
      "start": "2026-08-25T01:30:00Z",
      "future_return_60m_pct": 1.3536646190014379
    }
  ],
  "normal_controls": [
    {
      "start": "2026-08-11T05:00:00Z",
      "future_return_60m_pct": 0.0
    },
    {
      "start": "2026-08-10T01:30:00Z",
      "future_return_60m_pct": -0.01539297495408709
    },
    {
      "start": "2026-08-13T00:00:00Z",
      "future_return_60m_pct": 0.02930232118496523
    },
    {
      "start": "2026-08-29T21:00:00Z",
      "future_return_60m_pct": 0.04508133210212595
    },
    {
      "start": "2026-08-06T11:30:00Z",
      "future_return_60m_pct": -0.061965451162704355
    }
  ],
  "detector_evaluation": [
    {
      "label": "SIMILAR",
      "start": "2026-08-19T15:00:00Z",
      "detected": true,
      "active_at": "2026-08-19T15:25:00Z",
      "legs": 2,
      "net_pnl_usd": 0.502535275671331,
      "capture_ratio": 0.08879753212003232
    },
    {
      "label": "SIMILAR",
      "start": "2026-08-21T08:00:00Z",
      "detected": true,
      "active_at": "2026-08-21T08:58:00Z",
      "legs": 1,
      "net_pnl_usd": -0.7556426857954943,
      "capture_ratio": -0.3350621310835513
    },
    {
      "label": "SIMILAR",
      "start": "2026-08-20T08:00:00Z",
      "detected": true,
      "active_at": "2026-08-20T08:10:00Z",
      "legs": 2,
      "net_pnl_usd": 0.47634710616643283,
      "capture_ratio": 0.1504791259089733
    },
    {
      "label": "SIMILAR",
      "start": "2026-09-03T14:00:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "SIMILAR",
      "start": "2026-08-21T01:00:00Z",
      "detected": true,
      "active_at": "2026-08-21T01:19:00Z",
      "legs": 1,
      "net_pnl_usd": -0.10354833141720535,
      "capture_ratio": -0.03845910490856465
    },
    {
      "label": "SIMILAR",
      "start": "2026-08-19T20:30:00Z",
      "detected": true,
      "active_at": "2026-08-19T21:08:00Z",
      "legs": 1,
      "net_pnl_usd": -0.42688940401273145,
      "capture_ratio": -0.3784123453237397
    },
    {
      "label": "SIMILAR",
      "start": "2026-08-20T14:30:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "SIMILAR",
      "start": "2026-08-18T13:30:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "SIMILAR",
      "start": "2026-08-25T01:30:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "CONTROL",
      "start": "2026-08-11T05:00:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "CONTROL",
      "start": "2026-08-10T01:30:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "CONTROL",
      "start": "2026-08-13T00:00:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "CONTROL",
      "start": "2026-08-29T21:00:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    },
    {
      "label": "CONTROL",
      "start": "2026-08-06T11:30:00Z",
      "detected": false,
      "active_at": null,
      "legs": 0,
      "net_pnl_usd": 0,
      "capture_ratio": null
    }
  ],
  "detected_similar": 5,
  "false_positive_controls": 0,
  "note": "Labels are evaluation-only and never detector features."
}
```

## Interpretation And Limits

- Features use only closed bars and metrics whose conservative availability time is no later than decision time.
- Fills use next bar open, never trigger-bar high/low or an earlier timestamp.
- Similar-event labels use future returns only for evaluation, never as features.
- Historical depth, historical book ticker, full historical aggTrades, and liquidation events are absent. Replay therefore remains PARTIAL.
- One calibration event and small control set cannot support new threshold recommendations. Keep V0 seeds unchanged pending broader shadow persistence.

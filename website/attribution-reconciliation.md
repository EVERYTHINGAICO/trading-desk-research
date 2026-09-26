---
title: Strategy Attribution and Binance Reconciliation
description: End-to-end trading strategy attribution and Binance Futures Demo reconciliation across signals, orders, fills, positions, protection, funding, commissions, and results.
keywords: strategy attribution, Binance reconciliation, trading order lifecycle, position cycle accounting, trading PnL attribution
canonical: https://everythingaico.github.io/trading-desk-research/attribution-reconciliation/
---

# Strategy Attribution And Binance Reconciliation

Attribution answers: **which frozen strategy decision owns this exchange position and its complete economic result?**

## Identity Chain

```text
experiment
  -> strategy version + configuration hash
  -> opportunity / signal
  -> frozen plan
  -> order intent + client order ID
  -> exchange order and fills
  -> position cycle
  -> protection orders
  -> commissions + funding + realized PnL
  -> strategy result
```

Every break in this chain is a first-class discrepancy. It must not be hidden under an “unattributed” aggregate indefinitely.

## Why Balance Is Not Performance

Wallet balance can move because of realized PnL, unrealized PnL, commissions, funding, transfers, deposits, withdrawals, corrections or positions created outside the system. Reconciled cycle attribution is required before assigning a balance change to a strategy.

## Reconciliation Properties

- Safe to repeat without duplicating ownership.
- Exact symbol and position-side matching.
- Time-bounded fill and funding linkage.
- Ambiguity remains unresolved instead of guessed.
- Repairs retain before/after evidence.
- Performance excludes or labels incomplete attribution.

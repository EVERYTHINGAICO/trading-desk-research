---
title: Algorithmic Trading Research Glossary
description: Definitions for Shadow trading, Binance Futures Demo, strategy attribution, reconciliation, causal availability, evidence classes, PBO, DSR, and immutable strategy versions.
keywords: algorithmic trading glossary, Shadow trading definition, Binance Futures Demo definition, PBO, Deflated Sharpe Ratio, strategy attribution
canonical: https://everythingaico.github.io/trading-desk-research/glossary/
---

# Research And Trading Glossary

**Attribution**  
The identity chain assigning an order, position and economic result to one frozen strategy decision.

**Binance Futures Demo**  
An exchange-provided environment used here for execution research. It is not equivalent to live trading.

**Causal availability**  
The requirement that data be published and received before the recorded decision time.

**Deflated Sharpe Ratio (DSR)**  
A statistic designed to account for selection bias, non-normal returns and the number of trials considered.

**Idempotency**  
The property that safely repeating an operation does not duplicate its economic effect.

**Probability of Backtest Overfitting (PBO)**  
A diagnostic for how often model selection is expected to choose a strategy that underperforms out of sample.

**Reconciliation**  
Comparison and repair of local records against observed exchange orders, fills, positions, fees and funding.

**Shadow trading**  
Forward observation of frozen decisions without sending exchange orders.

**Strategy version**  
An immutable identity for rules. Changing parameters or logic creates a new version rather than rewriting evidence.

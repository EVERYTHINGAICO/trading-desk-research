---
title: Trading Research System Capabilities
description: Technical capabilities of the Everything AI Co trading research system, including causal signals, Shadow testing, Binance Futures Demo, risk protection, attribution, and audit evidence.
keywords: trading research system, causal signals, paper trading, Shadow trading, trading strategy versioning, trading risk controls
canonical: https://everythingaico.github.io/trading-desk-research/capabilities/
---

# Trading Research System Capabilities

## Research Pipeline

| Layer | Capability | Evidence produced |
| --- | --- | --- |
| Market observation | Spot and USD-M Futures market context | Timestamped observations and quality states |
| Strategy | Versioned causal signal rules | Strategy ID, version, configuration hash, decision |
| Shadow | Forward observation without orders | Frozen plans and resolved virtual outcomes |
| Demo | Gated Binance Futures Demo execution | Order intents, exchange IDs, fills and protection |
| Safety | Notional limits and exchange-native exits | Stop-loss and take-profit records |
| Attribution | Signal-to-cycle ownership | Strategy, opportunity, order, position and result links |
| Reconciliation | Local/exchange comparison | Discrepancies, repairs and incident evidence |
| Research | Preregistration and evidence gates | Protocols, manifests, null results and evidence class |

## Deliberate Separations

- A passing unit test is not statistical validation.
- A profitable replay is not prospective evidence.
- A Demo fill is not a live-market fill.
- A higher Demo balance is not attributable performance until fills, fees, funding, transfers, and cycles reconcile.
- Enabling a strategy for observation does not promote its scientific evidence class.

## Technology

Python 3.13, SQLite, JSON/JSONL evidence, deterministic configuration hashes, GitHub Actions, JSON Schema, and a local HTTP dashboard. Runtime state and credentials are excluded from the public repository.

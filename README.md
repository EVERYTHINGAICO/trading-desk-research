# Everything AI Co Trading Desk Research System

![Everything AI Co](assets/everythingailogo.png)

An experimental algorithmic trading research system from [Everything AI Co](https://www.everythingaico.com/) for causal signal generation, forward Shadow testing, Binance Futures Demo execution, attribution, protection, reconciliation, and auditable strategy research.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Product version](https://img.shields.io/badge/version-0.9.0--alpha.1-orange.svg)](VERSION)
[![Research evidence](https://img.shields.io/badge/research-E1%20exploratory-yellow.svg)](docs/research/README.md)

> [!IMPORTANT]
> **The strategies in this repository have not been validated with sufficient rigor and do not have a proven trading edge.** Nothing here demonstrates future profitability. The contribution of this project is the system, research workflow, safety controls, evidence trail, and method used to evaluate strategies without look-ahead bias.

This is a public research repository, not financial advice, a trade recommendation, or a production-ready live trading product. Read [DISCLAIMER.md](DISCLAIMER.md) before using it.

## What This Project Contributes

- A staged research method: hypothesis, design, implementation, tests, forward observation, and maintenance.
- Causal signal evaluation using only information available at decision time.
- Separate Shadow and Binance Futures Demo paths for forward testing.
- Immutable strategy versions and explicit rollout configuration.
- Strategy attribution from signal through order, position, protection, and result.
- Small-notional Demo canaries, stop-loss and take-profit protection, and automatic safety checks.
- Idempotent execution, exchange reconciliation, stale-data detection, and operational alerts.
- SQLite and JSONL evidence suitable for audits, incident review, and reproducible research.
- A local dashboard for strategy status, positions, balances, attribution, and performance inspection.

## What This Project Does Not Prove

Passing software tests means that the tested code behaves according to its contracts. It does **not** establish statistical significance, robustness across regimes, realistic live execution, or profitable predictive edge.

The current suite has 120 passing software tests. Strategy validation remains a separate and unfinished research task requiring adequate forward samples, fees and slippage, regime coverage, out-of-sample analysis, and documented acceptance criteria.

## Strategy Research Status

| Strategy | Current research path | Edge status |
| --- | --- | --- |
| Pedro Ultra | Shadow and small-notional Demo | Unproven |
| Waterfall v2 | Shadow and small-notional Demo | Unproven |
| Pete Panic Dip | Shadow and small-notional Demo | Unproven |
| Reverse Waterfall | Forward Shadow and explicitly overridden Demo canary | Unproven; validation currently fails its promotion gate |

Demo activation is an observability decision, not evidence of profitability. Reverse Waterfall's Demo route is intentionally labeled as an override so a failed validation state cannot be mistaken for approval.

## Architecture

```text
market data
    -> versioned strategy signal
    -> causal eligibility and risk gates
    -> Shadow evidence or Demo adapter
    -> idempotent order execution
    -> exchange-native protection
    -> reconciliation and attribution
    -> SQLite / JSONL / reports / dashboard / alerts
```

The Demo executor refuses non-Demo Binance endpoints and remains disabled unless both `BINANCE_DEMO_TRADING_ENABLED` and `BINANCE_DEMO_ALLOW_ORDERS` are true. Credentials belong in the local environment only; see [.env.example](.env.example).

## Repository Map

```text
config/   versioned strategy and rollout configuration
docs/     designs, validation reports, incidents, releases, and maintenance notes
scripts/  scanners, executors, reconciliation, reporting, and dashboard commands
src/desk/ core research, execution, attribution, and safety modules
tests/    behavioral and regression tests for the software system
assets/   Everything AI Co and dashboard visual assets
```

Runtime databases, event streams, journals, credentials, personal agent files, and local chat artifacts are intentionally excluded from the public repository.

## Quick Start

Use Python 3.13 and start in Shadow mode. Commands below assume the repository root as the working directory.

```bash
python -m venv .venv
```

Activate the environment with `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on Linux and macOS, then install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

```bash
python -m pytest -q
python scripts/init_db.py
python scripts/run_shadow_once.py
python scripts/dashboard.py
```

The dashboard listens on `http://127.0.0.1:8890` by default. Use the environment variables documented in [.env.example](.env.example) to change runtime settings. The application does not automatically load `.env` files.

Do not enable Demo order flags until you have reviewed the configuration, exchange account, notional limits, and [DISCLAIMER.md](DISCLAIMER.md).

## Research Method

1. **Plan:** state the hypothesis, market assumptions, failure modes, and measurable acceptance criteria.
2. **Design:** define causal inputs, frozen outputs, strategy version, attribution identity, and risk boundaries.
3. **Implement:** preserve strategy isolation and record every decision needed for later reconstruction.
4. **Test:** verify software behavior and regressions independently from strategy performance.
5. **Forward observe:** collect Shadow and small-notional Demo evidence without rewriting history.
6. **Maintain:** reconcile exchange state, investigate unattributed events, monitor protections, and calibrate only through new versions.

This separation is deliberate: code correctness, operational reliability, and trading edge are different claims and require different evidence.

## Key Documentation

- [Research program index and current evidence state](docs/research/README.md)
- [Doctoral-grade research program](docs/research/DOCTORAL_RESEARCH_PROGRAM.md)
- [Scientific threat model](docs/research/SCIENTIFIC_THREAT_MODEL.md)
- [Research bibliography](docs/research/BIBLIOGRAPHY.md)
- [Research governance](docs/research/RESEARCH_GOVERNANCE.md)
- [Experiment registry](docs/research/EXPERIMENT_REGISTRY.md)
- [Evidence gates](docs/research/EVIDENCE_GATES.md)
- [Research data management](docs/research/DATA_MANAGEMENT_PLAN.md)
- [Authority and scope](docs/AUTHORITY.md)
- [Execution state](docs/EXECUTION_STATE.md)
- [Multi-strategy Demo design](docs/DEMO_MULTI_STRATEGY_DESIGN.md)
- [Attribution guardrails](docs/ATTRIBUTION_GUARDRAIL_PLAN.md)
- [Reconciliation design](docs/RECONCILIATION_DESIGN.md)
- [Reverse Waterfall validation](docs/NOVA_WATERFALL_VALIDATION.md)
- [Public GitHub publication guide](docs/GITHUB_PUBLICATION.md)
- [Security policy](SECURITY.md)

## Everything AI Co

[Everything AI Co](https://www.everythingaico.com/) builds applied AI systems with explicit process, human review, auditability, and privacy-conscious engineering. This repository publishes the engineering and research method behind an experimental quantitative trading desk while keeping profitability claims separate from technical capability.

Explore the organization's public work at [github.com/EVERYTHINGAICO](https://github.com/EVERYTHINGAICO).

## Resumen En Espanol

Este repositorio publica un sistema experimental de investigacion de trading algoritmico. **Las estrategias todavia no tienen un edge probado ni han sido validadas con suficiente rigor.** El aporte es la infraestructura, el metodo de investigacion, la trazabilidad, las protecciones y la evidencia para evaluar estrategias de forma causal, sin look-ahead bias.

## License, Versioning, And Use

The software and documentation are licensed under the [Apache License 2.0](LICENSE), with attribution information in [NOTICE](NOTICE). Everything AI Co names, logos, and product branding are governed separately by [TRADEMARKS.md](TRADEMARKS.md).

The public product version is `0.9.0-alpha.1`. Strategy identifiers such as `waterfall-forward-v2` and immutable configuration hashes are versioned independently so software releases cannot be confused with evidence of strategy performance. See [DISCLAIMER.md](DISCLAIMER.md) for risk and responsibility terms.

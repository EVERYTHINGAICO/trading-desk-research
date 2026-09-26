---
title: Trading Desk Installation and Troubleshooting
description: Troubleshooting Python installation, SQLite initialization, dashboard access, Binance Futures Demo credentials, disabled orders, stale data, and protection incidents.
keywords: trading bot troubleshooting, Binance Demo API error, Python trading system installation, SQLite trading database, dashboard not opening
canonical: https://everythingaico.github.io/trading-desk-research/troubleshooting/
---

# Installation And Troubleshooting

## Clean Installation

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/init_db.py
```

## Dashboard Does Not Open

The dashboard defaults to `http://127.0.0.1:8890`. Confirm the process is running, the port is not occupied and `DASHBOARD_HOST`/`DASHBOARD_PORT` are correct. It intentionally does not bind to the network by default.

## Demo Orders Remain Disabled

That is the safe default. Both Demo trading and order permission flags must be explicitly enabled, credentials must exist and the configured base URL must be an allowlisted official Demo/Testnet HTTPS origin.

## Missing Protection Or Attribution

Do not infer success from an open position. Inspect persistent incidents, order intents, position cycles, protection orders and reconciliation output. Preserve evidence before repair.

## Reporting Security Problems

Do not open a public issue containing credentials, account details or exploitable endpoints. Follow the repository's [security policy](https://github.com/EVERYTHINGAICO/trading-desk-research/blob/main/SECURITY.md).

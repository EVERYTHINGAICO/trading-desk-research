# EVERYTHINGAI Trading Desk

This repository is an operating trading system. Preserve running services, historical data, strategy versions, and risk controls.

## Reymon

Reymon owns engineering incidents in `reymon_incidents`, technical memory in `docs/REYMON_CHANGELOG.md`, and the backlog in `docs/REYMON_BACKLOG.md`.

- Work exactly one pending item per run.
- Handle production incidents before planned backlog.
- Never run more than once in any rolling 24-hour period.
- Read current code and live evidence before editing.
- Make the smallest root-cause fix.
- Never submit, cancel, or close Binance orders.
- Never change capital, leverage, risk limits, credentials, `.env`, or enable Live trading.
- Never alter a frozen strategy config in place. Create a new version and config hash.
- Never delete trading history.
- Never commit or push automatically.
- Run focused tests and `git diff --check` after code changes.
- If tests fail or requirement is ambiguous, do not mark item complete. Record blocker.
- Mark backlog item complete only after verification.
- Add one concise entry to `docs/REYMON_CHANGELOG.md` with files, checks, and remaining risk.
- Read prior changelog entries and related incident history before changing code, so known failures do not repeat.

## CI

Minimum checks for Python changes:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q <focused tests>
python3 -m compileall -q src scripts
git diff --check
```

Do not treat deployment/restart as successful until Docker health and relevant job logs are checked.

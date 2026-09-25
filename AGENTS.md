# EVERYTHINGAI Trading Desk

This repository is an operating trading system. Preserve running services, historical data, strategy versions, and risk controls.

## Research Integrity

Before proposing, evaluating, or describing a strategy, read `docs/research/README.md`, `RESEARCH_GOVERNANCE.md`, `SCIENTIFIC_THREAT_MODEL.md`, and `EXPERIMENT_REGISTRY.md`.

- Treat every existing strategy as E1 exploratory unless the registry records a higher evidence class.
- Never equate passing software tests, Demo activation, or account balance with statistical edge.
- Never inspect a locked confirmatory outcome before protocol registration is complete.
- Record every attempted variant, including failed and abandoned variants.
- Preserve null and negative results.
- Count independent market events, not correlated legs, unless a declared dependence model justifies otherwise.
- Any change to a registered rule, parameter, sample, metric, exclusion, cost, or threshold creates a new experiment or amendment.
- Every result must state evidence class, assumptions, uncertainty, limitations, and a link to its manifest.
- AI-generated hypotheses and analyses follow the same preregistration and disclosure rules as human-generated work.

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

# Contributing

Thank you for helping improve the Everything AI Co Trading Desk Research System.

## Scope

Contributions should improve the research system, causal evaluation, observability, safety, documentation, or test coverage. Strategy changes must not be described as profitable or proven without separately reviewed evidence.

## Development Setup

Use Python 3.13 from the repository root:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest -q
```

Activate the virtual environment before installation where your platform requires it.

## Change Process

1. Open an issue describing the problem, expected behavior, and risk boundary.
2. Create a focused branch and preserve existing strategy versions and evidence.
3. Add or update tests for behavioral changes.
4. Run the complete test suite from a clean checkout.
5. Submit a pull request that distinguishes software correctness from strategy performance.

Never include credentials, account information, runtime databases, journals, event logs, or private chat material. Report security issues according to [SECURITY.md](SECURITY.md).

## Strategy Research

Parameter or rule changes require a new strategy version. Do not rewrite prior evidence, use future information in historical decisions, or promote a strategy based only on replay, Shadow, or Demo profitability.

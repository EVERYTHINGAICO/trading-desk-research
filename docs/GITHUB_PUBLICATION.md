# Public GitHub Publication Guide

## Recommended Repository Metadata

- **Owner:** `EVERYTHINGAICO`
- **Repository name:** `trading-desk-research`
- **Visibility:** Public
- **Website:** `https://www.everythingaico.com/`
- **Description:** Experimental algorithmic trading research system for forward Shadow testing, Binance Futures Demo execution, attribution, protection, reconciliation, and auditable strategy research by Everything AI Co. No proven edge.

Recommended topics:

```text
algorithmic-trading
quantitative-research
paper-trading
shadow-trading
forward-testing
binance-futures
trading-bot
risk-management
python
sqlite
docker
ai-agents
reproducible-research
everything-ai-co
```

## Positioning and Search Language

Use accurate phrases naturally in the README, repository description, release notes, and future documentation:

- algorithmic trading research system
- quantitative strategy research
- Binance Futures Demo trading
- Shadow trading and forward testing
- strategy attribution and reconciliation
- automated trade protection and risk controls
- reproducible, auditable trading research
- AI-assisted research by Everything AI Co

Do not use claims such as “profitable bot,” “winning strategy,” “proven returns,” “guaranteed,” or “production ready.” Search visibility must not come at the cost of misleading financial claims.

## Suggested Social Preview

Use the Everything AI Co logo and this short message:

> **Trading Desk Research System**
>
> Causal forward testing, Demo execution, attribution, protection, and auditable research. Strategies are experimental; no proven edge.

## Publication Checklist

- Publish only the clean, parentless `github-safe-main` branch as `main`.
- Do not push local development branches, tags, or historical commits.
- Confirm `.env`, databases, runtime logs, journals, chats, account data, and personal agent files are absent.
- Run the complete software test suite and record the exact result without implying strategy validation.
- Run secret scanning against the final Git tree, not only the working directory.
- Configure the repository description, website, topics, and social preview.
- Enable GitHub secret scanning and push protection when available.
- Review [DISCLAIMER.md](../DISCLAIMER.md) and [SECURITY.md](../SECURITY.md).
- Choose and add a license deliberately before describing the project as open source.

## Versioning

Strategy calibration must create a new identifiable version. Preserve previous configuration and evidence so that parameter changes cannot rewrite the apparent performance of an earlier version. Demo overrides must remain explicit, narrow, and distinguishable from validated promotion.

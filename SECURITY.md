# Security Policy

## Supported Versions

Security updates are provided for the latest tagged prerelease only. Older alpha versions and untagged commits are unsupported.

## Reporting a Vulnerability

Report suspected vulnerabilities privately to `developer@everythingaico.com`. Include the affected component, reproduction steps, expected impact, and any proposed mitigation. Do not open a public issue containing credentials, account details, exploitable endpoints, or other sensitive material.

## Secrets and Account Data

- Never commit API keys, secret keys, chat identifiers, account exports, `.env` files, databases, event logs, or journals.
- Use `.env.example` only as a field reference and keep real values in the local environment.
- Use restricted Binance Demo credentials while researching execution behavior.
- Rotate credentials immediately if they are exposed, even if the exposure was brief or later removed from Git history.
- Treat Git history, release archives, build artifacts, screenshots, and issue attachments as possible disclosure surfaces.

## Trading Safety Boundary

The repository is designed for Shadow research and explicitly gated Binance Futures Demo execution. Enabling order flags, changing endpoints, increasing notional, or connecting live credentials changes the risk boundary and is not covered by the project's current validation claims.

Security fixes may be disclosed publicly after affected credentials are revoked and a mitigation is available.

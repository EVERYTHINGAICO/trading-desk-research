# GOV-001: Research Governance Ratification

- Status: `ACCEPTED`
- Decision date: 2026-09-25
- Effective governance version: `research-governance-v1`
- Decision owner: Everything AI Co repository maintainers
- Scope: research claims, experiment registration, evidence promotion, and public reporting
- Supersedes: informal research decision making

## Context

The repository contains operational software, exploratory strategies, historical reports, and Demo observations. Without an explicit authority model, readers or automated agents could mistakenly elevate engineering evidence into a statistical or profitability claim.

## Decision

Everything AI Co ratifies [RESEARCH_GOVERNANCE.md](../RESEARCH_GOVERNANCE.md), [EVIDENCE_GATES.md](../EVIDENCE_GATES.md), [SCIENTIFIC_THREAT_MODEL.md](../SCIENTIFIC_THREAT_MODEL.md), and [EXPERIMENT_REGISTRY.md](../EXPERIMENT_REGISTRY.md) as the normative research-governance baseline.

The following institutional assignments apply:

| Responsibility | Assignment | Authority and constraint |
| --- | --- | --- |
| Program sponsor | Everything AI Co | Funds or prioritizes work; cannot waive evidence gates |
| Claim owner | Everything AI Co repository maintainers | Approves exact public wording and links every claim to evidence |
| Registry custodian | Everything AI Co repository maintainers | Preserves registrations, amendments, null results, and hashes |
| Protocol proposer | Assigned per experiment | Declares the mechanism, model universe, estimand, and decision rule |
| Implementer | Assigned per experiment | Implements only the frozen protocol and discloses deviations |
| Validator | Named per E2+ experiment | Must not be the sole implementer; verifies causal and statistical evidence |
| Independent reproducer | Named per E5 claim | Must not have implemented the evaluated strategy or analysis |

No validator or independent reproducer is currently assigned because no confirmatory experiment has been registered. This is a blocking state, not an exception: no experiment may enter E2 without a named validator, and no claim may enter E5 without a named independent reproducer.

## Evidence And Claim Rules

1. All existing strategies remain E1 exploratory.
2. Demo operation is execution observation, not evidence of edge.
3. Every future experiment receives a permanent terminal status.
4. Failed, null, abandoned, invalidated, and superseded experiments remain countable research attempts.
5. Changes after registration create a linked amendment or new experiment.
6. Software tests, research statistics, prospective evidence, and operational evidence remain separate claims.
7. Live-capital authorization is outside this program and cannot be inferred from any evidence class.

## Independence Standard

For E2-E4, the validator may belong to Everything AI Co but must not be the sole author of both implementation and validation. Role overlap must be disclosed. E5 requires a reproducer who did not implement the evaluated strategy or analysis. An AI agent cannot serve as the sole independent validator or reproducer when it operated from the same prompts, context, data access, or implementation lineage.

## Amendment Procedure

Governance changes require a new decision record, public rationale, review through a protected pull request, and an updated governance version. Prior decisions remain available and linked. Governance cannot be amended retroactively to rescue a failed experiment.

## Consequences

- Promotion may be slower because independence and permanent negative records are mandatory.
- The project gains a defensible boundary between software capability and scientific support.
- Until named reviewers exist, confirmatory and independently reproduced claims remain unavailable.

## Ratification Evidence

This decision becomes effective when merged into protected `main` after required CI. The merge commit is the durable ratification signature; the GitHub issue and pull request preserve deliberation and review history.

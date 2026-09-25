# Experiment Registry

- Registry governance: `research-governance-v1`
- Registry custodian: Everything AI Co repository maintainers
- Confirmatory registrations accepted: none

This registry prevents undocumented model selection and survivorship of positive results. It begins prospectively with the public research program. Historical strategies are listed for completeness but are not retroactively treated as preregistered.

## Legacy Research Inventory

| Registry ID | Strategy | Current version | Classification | Confirmatory claim permitted | Required next action |
| --- | --- | --- | --- | --- | --- |
| LEGACY-001 | Pedro Ultra | `pedro-ultra-v1` | E1 exploratory/operational | No | Reconstruct model universe and register a new hypothesis |
| LEGACY-002 | Waterfall v2 | `waterfall-forward-v2` | E1 with causal controls | No | Define event independence, baseline, and locked confirmatory dataset |
| LEGACY-003 | Pete Panic Dip | Current configured version | E1 exploratory/operational | No | Formalize mechanism, estimand, and sampling frame |
| LEGACY-004 | Reverse Waterfall | `reverse-waterfall-forward-v1` | E1; promotion gate failed/overridden for Demo observation | No | Preserve failure, remove it from confirmatory calibration, and preregister successor |

Demo activation is operational observation, not confirmation of edge.

## Prospective Experiments

| Experiment ID | Hypothesis ID | Registered UTC | Evidence class | Strategy/config | Dataset manifest | Status | Result record |
| --- | --- | --- | --- | --- | --- | --- | --- |
| None | None | None | None | None | None | `NOT_STARTED` | None |

## Registration Rules

1. Assign sequential IDs in the form `EXP-YYYY-NNN`.
2. Add the frozen hypothesis document and hashes in the same commit.
3. Never delete or renumber an experiment.
4. Amendments create an appended record and normally a new experiment.
5. Every registered experiment receives a terminal status.
6. Every attempted variant contributes to the declared model-universe count.

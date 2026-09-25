# Research Governance

- Governance version: `research-governance-v1`
- Status: ratified by [GOV-001](decisions/GOV-001_RESEARCH_GOVERNANCE_RATIFICATION.md)
- Effective date: 2026-09-25
- Claim owner: Everything AI Co repository maintainers
- Confirmatory validator: must be named per E2+ experiment; currently unassigned and therefore blocking

## Evidence Classes

| Class | Meaning | Permitted claim |
| --- | --- | --- |
| E0 | Idea or retrospective observation | Hypothesis generation only |
| E1 | Exploratory replay/backtest | Engineering feasibility only |
| E2 | Preregistered historical confirmation | Statistical result under declared assumptions |
| E3 | Frozen prospective Shadow | Prospective causal evidence, not execution evidence |
| E4 | Small-notional Demo | Demo execution and operational evidence |
| E5 | Independently reproduced | Reproduced result within declared tolerance |

No class implies future profitability or suitability for live capital.

## Required Identities

Every experiment must bind:

- `research_question_id`
- `hypothesis_id`
- `experiment_id`
- `strategy_version`
- `config_sha256`
- `dataset_manifest_sha256`
- `code_commit`
- `protocol_sha256`
- `analysis_plan_sha256`
- `registered_at_utc`
- `evidence_class`

## Separation of Roles

- **Proposer:** writes the hypothesis and declares the model universe.
- **Implementer:** implements the frozen protocol without viewing locked outcomes.
- **Validator:** verifies causal integrity and statistical calculations.
- **Reproducer:** reruns the artifact independently.
- **Claim owner:** signs the final scope and limitations of every public claim.

One person may fill multiple roles during exploratory work, but E2 and above must disclose role overlap. E5 requires a reproducer who did not implement the tested strategy.

An AI agent may assist any role but cannot be the sole independent validator or reproducer when it shares implementation lineage, prompts, context, or data access with the work under review.

## Change Control

After registration, changes to rules, parameters, metrics, sample boundaries, costs, exclusions, or acceptance thresholds create a new experiment ID. Corrections remain linked to the superseded record; they do not overwrite it.

Access to locked test outcomes before the analysis plan is frozen invalidates confirmatory status and reclassifies the experiment as exploratory.

## Null and Negative Results

All registered experiments receive a terminal result: `SUPPORTED`, `NOT_SUPPORTED`, `INCONCLUSIVE`, `INVALIDATED`, or `ABORTED`. Missing and negative results remain in the registry and count toward the model universe used for multiple-testing correction.

## Promotion Authority

Automation may calculate gates but may not redefine them. Promotion requires:

1. machine-verifiable evidence manifest;
2. validator sign-off;
3. documented limitations;
4. a new immutable release or strategy version;
5. explicit human approval.

Live-capital deployment is outside this research program.

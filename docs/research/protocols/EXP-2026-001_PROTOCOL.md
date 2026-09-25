# EXP-2026-001 Protocol: False-Promotion Control

- Protocol version: `exp-2026-001-v1`
- Registration class: E2 confirmatory methods experiment
- Registration date: 2026-09-25
- Execution status: `BLOCKED_VALIDATOR`
- Strategy capital: none

## Research Question

Does the provenance-first promotion protocol reduce false strategy promotions relative to the repository's conventional chronological train/validation rule when researchers select among correlated variants?

## Hypotheses

- **Primary null:** the proposed protocol's false-promotion probability is greater than or equal to the baseline's probability under zero true edge.
- **Primary alternative:** the proposed protocol's false-promotion probability is lower.
- **Calibration criterion:** under the declared global-null scenarios, the proposed protocol should have false-promotion probability at or below 0.05, with a two-sided 95% interval whose upper bound does not exceed 0.075.

The superiority hypothesis and absolute calibration criterion are separate. Passing one does not imply passing the other.

## Unit And Estimand

The unit is one independently generated research campaign containing a complete candidate model universe. The primary estimand is the paired difference:

`P(any false promotion | proposed protocol) - P(any false promotion | baseline)`.

Legs within an event, symbols driven by the same latent event, and parameter variants derived from one mechanism are not independent units.

## Baseline

The baseline reproduces the current simple decision family:

1. chronological 70/30 train/validation split;
2. at least 30 closed observations;
3. positive train and validation net expectancy;
4. validation profit factor at least 1.15;
5. selection of the best passing variant without model-universe correction.

This baseline is a comparator, not an endorsed scientific method.

## Proposed Protocol

The intervention must apply all of the following without outcome-dependent substitution:

1. complete trial and model-universe accounting;
2. event-level clustering and effective sample calculation;
3. chronological purging and embargo derived from label horizon;
4. dependence-aware uncertainty estimation;
5. selection correction using preregistered DSR/PBO and family-wise or false-discovery control;
6. cost and latency stress survival;
7. one locked final evaluation untouched by selection.

Exact estimators and numerical thresholds beyond the calibration criterion must be specified in the analysis plan and numerically validated before outcomes are generated.

## Synthetic Scenario Matrix

The generator must cross these declared factors:

| Factor | Levels |
| --- | --- |
| Independent events per campaign | 30, 60, 120, 250 |
| Candidate variants | 1, 10, 50, 100 |
| Within-family dependence | 0.0, 0.3, 0.6 |
| Innovation family | Gaussian, Student-t(5), skewed heavy-tail |
| Net true effect in R/event | 0.00, 0.05, 0.10, 0.20 |
| Market process | stationary, volatility-clustered, two-state regime shift |

Each cell receives 10,000 deterministic Monte Carlo replications from a counter-based random stream. Null cells use exactly zero net effect after costs. Positive-effect cells are secondary power analyses.

## Controls

- Negative control: randomly permuted event labels preserving cluster sizes.
- Sign control: invert all strategy outcomes.
- Leakage control: deliberately inject one future-derived feature; causal controls must reject the campaign.
- Multiplicity control: increase null variants while holding data fixed; uncorrected promotion should not be mistaken for true edge.
- Cost control: apply normal, adverse, and extreme cost schedules independent of realized direction.

## Exclusions And Missingness

No generated campaign may be excluded because of poor performance, numerical failure, or inconvenient distribution. Generator or estimator failures receive explicit terminal records and count toward operational failure rates. A scenario may be invalidated only by a preregistered implementation defect that affects truth labels; reruns retain links to invalidated outputs.

## Success And Falsification

The protocol is supported only if:

1. the primary paired difference is below zero and its 95% interval excludes zero;
2. the absolute calibration criterion passes across the prespecified global-null aggregate;
3. no negative or leakage control is incorrectly promoted;
4. results remain directionally stable across dependence and heavy-tail families;
5. the artifact is reproduced from its signed manifest.

Failure of any item produces `NOT_SUPPORTED` or `INCONCLUSIVE` according to the analysis plan. Thresholds cannot be relaxed after generation.

## Boundary

This experiment evaluates a research protocol, not the profitability of Pedro Ultra, Waterfall, Pete, Reverse Waterfall, or any other strategy. It submits no orders and authorizes no strategy promotion.

# EXP-2026-001 Analysis Plan

## Analysis Populations

- **Primary:** all zero-effect cells in the complete scenario matrix.
- **Secondary:** positive-effect cells for power and false-rejection characterization.
- **Diagnostic:** each distribution, dependence, sample-size, model-universe, and market-process stratum.

## Primary Analysis

For each paired campaign, record whether the baseline and proposed protocol promote any candidate. Estimate the paired difference in false-promotion probability and a two-sided 95% interval using a paired campaign bootstrap stratified by scenario cell. Report the cell-weighted aggregate and every stratum; aggregation may not hide a failed stratum.

The primary one-sided superiority test uses alpha 0.05. The absolute calibration interval is evaluated separately against the protocol's 0.05 target and 0.075 upper-bound criterion.

## Secondary Analyses

- True-promotion probability by effect size and effective sample size.
- False rejection of known positive mechanisms.
- Calibration curves by candidate-universe size.
- Sensitivity to dependence, heavy tails, volatility clustering, and regime shift.
- Failure rates and runtimes for each method.
- Ablation of registry accounting, dependence correction, selection correction, and cost stress.

Secondary hypothesis families use Benjamini-Hochberg FDR at `q=0.05`; raw and adjusted values must both be reported. Exploratory diagnostics are labeled and cannot alter the primary decision.

## Randomness And Reproducibility

- Use a counter-based generator with seed namespace `EXP-2026-001`.
- Derive each replication stream from scenario identity and replication number.
- Record generator version, parameters, stream identity, software commit, environment digest, and output hashes.
- A rerun must not overwrite an earlier artifact.

## Numerical Validation

Before generating confirmatory outcomes:

1. verify zero-effect sample means and declared covariance against analytic targets;
2. verify effect injection independently;
3. test estimators on fixed published or independently derived examples;
4. demonstrate that label leakage is detected;
5. have the named validator approve the generator and analysis implementation without viewing confirmatory outcomes.

## Reporting

Report counts, effect estimates, uncertainty intervals, raw and adjusted significance values, assumptions, failed computations, exclusions, deviations, and residual threats. Publish null and adverse findings with the same artifact structure as favorable findings.

## Locked Decisions

No scenario, replication, outcome, metric, or method may be removed after outcomes are available. Any amendment creates a successor experiment and leaves EXP-2026-001 terminally classified under this plan.

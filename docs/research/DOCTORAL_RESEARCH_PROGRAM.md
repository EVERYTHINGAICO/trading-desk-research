# Doctoral-Grade Research Program

## Purpose

This program develops and evaluates a provenance-first protocol for algorithmic trading research. Its subject is not whether one named strategy is profitable. Its subject is whether a causal, versioned, auditable promotion protocol can reduce false discoveries while preserving enough information for independent reproduction and refutation.

The program uses Stanford's general doctoral standard as an aspiration: an original contribution to knowledge, work meeting the highest standards of its discipline, and lasting intellectual value. This repository is not affiliated with Stanford University and does not represent a Stanford dissertation.

## Proposed Contribution

> A causal and overfitting-aware protocol for promoting sparse, regime-dependent trading strategies from preregistered hypothesis through Shadow observation and small-notional Demo execution, with cryptographic provenance and event-level attribution.

## Primary Research Question

Does the proposed protocol reduce false promotion decisions relative to conventional chronological train/validation testing when researchers explore multiple correlated strategy variants?

## Secondary Questions

1. Which causal provenance controls detect look-ahead, stale-data, attribution, and evidence-reuse failures?
2. How should correlated legs, symbols, and signals be reduced to defensible independent event units?
3. How sensitive are promotion decisions to multiple-testing correction, execution costs, latency, and market regime?
4. Can an independent researcher reproduce every reported statistic from immutable inputs and a tagged software release?

## Falsifiable Claims

The protocol will be considered unsupported if it cannot outperform a declared baseline on false-promotion control in synthetic experiments, if independent reproduction materially disagrees with the signed result manifest, or if promotion decisions are unstable under preregistered cost and dependence stress tests.

No strategy-level edge claim is part of the contribution unless it separately passes the evidence gates in [EVIDENCE_GATES.md](EVIDENCE_GATES.md).

## Work Packages

| WP | Scope | Principal output | Entry condition | Exit condition |
| --- | --- | --- | --- | --- |
| WP0 | Governance | Policies, roles, registry, change control | Program approved | Every claim has an owner and evidence class |
| WP1 | Theory and protocol | Formal hypotheses, baselines, estimands | WP0 | Protocol hash frozen before confirmatory data |
| WP2 | Data foundation | Schemas, provenance, snapshots, data dictionary | WP1 | Independent reconstruction of one canonical event |
| WP3 | Statistical validation | Dependence-aware inference and overfitting diagnostics | WP2 | Synthetic calibration and numerical verification pass |
| WP4 | Execution validity | Cost, latency, partial-fill and failure models | WP2 | Stress suite bounds optimistic performance |
| WP5 | Confirmatory studies | Ablations, controls, locked test evaluation | WP3-WP4 | Predetermined analyses completed without retroactive edits |
| WP6 | Prospective evidence | Frozen Shadow then Demo observation | WP5 | Effective sample and track-length requirements met |
| WP7 | Independent reproduction | External rerun and discrepancy report | WP6 | Results reproduced within declared tolerances |
| WP8 | Manuscript and defense | Papers, thesis narrative, limitations | WP7 | Claims survive adversarial review |

## Required Statistical Methods

- Event-level estimands and dependence-aware block bootstrap intervals.
- Probabilistic and Deflated Sharpe Ratio.
- Probability of Backtest Overfitting.
- Purged and embargoed chronological evaluation; CPCV where assumptions permit.
- White Reality Check or Superior Predictive Ability test against a declared model universe.
- False Discovery Rate control across strategies, symbols, regimes, hours, and parameter variants.
- Minimum Track Record Length and prospective power analysis.
- Sensitivity surfaces, ablation studies, negative controls, and cost stress tests.

Method selection, assumptions, thresholds, and the complete model universe must be frozen in the protocol before confirmatory evaluation. No metric is a universal certificate of edge.

## Publication Units

1. **Protocol paper:** architecture and formal threat model for causal trading research.
2. **Methods paper:** false-promotion calibration on synthetic and controlled historical experiments.
3. **Prospective paper:** preregistered Shadow and Demo observations, including negative results.
4. **Research artifact:** datasets, manifests, software release, reproduction workflow, and discrepancy log.

## Canonical References

- Stanford University, *Doctoral Degrees, Dissertations & Dissertation Reading Committees*.
- White (2000), *A Reality Check for Data Snooping*.
- Bailey et al., *The Probability of Backtest Overfitting*.
- Bailey and Lopez de Prado, *The Deflated Sharpe Ratio*.
- Harvey, Liu, and Zhu (2016), *...and the Cross-Section of Expected Returns*.
- Wilkinson et al. (2016), *The FAIR Guiding Principles for Scientific Data Management and Stewardship*.

Full bibliographic records and persistent identifiers will be maintained in the future manuscript bibliography.

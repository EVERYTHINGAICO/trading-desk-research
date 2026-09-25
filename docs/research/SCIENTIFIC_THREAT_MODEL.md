# Scientific Threat Model

The protected asset is the validity of a research conclusion. A result is unsafe when a reasonable reader could interpret noise, leakage, dependence, or operational artifacts as evidence of edge.

## Threat Register

| ID | Threat | Failure mechanism | Required control | Detection evidence |
| --- | --- | --- | --- | --- |
| T01 | Look-ahead leakage | A feature or label uses information unavailable at decision time | Exchange, receipt, availability, and decision timestamps; as-of joins | Causality audit and synthetic leakage tests |
| T02 | Data snooping | Reused observations guide selection and later appear confirmatory | Experiment registry, locked test, complete model universe | Registry-to-result reconciliation |
| T03 | Multiple testing | The best of many variants appears significant by chance | Trial accounting, FDR, Reality Check/SPA, DSR | Family definition and corrected inference |
| T04 | Backtest overfitting | Parameters fit idiosyncratic paths | Purging, embargo, CPCV/PBO where assumptions permit | Stability and PBO report |
| T05 | Pseudoreplication | Correlated legs or symbols inflate sample size | Event-level unit and cluster/dependence model | Effective sample calculation |
| T06 | Survivorship bias | Delisted or failed assets disappear from the universe | Point-in-time universe and delisting ledger | Universe reconstruction report |
| T07 | Execution optimism | Mid-price fills, fixed costs, or ignored failures inflate return | Variable spread, slippage, latency, partial-fill and rejection model | Cost decomposition and stress envelope |
| T08 | Regime selection | Favorable windows are chosen after inspection | Preregistered boundaries and regime definitions | Boundary hash and sensitivity report |
| T09 | Attribution error | PnL is assigned to the wrong strategy or cycle | End-to-end immutable identity and reconciliation | Unattributed/conflicted event report |
| T10 | Missing-not-at-random data | Outages disproportionately remove adverse periods | Explicit missingness states and outage ledger | Missingness analysis and bounds |
| T11 | Researcher degrees of freedom | Metrics, exclusions, or thresholds change after outcomes | Frozen analysis plan and amendment history | Protocol/result diff |
| T12 | Reproduction drift | Dependencies, data, or exchange semantics change | Tagged software, locked environment, manifests and schemas | Independent reproduction report |
| T13 | Publication bias | Null and negative studies vanish | Terminal status required for every registration | Registry completeness audit |
| T14 | Operational contamination | Manual action changes an allegedly automated result | Actor/source fields and account reconciliation | Intervention ledger |

## Adversarial Review Questions

Every confirmatory report must answer:

1. What information could not have been known at the decision timestamp?
2. How many hypotheses, variants, symbols, windows, metrics, and exclusions were considered?
3. What is the effective number of independent observations?
4. Which result would have been reported if the sign were reversed?
5. Which assumptions most improve the result, and what happens when they are stressed?
6. Can the complete result be rebuilt without private judgment calls?
7. What evidence would falsify the claimed mechanism?
8. Did any human or agent inspect locked outcomes before the protocol was frozen?

## Residual Risk

Passing every control does not prove future profitability. Market adaptation, structural breaks, exchange changes, limited rare-event samples, and unknown unknowns remain. Reports must distinguish controlled threats from residual uncertainty.

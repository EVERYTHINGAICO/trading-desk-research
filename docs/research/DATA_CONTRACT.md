# Causal Research Data Contract

- Contract version: `causal-research-data-v1`
- Governance: `research-governance-v1`
- Time standard: UTC represented as RFC 3339 and Unix milliseconds
- Integrity algorithm: SHA-256

## Causal Clock Model

Every observation must distinguish four times:

1. `exchange_event_ms`: when the source says the event occurred.
2. `exchange_available_ms`: earliest documented publication time, if distinct.
3. `received_ms`: when the collector completed receipt.
4. `decision_ms`: when the research decision was committed.

An input is causally eligible only when its required availability time and `received_ms` are both less than or equal to `decision_ms`. Missing timestamps do not receive invented values; they produce an explicit unverifiable or unavailable state.

## Stable Identities

Records bind dataset, source, instrument, schema, strategy, configuration, experiment, event, and decision identities. IDs are immutable. Corrections create new records with `supersedes_record_id`; they never replace raw evidence.

## Quality Vocabulary

- `OBSERVED`: source value and required timestamps are present.
- `MISSING`: expected source value was unavailable.
- `STALE`: value arrived but exceeded the registered freshness bound.
- `UNVERIFIABLE`: causal availability cannot be established.
- `CORRECTED`: append-only correction linked to the prior record.
- `SYNTHETIC`: generated fixture or experiment data, never market evidence.

## Null Semantics

`null` means unavailable or inapplicable according to the accompanying quality and reason fields. It never means zero. Numeric units, precision, and transformations must be declared in the schema or data dictionary.

## Dataset Manifest

Every dataset snapshot conforms to [dataset-manifest-v1.schema.json](schemas/dataset-manifest-v1.schema.json) and binds:

- source and license;
- inclusive temporal boundaries;
- schema identifiers;
- files, byte sizes, media types, row counts, and SHA-256 hashes;
- known gaps, corrections, and exclusions;
- generating code commit and environment digest;
- privacy classification;
- detached signature metadata when published as confirmatory evidence.

The canonical bytes for hashing and signing are UTF-8 JSON with sorted keys, separators `,` and `:`, no insignificant whitespace, and the `signatures` array replaced by an empty array. A detached signature covers the SHA-256 digest of those bytes.

## Signature Policy

Design fixtures may be explicitly `UNSIGNED_DESIGN_FIXTURE`. E2+ evidence requires either:

- Sigstore keyless signature bundle with verified identity and transparency-log inclusion; or
- Ed25519 detached signature whose public key fingerprint is recorded in a governance decision.

A Git commit or plain hash provides integrity linkage but is not, by itself, an independent identity signature.

## Privacy Classes

- `PUBLIC`: safe and licensed for publication.
- `PUBLIC_SANITIZED`: transformed to remove account or operator identifiers.
- `RESTRICTED_REPRODUCIBLE`: available to approved validators under controls.
- `PRIVATE_OPERATIONAL`: credentials, raw account exports, private logs, linkage keys, and identifying data; never published.

## Canonical Reconstruction

The synthetic fixture [CANONICAL_EVENT_SYNTHETIC_V1.json](examples/CANONICAL_EVENT_SYNTHETIC_V1.json) demonstrates the contract. A reproducer can verify:

1. all feature inputs were received before `decision_ms`;
2. `return_1m = close / previous_close - 1 = 98 / 100 - 1 = -0.02`;
3. `relative_volume = volume / baseline_volume = 240 / 100 = 2.4`;
4. the declared rule requires `return_1m <= -0.015` and `relative_volume >= 2.0`;
5. both predicates are true, producing `WATCH`;
6. changing any observation after `decision_ms` cannot alter this frozen decision.

This fixture proves reconstructability of the contract only. It is not evidence for a trading strategy.

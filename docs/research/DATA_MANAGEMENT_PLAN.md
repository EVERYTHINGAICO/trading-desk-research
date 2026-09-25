# Research Data Management Plan

## Objectives

Research data must support causal reconstruction, independent verification, legal reuse, and long-term interpretation without publishing credentials or account-identifying information.

## Data Layers

| Layer | Contents | Mutability | Public status |
| --- | --- | --- | --- |
| L0 raw | Exact exchange responses and receipt metadata | Append-only | Sanitized subset where licensing permits |
| L1 normalized | Versioned canonical market records | Derived and immutable per release | Publishable dataset candidate |
| L2 features | As-of features with availability timestamps | Derived and immutable | Publish with provenance |
| L3 decisions | Signals, gates, frozen plans, rejection reasons | Append-only | Publish sanitized research records |
| L4 execution | Shadow/Demo orders, fills, protection and reconciliation | Append-only corrections | Aggregate or pseudonymized only |
| L5 analysis | Registered samples, metrics, manifests and figures | Rebuildable | Public research artifact |

## Required Provenance

Each record family must identify source, exchange timestamp, local receipt timestamp, availability timestamp, normalization version, timezone, units, symbol mapping, missing-data state, and content hash.

## Snapshot Manifest

Every published or confirmatory dataset must include:

- persistent dataset ID and semantic version;
- creation timestamp and responsible researcher;
- source and usage license;
- inclusive time boundaries;
- schema version;
- row counts and partitions;
- SHA-256 per file and manifest;
- known gaps, outages, delistings, and corrections;
- code commit used to construct it;
- relationship to superseded snapshots.

## Privacy and Security

Never publish API credentials, account IDs, chat identifiers, raw account exports, IP addresses, private operator logs, or linkage keys. Demo records must be minimized and pseudonymized. Public manifests may prove possession and integrity without exposing private source records.

## FAIR Alignment

- **Findable:** persistent identifiers, citation metadata, indexed releases.
- **Accessible:** documented protocol and controlled authentication where required.
- **Interoperable:** open formats, explicit schemas, UTC timestamps, stable vocabularies.
- **Reusable:** provenance, licenses, assumptions, quality flags, and versioned construction code.

## Retention and Corrections

Raw evidence is append-only. Corrections create new records and retain links to prior values. Public datasets retain metadata even if licensing or safety requires withdrawing data files.

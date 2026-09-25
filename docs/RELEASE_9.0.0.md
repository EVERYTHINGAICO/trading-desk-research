# Release 9.0.0 - Causal Waterfall v2

- `waterfall-forward-v1` remains preserved but is marked `INVALIDATED_LOOKAHEAD`.
- `waterfall-forward-v2` starts fresh prospective Forward Shadow under config SHA-256 `62b21fbae809b99ca60d54efc66f181b0915b768aa4b304dc7d669ba62cbc07d`.
- Same-bar fills/exits are impossible; pending fills and exits require later contiguous bars.
- Data gaps fail closed and leave open virtual legs unresolved without invented PnL.
- OI uses exchange-time/as-of availability with bounded 5m baseline.
- Nova deterministic validation and bound Helios audit gate activation.
- Helios authorized Forward Shadow only. Demo remains unauthorized until independent prospective gates pass.
- Dashboard and Lumen now report v2 only; v1 rows remain preserved for audit but no longer contribute current Waterfall metrics.

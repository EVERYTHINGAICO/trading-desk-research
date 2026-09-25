# Release 8.2.0 - Binance Demo cycle performance

- Imports terminal Binance order history alongside fills/income.
- Links entry and exit fills to exact position cycles when attribution is unambiguous.
- Assigns funding only when exactly one symbol cycle owns the event time.
- Persists `WIN`, `LOSS`, `FLAT`, `OPEN`, or `UNATTRIBUTED` cycle performance.
- Trusted stats exclude incomplete/ambiguous cycles and never use Shadow outcomes as Demo proxies.
- Generates Demo performance reports every 15 minutes.

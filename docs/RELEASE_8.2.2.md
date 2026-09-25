# Release 8.2.2 - Reymon dispatcher recovery

- Reymon uses the only thinking mode supported by its configured model: `off`.
- Failed agent starts no longer consume the rolling 24-hour successful-review quota.
- Quota starts from successful completion, not attempted start.
- Detector exports pending incident evidence into the agent workspace; Reymon does not need direct access to the Docker volume.
- Dispatcher uses headless code mode with explicit workspace and marks success only when Reymon appends a verified changelog entry.

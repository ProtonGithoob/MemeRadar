# Telegram alert fixture

`replay.json` is a redacted, credential-free `CandidateStateChanged` event
projected into a deterministic `ENTRY_READY` notification. It is consumed by
the Sprint 7.1 contract tests with the fixture notification adapter; no
Telegram endpoint or bot token is present.

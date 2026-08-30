# Historical caller-performance fixtures

These deterministic, synthetic records exercise the E5.4 provider-independent
historical social-call outcome seam without credentials or network access.

`replay.json` includes good, poor, rug-heavy, duplicated and insufficient-sample
callers. Market observations are event-time ordered only by the analyzer, so
the contract can replay them in a different delivery order. Risk observations
are explicit evidence; missing rug or liquidity-collapse evidence remains
unknown and is never counted as a clean outcome.

The records are not evidence of live authors, posts, tokens or performance. No
secrets, cookies, session state, wallet keys or transaction-signing material
belong in this directory.

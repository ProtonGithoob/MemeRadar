# Smart-money confluence fixtures

These redacted, deterministic records exercise the Phase 4 Sprint 4.3
application seam without provider credentials:

- `replay.json` contains three qualified wallets. Wallets ending in `12` and
  `13` share an observed intermediary ending in `15`; wallet `14` is an
  independent participant.
- `graph_stale.json` contains the same relationship shape outside its freshness
  window so the analyzer must publish `UNKNOWN` and withhold confluence.

The records are synthetic and are not evidence of a live wallet, provider, or
trade. `WalletRoundTrip` entries are completed FIFO slices used only to replay
entry, exit, confluence, and distribution calculations. No secrets, tokens,
cookies, wallet keys, or transaction-signing material belong in this directory.

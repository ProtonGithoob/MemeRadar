# Smart-wallet score replay fixtures

These files are synthetic, credential-free inputs for Phase 4 Sprint 4.2.
They represent Sprint 4.1 FIFO round-trip snapshots for a well-sampled wallet,
a tiny-sample wallet, incomplete/stale evidence and rolling-window boundary
cases. `penalties.json` contains explicit normalized manipulation penalties.

The fixture contract constructs provider-independent domain records before
calling `SmartWalletScorer`. No API key, access token, cookie, wallet secret or
provider session material is stored here. The high score is a deterministic
research recommendation only; it cannot mutate registry tiers or authorize
execution.

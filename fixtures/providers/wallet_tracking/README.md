# Wallet-tracking replay fixtures

These files are synthetic, redacted normalized evidence for Phase 4 Sprint
4.1. They contain two explicitly configured tracked wallets, duplicate source
delivery, FIFO-matched buys and sells, an unmatched sell, token creation time
and a normalized rug-outcome observation.

The fixtures contain no API keys, access tokens, cookies, wallet secrets or
provider session material. They are replayed through
`WalletTrackingAnalyzer`; provider adapters are responsible for producing the
same normalized `Observation` shapes when live access is available.

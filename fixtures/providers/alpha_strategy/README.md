# AlphaStrategy replay fixture

This directory contains synthetic, credential-free inputs for research
extension E6.1.  The replay covers a fully populated correlated feature
snapshot, sparse evidence, score clamping, a deterministic hard-risk block and
unknown risk.  Values are normalized feature components rather than provider
payloads; the strategy layer has no transport or persistence dependency.

`replay.json` intentionally contains no API keys, access tokens, cookies,
wallet secrets or other credentials.  It is used only by deterministic unit
and contract tests and never authorizes a real or paper order.

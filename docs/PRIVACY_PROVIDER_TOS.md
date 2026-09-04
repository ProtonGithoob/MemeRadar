# Privacy and provider-terms operating policy

Version: `privacy-provider-terms-v1`
Reviewed: 2026-09-01

This is the implementation policy for MemeRadar's analysis-only provider
boundaries. It does not replace a legal review, a provider agreement or a
jurisdiction-specific privacy notice.

## Free-first operating posture

The core stack is intentionally `FREE-FIRST`, `PROVIDER-INDEPENDENT` and
`KEYLESS-CORE-BOOT`: standard Solana RPC, DexScreener market/reference data,
local wallet/risk analysis and a disabled-or-local narrative seam can run
without paid credentials. Helius, Birdeye, authenticated RugCheck, social
analytics, external wallet enrichment, external narrative and Telegram are
optional. A provider's free tier or public endpoint is still subject to its
terms, quotas, availability and non-production guarantees.

## Data minimization

- Collect only public or explicitly authorized data needed for discovery,
  safety, correlation, replay and paper-trading analysis.
- Normalize provider responses at the adapter boundary and retain bounded
  provenance, timestamps, freshness and hashes rather than unnecessary raw
  response bodies.
- Do not collect private messages, contact lists, unrelated wallet history or
  credentials/secrets. Public wallet addresses and social identities are still handled
  as potentially sensitive identifiers.
- Keep exports redacted and bounded. Do not put API keys, cookies, bearer
  tokens, private keys or seed phrases in logs, fixtures, reports or commits.
- Honor a documented retention/deletion decision only through the controlled
  process in [`docs/DATA_RETENTION.md`](DATA_RETENTION.md); do not delete
  evidence invisibly during scoring or replay.

## Provider usage rules

| Source family | Allowed implementation posture | Evidence boundary |
| --- | --- | --- |
| Solana RPC/Helius | Official/public read APIs with configured limits | Standard RPC and Helius capabilities stay separate; unknown or conflicting data fails closed |
| DexScreener/Birdeye market data | DexScreener public API by default; Birdeye only when configured | Market values and pair selection retain provider/source/time provenance |
| DexScreener project metadata | Declared websites and social URLs supplied by the API | Metadata only; no social counts, sentiment, velocity or scraping |
| RugCheck and protocol adapters | Public contracts and independently reviewed definitions | Third-party claims corroborate deterministic checks |
| X/social | Official or otherwise compliant provider/API | No brittle scraping; bounded public identifiers and content only |
| External wallet intelligence | Contracted/read-only source when approved | Labels corroborate internal wallet scoring and never authorize entry |
| Telegram | Official Bot API through the existing HTTPS adapter | Delivery is downstream notification only |
| Jupiter/quote and execution | Disabled until the locked Phase 12 gate | No signing or submission authority in analysis/paper services |

The application never sends provider credentials to browser code. API keys,
bearer tokens and Telegram bot tokens are sent only as server-side headers by
the relevant adapter, and secret-bearing URLs are rejected. Ollama is a local
advisory narrative endpoint; its output is untrusted explanatory evidence and
cannot alter deterministic scoring, risk gates or execution modes.

Use official documentation and provider terms for current limits, attribution,
storage and redistribution requirements. Do not bypass authentication,
robots/access controls, rate limits, paywalls or terms. Do not copy upstream
code when its license is unclear or restrictive; independently implement
documented behavior and record the reuse decision.

## Review and blocker semantics

Provider credentials, network availability, contractual approval, legal review
and production retention approval are separate acceptance facts. Missing
optional configuration is `UNCONFIGURED_OPTIONAL`; configured but unreachable
or rate-limited access is `BLOCKED_EXTERNAL`, and unsupported capability is
`DEGRADED`. None of these states is fabricated as a PASS. Local fixtures prove
schema, redaction, rate-limit and fail-closed behavior only.

Provider disagreement becomes explicit `CONFLICTED` evidence. External wallet
labels, provider labels, social signals or healthy-provider states cannot
independently increase AlphaScore or authorize `ENTRY_READY`.

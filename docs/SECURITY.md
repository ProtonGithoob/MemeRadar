# Security and Trading Safety

## Security posture

MemeRadar analyzes adversarial assets and untrusted internet content. Treat all token metadata, social posts, URLs, provider payloads and LLM inputs as untrusted.

## Secrets

Never commit:
- API keys/tokens;
- X cookies/session state;
- Telegram bot token;
- private keys/seed phrases;
- signed transaction material that exposes secrets;
- database production passwords.

Use environment/secret-manager references. `.env.example` contains names and safe placeholders only. Logs and doctor commands redact credentials.

The Sprint 3.1 RugCheck integration is read-only. `RUGCHECK_API_KEY`, when needed, is sent only as an `Authorization: Bearer ...` header; the adapter rejects credential-bearing base URLs and does not include provider response bodies in errors. `make rugcheck-doctor` reports configuration presence rather than values and returns `BLOCKED_EXTERNAL` when no endpoint is configured. RugCheck severity and verification are advisory inputs: on-chain authority evidence remains the deterministic security authority, and provider verification is never treated as an endorsement.

The Sprint 5.1 social integration is also read-only. `SOCIAL_API_KEY` is sent
only as a Bearer header; credential-bearing URLs, cookies, browser session
state, fragments and unsupported links are rejected or ignored. The adapter
does not scrape, fetch post-linked URLs or expose a write endpoint. Post text,
tickers, links, author metrics and copied-text clusters are untrusted
corroborating evidence, never token identity proof or an execution override.
`make social-doctor` reports only presence/status metadata and never emits the
credential.

Sprint 5.2 trusted/KOL labels are explicit configuration and cannot be earned
from a burst of posts. Copied-text, spam, coordination and bot-like heuristics
are bounded advisory penalties; they do not assert account identity, common
control or malicious intent. Missing or stale social evidence cannot be
converted into a safe score, and neither social score can clear a deterministic
risk hard gate or enable execution.

Sprint 5.3 keeps the narrative seam strictly advisory. The `NarrativeAnalyzer`
gateway sanitizes untrusted social/token content (secret-shaped and
instruction/tool-shaped text is stripped before the model view), enforces
bounded evidence, character, token and cost budgets, caches validated strict
output by a deterministic content/config key, and converts timeout, malformed
output, provider outage or non-fresh evidence into a zero-confidence
unavailable snapshot with explicit reason codes. Narrative results carry no
risk-gate, scoring-weight or execution authority: `execution_eligible()` is
always false, deterministic analysis never waits on an LLM, and no narrative
value can clear a hard block or change an operating mode.

The E6.2 external-wallet seam is read-only corroboration. Labels and token
signals preserve source confidence, observed/expiry times, raw source IDs and
provenance, but external labels cannot replace the internal `SmartWalletScore`
or holder-graph actor clustering. Fresh agreement can add only a bounded
confidence bonus; stale labels are ignored for positive confidence and
disagreement is `CONFLICTED_EXTERNAL_WALLET_LABEL`. External security/rug
fields remain advisory evidence and cannot create or clear deterministic
on-chain hard gates. The fixture adapter never accesses the network, and
`make external-wallet-doctor` reports presence only and never emits secrets or
probes an unapproved URL. No live GMGN/CabalSpy adapter is enabled.

Core Sprint 6.1 feature windows are also analysis-only derived records. Their
stable IDs and persisted JSON values are replay identities, not authorization
tokens. The aggregator uses the correlation event-time boundary, invalidates
future evidence, preserves `UNKNOWN`/`STALE`/`CONFLICTED`/`INVALID` states and
does not fabricate missing families. Feature snapshots and external-wallet
corroboration carry `execution_eligible=false`; only later deterministic risk
and decision gates can evaluate eligibility, and the protected operating
modes remain unchanged.

## Operating modes

Default and mandatory until roadmap gates explicitly unlock:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Mode changes are validated, authenticated and audit logged. Auto execution cannot be enabled by model output or score transition.

## Wallet/signing isolation

When Phase 12 is implemented:
- analysis/API/web components do not receive signing secrets;
- signing occurs in a narrowly scoped execution runtime/interface;
- use least-privilege wallet with limited funds;
- retain SOL reserve for fees;
- never accept a private key through web query parameters/loggable CLI arguments;
- wipe/avoid unnecessary in-memory copies where practical;
- support rapid wallet revocation/rotation runbook.

## Execution guardrails

Required before live submission:
- system and execution kill switches clear;
- manual/auto mode policy permits action;
- candidate not blocked/cooldowned;
- critical risk evidence fresh;
- quote fresh;
- slippage <= configured max;
- price impact <= configured max;
- liquidity >= configured minimum;
- order size <= per-trade/per-token limits;
- portfolio exposure <= total limit;
- daily loss limit not breached;
- reserve remains after trade/fees;
- unique idempotency key not previously executed;
- expected mint/pair/route are verified.

Failure is fail-closed.

## LLM security

Social/token content may contain prompt injection. Narrative LLM integration must:
- place untrusted content in clearly delimited data fields;
- use strict structured output/schema validation;
- expose no tools capable of execution/trading/config mutation;
- never provide secrets to prompts;
- cap content size/token budget;
- reject/ignore instructions embedded inside posts/metadata;
- record provider/model/schema/config hash for audit;
- degrade gracefully on malformed output.

## SSRF / URL safety

Do not blindly fetch arbitrary token/social URLs from backend. Use allowlists or controlled egress and reject loopback, link-local, private-network and unsupported schemes when fetching is necessary.

## API / Web

- auth required for non-public/operator deployments;
- RBAC: viewer/operator/admin/execution roles;
- CSRF/session protections as applicable;
- secure cookies/headers;
- input validation and bounded pagination;
- rate limits for mutating/heavy endpoints;
- no secret echo in API errors;
- audit config, permission, kill-switch and execution actions.

The analysis-only manual mint endpoint requires `Authorization: Bearer <OPERATOR_API_TOKEN>` when `OPERATOR_API_TOKEN` is configured and fails closed with `503` when it is not configured. It accepts only a canonical Solana mint, never accepts signing material, and returns `execution_enabled: false`; the bearer value is compared in constant time and is not logged or returned.

## Supply chain

CI should include:
- dependency audit/scanning;
- secret scanning;
- pinned/locked dependencies;
- container scan when images exist;
- SBOM later in hardening phase;
- license review for externally reused repositories/code.

Never curl-and-execute arbitrary installer scripts in CI without review/pinning.

## Database

- least-privilege application roles in production;
- TLS where deployment requires;
- migrations use controlled credentials separate from runtime if practical;
- encrypted backups where applicable;
- audit tables append-oriented and protected from ordinary operator mutation;
- raw payload retention must avoid secrets/private user data not required for analysis.

## Threats to test

- malicious token metadata;
- spoofed ticker/mint mapping;
- social spam/coordinated shilling;
- creator-controlled wallet clusters;
- provider poisoning/conflicts;
- stale quotes/risk observations;
- replayed duplicate events/orders;
- prompt injection;
- API authorization bypass;
- leaked logs/config;
- Telegram command spoofing if command controls are later added;
- provider outage during an open position;
- partial transaction submission/unknown finality.

## Kill switch behavior

Global execution kill switch must prevent all new live submissions immediately while preserving monitoring/reconciliation. It must not blindly abandon already-submitted transactions. A separate analysis pause may stop ingestion if needed.

## Incident response baseline

For suspected credential compromise:
1. enable execution kill switch;
2. rotate/revoke exposed credentials/wallet as applicable;
3. preserve audit/log evidence;
4. reconcile open/pending transactions;
5. identify exposure source;
6. remediate and verify scans/tests before re-enable;
7. document incident and preventive action.

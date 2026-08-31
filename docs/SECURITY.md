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

Sprint 7.1 keeps Telegram behind the application-facing `NotificationPort`.
`TelegramNotificationAdapter` accepts only HTTPS base URLs, sends the bot
token only in the Telegram request path, and never includes it in `repr`,
fixtures, errors, logs or doctor output. Alert rendering uses an allow-list of
bounded fields, strips control characters and redacts secret-shaped values;
provider response bodies and raw error text are not persisted. Authentication,
schema and transport failures are classified safely, and rate limits defer
the leased notification outbox rather than causing a retry storm. A Telegram
notification cannot mutate candidates, clear risk, change modes, sign or
submit a transaction. The fixture adapter and doctor make the path testable
without credentials; live Telegram acceptance is `BLOCKED_EXTERNAL` when
configuration is absent.

Sprint 7.2 keeps the operator read surface strictly GET-only and behind the
application `ReadQueryPort`. Query DTOs reject unknown parameters, oversized
limits, malformed cursors and unbounded time windows. Responses are mapped
through strict models with bounded pages, no raw provider body/reference,
recursive secret-shaped redaction and a permanently false
`execution_eligible` flag where a view reports that field. A read of
`ENTRY_READY` is informational only: it cannot transition a candidate, send a
notification, mutate config, open a paper/live position, sign or submit a
transaction. Missing storage returns a safe `503` and empty non-persisted
catalogs remain empty; `UNKNOWN`, `STALE`, `CONFLICTED` and `INVALID` evidence
are preserved rather than upgraded to safe.

Core Sprint 6.1 feature windows are also analysis-only derived records. Their
stable IDs and persisted JSON values are replay identities, not authorization
tokens. The aggregator uses the correlation event-time boundary, invalidates
future evidence, preserves `UNKNOWN`/`STALE`/`CONFLICTED`/`INVALID` states and
does not fabricate missing families. Feature snapshots and external-wallet
corroboration carry `execution_eligible=false`; only later deterministic risk
and decision gates can evaluate eligibility, and the protected operating
modes remain unchanged.

Core Sprint 6.2 score recomputation is likewise a deterministic analysis
operation. The score ID, strategy identity and persisted config hash provide
replay/audit identity only; they are not permission grants. Repository-backed
recomputation preserves hard-risk references and fail-closed freshness, and a
blocked or unknown risk result cannot be upgraded by component weights,
penalties or score magnitude.

Core Sprint 6.3 `DecisionEngine` is a second deterministic safety boundary. It
requires candidate/score/risk identity and event-time validity, rechecks
critical risk freshness, hard blocks, configuration, confidence and the
explicit risk eligibility predicate, and maps unsafe evidence to
`RISK_REJECTED` where the lifecycle permits. Hysteresis/cooldown logic only
suppresses upward state churn; safety downgrades and risk escalation are not
suppressed. The engine can recommend `ENTRY_READY` but has no paper/live
position, wallet, signer, provider or execution dependency. Score-delta and
risk-escalation events are audit evidence, never permission grants; LLM and
external-wallet evidence remain advisory.

## Operating modes

Default and mandatory until roadmap gates explicitly unlock:

```text
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

Mode changes are validated, authenticated and audit logged. Auto execution cannot be enabled by model output or score transition.

Phase 9.1 paper execution preserves these modes as constructor invariants. The
engine accepts normalized quote data only, stores no signer or private-key
material, and cannot submit a transaction. Paper order/fill/cash records are
append-oriented and idempotent; stale/unknown/conflicted quote or risk input,
insufficient cash, reserve violations and position over-sells fail closed.
Paper replay uses pinned policy/config/fill-model identity and an event-time
boundary, and reconciliation reports mismatches without silently repairing
history. A paper result, `ENTRY_READY` decision or external label is not
execution permission.

The Sprint 9.2 exit engine preserves the same boundary: it accepts normalized
evidence only, emits an advisory `ExitEvaluation`, and has no persistence,
provider, signer or transaction-submission authority. External distribution
alerts can be recorded as corroboration but cannot force an exit alone. Exit
timeline persistence is append-only and retains before/after evidence
references for audit and replay. The protected modes remain unchanged.

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

Sprint 7.3 adds optional `VIEWER_API_TOKEN`, `ADMIN_API_TOKEN` and
`EXECUTION_API_TOKEN` credentials alongside the existing operator token.
Configured role tokens are unique, compared in constant time and converted to
role-only principals; values never enter audit actors, errors, logs or
responses. The `/v1/control` state/config reads require any configured role,
analysis pause/resume requires operator/admin, config mutation requires admin,
and execution-role access can only activate the restrictive execution
kill-switch. If any role token is configured, the existing read API also
requires a valid role bearer token; with no configured token, local development
read behavior remains unchanged.

Sprint 8.1 keeps the browser boundary credential-free: the web bundle receives
no API token, provider secret, cookie, wallet material or raw provider payload.
`NEXT_PUBLIC_REALTIME_URL`, when configured, is endpoint metadata only. Missing
stream configuration is rendered as `DISABLED`; connection errors are shown as
`RECONNECTING`/`DEGRADED` after bounded retries. Theme preference is local UI
state only. Score, risk, freshness and connection badges are explanatory
projections, and realtime messages cannot mutate decisions, controls, modes or
execution.

Sprint 8.2 keeps Radar/detail reads on the server side. `MEMERADAR_API_BASE_URL`
is preferred for internal server-to-API fetches, while the optional
`MEMERADAR_VIEWER_API_TOKEN` is read only by the gateway and sent only as a
Bearer header. The web bundle and rendered markup receive neither credential.
The gateway rejects malformed or unbounded records, maps timeout/auth/
unavailable/invalid responses without reading provider error bodies, and the
detail view renders only bounded normalized fields and allow-listed numeric
projections. Empty, unknown, stale, conflicted and invalid evidence remains
non-safe and visible; no UI read, chart, realtime message or advisory label
can authorize `ENTRY_READY`, alter modes, clear a kill switch, sign or submit.

Sprint 8.3 keeps wallet, provider, settings and audit reads behind that same
server boundary. Wallet scores and external labels remain corroborating
evidence; provider health is data-quality evidence; audit/config metadata is
not a permission grant. Settings render protected modes and a role matrix but
contain no mutation form, arbitrary configuration input, signing path or order
control. Gateway parsers reject malformed or unsafe records, display
projections allow-list fields and redact secret-shaped keys/values, and the
browser receives no viewer/control credential or raw provider response. Gate
P8 browser tests verify these boundaries against the keyless Compose runtime.

## E8.4 stream integrity and protocol safety

Stream transport is untrusted input. The provider-independent coordinator
stores cursor/gap/recovery state explicitly, bounds backfill ranges and
timeouts, and raises observable backpressure rather than dropping events.
Recovered events retain slot/signature, source, timestamps and parser/registry
provenance; successful fetch alone is not trusted verification. Unknown,
unverified or conflicting protocol identities fail closed.

Protocol routing requires the full `(program_id, discriminator_or_tag)` key;
Anchor and native identity rules are kept distinct. Production registry
definitions remain non-authoritative until independently verified. Processed
chain evidence retains its commitment state and a later reorg emits an
append-only revert correction, preserving the earlier observation.

Replay uses a pinned event-time manifest and excludes evidence after its
boundary. Stream health only reduces data quality/confidence and cannot raise
AlphaScore, clear a hard risk gate, authorize `ENTRY_READY`, sign or submit a
transaction. The stream doctor reports endpoint presence and local contract
status only; missing/unverified external access is `BLOCKED_EXTERNAL` and no
credential values are printed.

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

The current protected deployment starts with the execution kill switch active.
Its clear endpoint is deliberately rejected while `ANALYSIS_ONLY=true`,
`PAPER_TRADING=true`, `MANUAL_EXECUTION=false` and `AUTO_EXECUTION=false`.
Control config mutation is limited to validated allow-listed alert/decision
fields; attempts to mutate modes, credentials, provider URLs, database URLs or
wallet material fail validation and create no audit/config record.

## Incident response baseline

For suspected credential compromise:
1. enable execution kill switch;
2. rotate/revoke exposed credentials/wallet as applicable;
3. preserve audit/log evidence;
4. reconcile open/pending transactions;
5. identify exposure source;
6. remediate and verify scans/tests before re-enable;
7. document incident and preventive action.

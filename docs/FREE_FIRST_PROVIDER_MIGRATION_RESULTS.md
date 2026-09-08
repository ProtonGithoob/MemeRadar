# FREE-FIRST Provider Migration — Completion Report

Last updated: 2026-09-05

## Current status

The provider migration is implemented and verified. MemeRadar now has a
provider-neutral capability model and a small bounded composition layer. Core
read-only analysis can initialize without paid or keyed provider credentials.

The protected modes remain unchanged and enforced:

```env
ANALYSIS_ONLY=true
PAPER_TRADING=true
MANUAL_EXECUTION=false
AUTO_EXECUTION=false
```

This document is the durable handoff for the migration. Read it together with
the current `docs/STATUS.md` before starting follow-up work.

## Git checkpoint

- Branch at implementation completion: `main`
- Starting commit: `ba5de244152d2c45e678cd07d44265e67c2f4ee1`
- Provider migration implementation checkpoint: `4351475b504fd1ad82c698d10efabb0736ed1a86`
- Implementation checkpoint message: `docs: clean provider design whitespace`
- The documentation commit containing this report is the subsequent handoff
  checkpoint; use `git log -1` for its exact hash.

Important: the worktree contained unrelated, uncommitted frontend changes when
this report was written. They are intentionally not part of this migration and
must not be discarded with `git reset`, `git clean`, or equivalent commands.

## Completed implementation

### Capability and composition architecture

- Extended the existing capability model with chain RPC, enhanced metadata,
  transaction history, realtime stream, market snapshot/quote, pair discovery,
  social metadata/analytics, risk, wallet enrichment, narrative, and alert
  delivery capabilities.
- Added bounded, at-most-once fallback composition without a broad registry
  rewrite.
- Kept provider-specific HTTP payloads inside provider adapters.
- Preserved provenance, timestamps, freshness, and explicit unavailable or
  degraded states.

### Solana

- Added `SolanaRpcAdapter` for standard Solana JSON-RPC only.
- Supported standard reads used by MemeRadar, including health, account info,
  transactions, signatures, and blocks.
- Helius DAS/enhanced and realtime capabilities remain Helius-only. They are
  unavailable or degraded when Helius is not configured.
- Public RPC uses bounded timeout, retry/backoff, 429 handling,
  `Retry-After`, concurrency limits, circuit protection, and redacted errors.
- Public RPC is rate-limited and non-guaranteed; it is not represented as
  production-grade infrastructure.

### Market data and paper quotes

- Added `DexScreenerAdapter` as the default market, reference-quote, pair
  discovery, and social-metadata provider.
- DexScreener is not used as a substitute for transaction history, holder or
  wallet history, realtime blockchain streams, Helius DAS, security auditing,
  or social analytics.
- Pair selection is deterministic: Solana chain, matching token identity,
  valid positive price, valid liquidity, preferred quote asset, highest
  meaningful liquidity, newest pair creation, pair-address tie-break, and DEX
  tie-break.
- Paper quotes are normalized `QuoteSnapshot` reference prices. They retain
  provider, chain, mint, pair, base/quote semantics, price semantics,
  liquidity, observation time, pair creation time, freshness, and provenance.
- Legacy/custom quote configuration remains supported and is never silently
  replaced by DexScreener when an explicit custom route is selected.

### Risk, wallets, social, narrative, and alerts

- Local wallet and risk engines remain primary, including wallet tracking,
  scoring, holder graph, flow analysis, and token security.
- RugCheck public functionality is free-first; authenticated enrichment is
  optional.
- External wallet and social analytics providers remain enrichment-only.
- DexScreener metadata can provide declared websites and social links. Missing
  social analytics remains unavailable, never fabricated as zero.
- Added `OllamaNarrativeAdapter`. Ollama is advisory enrichment only and can be
  unavailable or explicitly disabled without blocking readiness.
- Telegram remains optional and server-side.
- No signing, private-key handling, live order submission, or safety bypass was
  added.

## Provider routing after migration

| Capability | Default route | Optional route or result when unavailable |
|---|---|---|
| `CHAIN_RPC` | Helius RPC when configured, otherwise Solana public RPC | Explicit unavailable/degraded |
| Helius enhanced/DAS | Helius only | Explicit unsupported/unavailable |
| `TRANSACTION_HISTORY` | Standard RPC where supported | Helius enhancement when configured |
| `REALTIME_STREAM` | Existing Helius stream seam | Explicit unavailable without stream provider |
| `MARKET_SNAPSHOT` / `MARKET_QUOTE` | DexScreener | Birdeye or explicit custom route |
| `PAIR_DISCOVERY` | DexScreener | Explicit unavailable |
| `RISK_SUMMARY` | Local deterministic analysis | Public/authenticated RugCheck enrichment |
| Wallet intelligence | Local MemeRadar engines | External wallet enrichment |
| Social metadata | DexScreener | Existing social enrichment |
| Social analytics | Existing external social provider | Explicit unavailable |
| Narrative | Ollama | Explicit external provider, then disabled |
| Alerts | Telegram when configured | Optional/unconfigured |

The implementation follows the documented [DexScreener API reference](https://docs.dexscreener.com/api/reference), standard [Solana JSON-RPC methods](https://solana.com/docs/rpc/http/gethealth), and Ollama's [`/api/generate`](https://docs.ollama.com/api/generate) and [`/api/tags`](https://docs.ollama.com/api/tags) endpoints.

## Configuration changes

`.env.example` now groups the configuration into CORE, SOLANA FREE-FIRST,
MARKET DATA FREE-FIRST, PAPER QUOTES, RISK, WALLET, SOCIAL, NARRATIVE,
TELEGRAM, AUTH, and PROTECTED MODES.

The important defaults are:

```env
SOLANA_RPC_URL=https://api.mainnet.solana.com
MARKET_DATA_PROVIDER=dexscreener
DEXSCREENER_API_URL=https://api.dexscreener.com
DEXSCREENER_API_KEY=
PAPER_QUOTE_PROVIDER=dexscreener
WALLET_INTELLIGENCE_PROVIDER=local
SOCIAL_METADATA_PROVIDER=dexscreener
NARRATIVE_PROVIDER=ollama
NARRATIVE_API_URL=http://host.docker.internal:11434
NARRATIVE_API_KEY=
NARRATIVE_MODEL=
```

Existing Helius, Birdeye, RugCheck, social, external-wallet, Telegram, paper
quote, Jupiter, and narrative environment variables remain supported through
compatibility aliases or deliberate legacy routing.

## Verification evidence

`make verify` passed with:

- Python: `879 passed`, `11 skipped`, `0 failed`
- Frontend: `45 passed`, `0 failed`
- Ruff, mypy, frontend lint/typecheck, Compose validation, migrations, secret
  scan, security review, and SBOM validation: passed
- One non-blocking deprecation warning

Additional targeted provider, routing, quote, pair-selection, configuration,
doctor, readiness, Ollama, Solana RPC, keyless-boot, and protected-mode tests
passed.

The isolated keyless acceptance environment passed:

```text
scripts/free_provider_doctor.py --no-network
status: PASS
reason: FREE_READ_ONLY_CORE_READY
CORE_FREE_READINESS: READY_FOR_FREE_READ_ONLY_SHADOW
```

With all optional credentials empty, local initialization, protected modes,
local wallet/risk engines, and the free provider composition remained valid.
`make paper-trading-doctor`, `make doctor`, and `make compose-config` also
passed. Ollama correctly reported `OPTIONAL_UNAVAILABLE` when no model was
configured.

Live public-provider acceptance was not claimed because sandbox outbound
network access could not complete the bounded live probe. Treat live endpoint
verification as `BLOCKED_EXTERNAL`, not as a deterministic implementation
failure.

## Local project lifecycle scripts

The local Compose stack can be managed from the repository root:

```bash
./scripts/start.sh
./scripts/status.sh
./scripts/stop.sh
```

Equivalent Make targets are `make start`, `make status`, and `make stop`.
`start.sh` rebuilds with `--remove-orphans`, enforces the protected mode
display, and waits for API liveness and readiness. `stop.sh` removes the
Compose containers/network but preserves the named PostgreSQL and Redis
volumes. `status.sh` reports all expected services plus API liveness,
readiness, web reachability, and the protected modes without printing secret
values.

Restart evidence on 2026-09-05:

```text
./scripts/stop.sh: PASS
./scripts/start.sh: PASS (API liveness/readiness)
./scripts/status.sh: DEGRADED (exit 1)
postgres, redis, api, worker, web: running
API liveness: PASS
API readiness: PASS
Web container: running
Web endpoint: FAIL (HTTP 500)
```

The current web response is caused by unrelated uncommitted frontend work in
the worktree: `positions.tsx` and `wallets.tsx` import `ProtectedShell`, but
the current `radar.tsx` does not export it. The lifecycle scripts did not edit
those files. Finish or revert that existing frontend work through its own
workflow, then rerun `./scripts/status.sh`; do not discard it while working on
the provider migration or lifecycle scripts.

## Remaining work

1. Run the live Solana public RPC and DexScreener doctors from a networked
   environment and record whether each is `PASS`, `RATE_LIMITED`,
   `BLOCKED_EXTERNAL`, or `DEGRADED`.
2. If enhanced metadata or realtime stream evidence is required, configure and
   separately validate Helius; do not treat it as required for free-core
   readiness.
3. Collect real read-only shadow samples using `make shadow-start` and validate
   freshness, thin liquidity, provider disagreement, volume quality, wallet
   evidence, and replay convergence.
4. Configure optional Birdeye, social analytics, external wallet, Ollama, or
   Telegram only when their enrichment is needed.
5. Review and separately commit the unrelated pending frontend work currently
   in the worktree before starting another frontend task.

The free stack is suitable for local analysis and read-only shadow preparation,
but public RPC and DexScreener data remain rate-limited external observations;
they do not prove real-world alpha or authorize live execution.

## New migration files

```text
packages/providers/src/memeradar_providers/composition.py
packages/providers/src/memeradar_providers/dexscreener.py
packages/providers/src/memeradar_providers/solana_rpc.py
scripts/dexscreener_doctor.py
scripts/free_provider_doctor.py
scripts/ollama_doctor.py
scripts/solana_rpc_doctor.py
fixtures/providers/dexscreener/token_pairs.json
fixtures/providers/ollama/generate.json
fixtures/providers/ollama/tags.json
fixtures/providers/solana_rpc/account_info.json
fixtures/providers/solana_rpc/block.json
fixtures/providers/solana_rpc/blocks.json
fixtures/providers/solana_rpc/health.json
fixtures/providers/solana_rpc/signatures.json
fixtures/providers/solana_rpc/transaction.json
tests/contract/test_contract_provider_composition.py
tests/contract/test_dexscreener_provider.py
tests/contract/test_ollama_narrative_provider.py
tests/contract/test_provider_capability_boundaries.py
tests/contract/test_solana_rpc_provider.py
tests/unit/test_config.py
tests/unit/test_dexscreener.py
tests/unit/test_free_provider_doctors.py
tests/unit/test_ollama_doctor.py
tests/unit/test_ollama_narrative.py
tests/unit/test_provider_composition.py
tests/unit/test_solana_rpc.py
Canonical follow-up references: `docs/PROVIDERS.md` and `docs/STATUS.md`.
```

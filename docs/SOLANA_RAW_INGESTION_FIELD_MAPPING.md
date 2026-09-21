# Solana Raw Ingestion Field Mapping

Status: implemented contract slice for the public `logsSubscribe` +
`getTransaction` source, 2026-09-20.

The implementation is keyless and read-only. It is wired through
`StreamIntegrityCoordinator` and the existing `CanonicalProtocolDecoder`; it
does not create a second discovery path or claim accepted live alpha evidence.

## Source fields

`logsSubscribe` notifications contain:

- `params.result.context.slot`;
- `params.result.value.signature`;
- `params.result.value.err`;
- `params.result.value.logs`;
- the WebSocket subscription identifier.

The subscription request carries the selected commitment, but Solana does not
repeat that commitment in each notification. The adapter must retain the
configured commitment as provenance and preserve processed/confirmed/finalized
semantics explicitly.

`getTransaction(signature, options)` can contain:

- `slot` and nullable `blockTime`;
- `transaction.signatures`;
- `transaction.message.accountKeys`;
- `transaction.message.instructions` with `programIdIndex`, account indexes,
  encoded instruction data and optional `stackHeight`;
- versioned-transaction address-table lookups and `meta.loadedAddresses`;
- `meta.err`, logs, inner instructions, balances and token balances;
- the transaction version.

## RawChainTransaction field matrix

| RawChainTransaction field | Required by contract | Public source | Transformation | UNKNOWN / failure case |
|---|---:|---|---|---|
| `chain` | yes | adapter configuration | fixed to `Chain.SOLANA` | never inferred from payload |
| `slot` | yes | `getTransaction.slot`; WS context slot is an observation cross-check | require non-negative integer; reject or record a slot conflict if values differ | transaction unavailable or malformed |
| `signature` | yes | `logsSubscribe.value.signature` and transaction signature list | canonical text; dedupe before HTTP fetch | malformed/missing signature |
| `event_index` | yes | transaction instruction order; inner-instruction parent/index when used | deterministic top-level/inner index namespace; one envelope per matching instruction | no matching protocol instruction |
| `program_id` | yes | `message.accountKeys[programIdIndex]`, or parsed instruction `programId` | resolve and validate canonical Solana address | invalid index, address-table resolution unavailable, malformed key |
| `discriminator_or_tag` | yes | instruction `data` after base58/base64 decode | Anchor: first 8 bytes; native: protocol-defined tag; retain normalized hex/int | unsupported encoding, too-short data, unverified protocol identity |
| `payload` | yes | WS logs plus raw/parsed transaction and metadata | bounded allow-listed mapping containing signature, slot, instruction accounts/data, logs, metadata references and protocol-specific decoded fields | raw evidence can be retained as UNKNOWN; never fabricate protocol fields |
| `occurred_at` | yes | `getTransaction.blockTime` | UTC timestamp with `event_time_source=blockTime` and `event_time_quality=EXACT` | missing or invalid `blockTime` fails closed; receipt time is never substituted |
| `observed_at` | yes | local receipt time of WS notification | UTC local clock immediately after notification parse | local clock failure |
| `ingested_at` | yes | local time after HTTP fetch and envelope construction | UTC local clock; must be >= `observed_at` | local clock failure/order violation |
| `transport` | yes | adapter identity | `solana-public-rpc` | never provider-inferred |
| `commitment` | yes | subscription configuration / fetch policy | map `processed`, `confirmed`, `finalized` to domain enum | unknown/missing policy is `UNKNOWN` |
| `event_schema_version` | yes | adapter/parser contract | current raw envelope schema version | unsupported transaction version or decoder schema |
| `token_id` | no | protocol-specific mint extracted from instruction accounts/metadata | canonical chain+mint UUID only after valid mint extraction | absent until protocol decoder proves mint |
| `candidate_id` | no | downstream persistence | normally unset at provider boundary | never synthesized from ticker/name |

## Current repository constraints

1. `RawChainTransaction.occurred_at` is non-nullable even though protocol
   observations allow nullable occurred time. This adapter obtains a block
   timestamp and fails closed when it is unavailable; it does not use receipt
   time as authoritative chain time.
2. `SolanaRpcAdapter.fetch_transaction()` currently keeps only a reduced
   `Observation` payload and does not expose instruction data, logs, inner
   instructions or transaction version. A raw source must extend this existing
   provider boundary rather than parse reduced observations downstream.
3. `CanonicalProtocolDecoder` routes only on the full
   `(program_id, discriminator_or_tag)` key and rejects unverified registry
   entries. A real transaction can prove transport and field availability
   while still correctly failing closed as `UNVERIFIED_PROTOCOL`.
4. Pump.fun `create`, `create_v2`, buy/sell variants and migration tags route
   only through the checked-in IDL pin. A genuine launch requires the
   authoritative create identity and payload decoding; no ticker/name may
   substitute for an exact mint.

## Implemented source boundary

`SolanaRawTransactionSource` subscribes to Pump.fun logs, deduplicates
signatures in a bounded in-memory window, fetches only launch-shaped
notifications, retries the normal indexing race three times, resolves parsed
and lookup-table account keys, and emits `RawChainTransaction` envelopes. The
worker uses this source when the database and Solana chain are enabled; source
events still pass through the existing cursor, gap, registry and early-runtime
path.

The bounded Pump.fun account mappings currently used are:

| Instruction | Mint account | User account | Token program account | Creator |
|---|---:|---:|---:|---|
| `create` | 0 | 7 | 9 | decoded from the instruction data |
| `create_v2` | 0 | 5 | 7 | decoded from the instruction data |
| legacy `buy` / `sell` | 2 | 6 | not mapped | not applicable |
| `buy_v2` / `buy_exact_quote_in_v2` / `sell_v2` | 1 | 13 | not mapped | not applicable |

The `create` and `create_v2` fields are decoded from the pinned local schema,
including name, symbol, URI, creator, mayhem mode, quote semantics and the
holder-reward flag where present. `create_v2` uses the official optional
remaining-account layout: quote mint at index 16, associated quote bonding
curve at 17 and quote token program at 18; missing or wrapped-SOL quote data
remains explicit SOL semantics. The token-program account is never mislabeled
as a creator.

## Pump.fun decoder pin

The local decoder uses no GitHub request at runtime:

- IDL source: [`pump.json`](https://github.com/pump-fun/pump-public-docs/blob/81091419e4457566469d4e2a27f64ed84d42419c/idl/pump.json)
- Creation docs: [`COIN_CREATION.md`](https://github.com/pump-fun/pump-public-docs/blob/81091419e4457566469d4e2a27f64ed84d42419c/docs/instructions/COIN_CREATION.md)
- upstream revision: `81091419e4457566469d4e2a27f64ed84d42419c`
- IDL SHA-256: `ffe966c42f1af41652ee753fe2f1e3f7cd4077d7e6f49faf3138959c8b56064b`
- local schema version: `pumpfun-idl-schema-v1`

Any mismatch is reported as `PROTOCOL_DRIFT_DETECTED` and is rejected before
authoritative canonical routing.

On 2026-09-20 a read-only finalized RPC probe fetched transaction
[`Vipr2GGwM9HfD8KJRwLGvcNXZ6AuCXeAERbDRrs2mQaocSVHC6WPsoSA9Bhjqt7NsRW1YZ7rLLUeZvPeRhypHsW`](https://explorer.solana.com/tx/Vipr2GGwM9HfD8KJRwLGvcNXZ6AuCXeAERbDRrs2mQaocSVHC6WPsoSA9Bhjqt7NsRW1YZ7rLLUeZvPeRhypHsW)
at slot `448814566`. Its parsed versioned transaction exposed expanded lookup
table keys, the Pump.fun program ID and a decoded inner
`buy_exact_quote_in_v2` tag. This verifies the public RPC field shape and
program identity only; it is not a launch sample or an alpha claim.

## Experimental acceptance boundary

The probe must separate these results:

- transport reachable and subscription accepted;
- transaction signature captured;
- HTTP transaction payload fetched and raw fields available;
- RawChainTransaction constructed;
- protocol identity verified;
- canonical decoder accepted;
- existing early runtime invoked and `DISCOVERED` persisted.

Only the last two stages can establish verified launch discovery. A public
RPC/WS response alone must not be reported as a live MemeRadar source.

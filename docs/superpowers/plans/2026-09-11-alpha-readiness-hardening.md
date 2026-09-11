# MemeRadar alpha-readiness hardening

## Scope

Close only demonstrated P0 gaps in the current `main` architecture. Keep the
existing canonical evidence, scoring/risk, Early Alpha, alert delivery, and
paper-ledger boundaries intact. Do not add external providers without a unique
verified data contract.

## Slices

1. Add failing tests for quote completeness, chain-specific fee reserves, and
   concurrent logical-position claiming.
2. Add the minimum domain/application/persistence changes, using database
   uniqueness for the durable claim and explicit `UNKNOWN` reason codes.
3. Add a bounded real-data inventory report that counts only persisted real
   evidence and preserves `INSUFFICIENT_SAMPLES` / `BLOCKED_EXTERNAL`.
4. Run focused tests, then the repository verification gates; update
   `docs/STATUS.md` with exact fresh evidence, blockers, modes, and SHA.

## Non-goals

- no second scorer, risk engine, lifecycle, Telegram pipeline, or provider
  metadata model;
- no live execution, signer, credentials, or fabricated real samples;
- no proprietary `solana-sniper-mcp` source or implementation reuse;
- no speculative Robinhood/X adapter without an available canonical source.

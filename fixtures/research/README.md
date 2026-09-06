# Research replay fixture

`replay_dataset.json` is a redacted, deterministic Phase 10.1 bundle. It
contains only normalized observations, provenance and a signal checkpoint; it
has no raw provider response, credential, wallet secret or network dependency.

Run it with:

```text
make replay-dataset
```

The command prints a canonical JSON artifact containing event-time feature
reconstruction, future-only outcome labels, a dataset digest and the four
protected MemeRadar modes. It is advisory research output and cannot submit or
sign a transaction.

`opportunity_case_studies.json` is a bounded `SYNTHETIC_REDACTED` research
bundle. It covers the required winner and negative-control cohorts across
Solana, BNB and read-only Robinhood. Its decision-time evidence is the
canonical replay dataset; the 2x/5x/10x/20x/50x/100x fields are kept in the
separate `future_outcome_targets` section and are never replay features.
Historical provider timestamps are not asserted by this fixture, so each case
uses `historical_status: UNKNOWN` and marks unavailable evidence explicitly.
Run the same canonical replay path with:

```text
make replay-dataset REPLAY_INPUT=fixtures/research/opportunity_case_studies.json
```

The research report is generated with:

```text
make opportunity-research
```

The checked-in report remains `INSUFFICIENT_SAMPLES` for this seven-case
synthetic bundle. It reports the split, feature-family ablation shape,
chain/archetype/age/market-cap/regime segments and explicit non-promotion;
it is not evidence for production weight changes.

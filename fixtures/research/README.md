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

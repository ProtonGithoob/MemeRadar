# Social intelligence fixtures

These redacted, deterministic records exercise the Phase 5 Sprint 5.2
provider-independent author-trust and social-velocity seam without credentials
or network access:

- `replay.json` contains explicit KOL/trusted/blocked configuration, an
  unlisted author, 1m/5m/15m activity, engagement metrics, copied text,
  explicit spam probability and an exact duplicate delivery.
- `future_stale.json` contains future and stale evidence that must not produce
  a fresh positive score.

The records are synthetic. They are not evidence of live authors, accounts,
posts or token behavior. Author labels are explicit configuration, never
promoted from activity; coordination is only a bounded copied-text diagnostic,
not a claim of common control or bot identity. No secrets, cookies, session
state or signing material belong in this directory.

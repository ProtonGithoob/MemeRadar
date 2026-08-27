# Social/X provider fixtures

These redacted, deterministic records exercise the Phase 5 Sprint 5.1
read-only social provider seam without credentials or network access:

- `search.json` is a paginated search response with one exact duplicate post,
  two normalized copied-text posts, mint/ticker/link extraction, and metrics.
- `health.json` is the minimal successful health envelope used by replay and
  doctor contract tests.

The records are synthetic and are not evidence of a live account, post,
provider, or token. The adapter must preserve post and author provenance,
normalize timestamps and metrics, reject unsafe links, and never use cookies,
browser sessions, or arbitrary write endpoints. No secrets belong in this
directory.

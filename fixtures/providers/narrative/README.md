# Narrative provider fixtures

These redacted, deterministic records exercise the optional Phase 5 Sprint
5.3 narrative seam without an LLM credential or network access:

- `valid.json` is a strict structured-output response with bounded narrative,
  novelty, organic/promotional probabilities, sentiment uncertainty, usage,
  schema and evidence references.
- `malformed.json` intentionally omits required structured fields so the
  application gateway must return an unavailable, zero-confidence fallback.
- `injection.json` is untrusted social content containing instruction-like
  text. It is data only and must be delimited/redacted before any provider
  call.

The records are synthetic and are not evidence of a live provider, model,
account or token. No secret, tool call, execution instruction or live-money
permission belongs in this directory.

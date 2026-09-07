# Token-security enrichment fixtures

These are repository-owned, synthetic response shapes for the optional
read-only GoPlus-style adapter. They contain no credentials and do not claim
live provider availability. The adapter normalizes only bounded high-value
fields; omitted fields are `UNKNOWN`.

The implementation independently reimplements the response-boundary behavior.
No third-party code is vendored or copied. GoPlus-style field names are used
as an interoperability contract, while local deterministic authority checks
remain authoritative.

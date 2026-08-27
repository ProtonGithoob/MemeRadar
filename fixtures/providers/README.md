# Provider fixtures

Provider fixtures are synthetic or redacted captures used by adapter contract tests. Every committed fixture must include:

- provider and capability;
- endpoint without credentials;
- capture timestamp;
- provider schema version and parser version;
- `redacted: true` metadata;
- normalized output expectations where the adapter contract requires them.

Use `memeradar_providers.fixtures.FixtureRecorder` for exports. It recursively redacts credential-shaped keys and URL/header values before a fixture can be written. Public Solana mint/pool addresses are data, not credentials, and are retained so canonical identity validation remains realistic.

Raw protocol fixtures may intentionally keep the provider's response envelope at the JSON root so an injected HTTP transport can replay them without a wrapper. In that case, the required fixture metadata is recorded in the provider-specific fixture README and contract test; the response itself must remain synthetic or redacted. The Helius RPC metadata and replay contract are in `fixtures/providers/helius/README.md`.

Live captures are never required for keyless CI and must not be committed if redaction is uncertain.

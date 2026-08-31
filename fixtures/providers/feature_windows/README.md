# Feature-window replay fixture

This directory contains a credential-free, synthetic replay for Phase 6
Sprint 6.1. `replay.json` represents normalized correlation output at one
event-time boundary plus the already-derived risk and holder evidence needed
to populate all feature families.

The expected windows are exactly `1m`, `5m` and `15m`. The fixture is redacted
and contains no provider credentials or live endpoint data. Replaying the same
event-time evidence in reverse delivery order must produce the same stable
feature-snapshot IDs, values, provenance, quality and config identity.

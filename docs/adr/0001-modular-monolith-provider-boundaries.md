# ADR 0001: modular monolith with provider-independent ports

- Status: Accepted
- Date: 2026-09-01

## Context

MemeRadar combines low-latency provider observations, deterministic risk and
score projections, persistence, research replay and an operator API. Provider
SDKs and transport failures change independently of business rules, while
replay must remain deterministic without network access.

## Decision

Keep the product as a modular monolith with explicit domain, application,
provider, persistence and telemetry boundaries. Provider SDKs stay in adapter
packages and implement application-facing ports. The domain and application
layers consume normalized contracts, provenance, freshness and reason codes;
they do not import a provider SDK, web framework or persistence implementation.
Live, backfill and replay chain observations converge through the canonical
decoder/normalizer contract.

## Consequences

This keeps local fixtures and replay provider-free, makes provider replacement
bounded, and supports later extraction only when measurement justifies it. It
requires explicit adapters, translation tests and some composition code. A
provider outage or disagreement is visible evidence and cannot be hidden by a
fallback that changes business semantics.

## Alternatives rejected

- A provider SDK directly in the domain would couple scoring and replay to
  external payload types.
- Immediate microservices or Rust extraction would add operational cost before
  the E11.1 latency evidence justifies it.
- Copying third-party repository code without a compatible license review is
  not an acceptable shortcut.

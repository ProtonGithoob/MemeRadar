# Architecture decision records

These records capture material decisions that constrain implementation. They
complement, rather than replace, [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
and the protected operating policy.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-modular-monolith-provider-boundaries.md) | Modular monolith with provider-independent ports | Accepted |
| [0002](0002-analysis-only-paper-first.md) | Analysis-only and paper-first execution boundary | Accepted |

New records should state the context, decision, consequences, alternatives and
the safety/replay impact. Reversals require a new ADR rather than silently
rewriting historical rationale.

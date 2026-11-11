# Next actions

1. Define the bounded social-call/caller, paper portfolio/quote, and
   pre-identity capture contracts before wiring those currently unconnected
   capabilities.
2. Run the changed workflow on a connected hosted runner; do not infer hosted
   acceptance from local `make verify`.
3. Provide isolated PostgreSQL or an authorized Docker daemon; migrate and run
   integration tests only against that disposable database.
4. Restore npm registry access, review compatible security updates, and rerun
   the production audit and web build.
5. Run browser E2E against the exact production build and exercise credential
   containment/accessibility checks.
6. Accept required read-only providers with bounded live probes and provenance.
7. Keep exact Pump.fun replay, copyability and `ALPHA_VALIDATED` blocked until
   verified protocol evidence and mature independent chronological outcomes
   exist.

Detailed causes and closure evidence are in
[REMAINING_BLOCKERS.md](REMAINING_BLOCKERS.md).

# Forward-shadow live acceptance — 2026-09-24

## Result

`BLOCKED_EXTERNAL`: the repository-supported Compose run could not reach the
host Docker socket. No PostgreSQL rows were inspected or counted in this
session, so no live database outcome claim is made.

## Evidence collected

| Check | Result |
| --- | --- |
| Repository | `/home/ubra/codex/MemeRadar`, local `main` |
| Starting HEAD | `f3f706ae8b275c9ad30b551e0cdae7023b416de5` |
| Compose config | PASS (`make compose-config`) |
| Migration graph | PASS (`0012_stream_gap_diagnostics` head; 27 tables in static check) |
| Database URL | not configured in the host environment |
| `scripts/doctor.py` | PASS for development/keyless mode; database/Redis not required |
| `scripts/stream_integrity_doctor.py` | `BLOCKED_EXTERNAL` because stream/backfill URLs are absent |
| Compose start | BLOCKED: `permission denied while trying to connect to the Docker API at unix:///var/run/docker.sock` |
| Local verification | PASS: `1463 passed, 21 skipped, 7 warnings`; coverage `79%` |
| Live DB row verification | NOT RUN; Docker access is required |
| Worker restart/idempotency proof | NOT RUN; Docker access is required |

The failure occurred before container creation, so it did not change project
data or protected modes. This is a host/runtime permission blocker, not a
provider success signal.

## Prior checked-in forward evidence (not a replacement for this run)

The checked-in artifact `artifacts/research/pumpfun-forward/report.json`
records `1278` launches, `124` first Dex observations, `121`
MemeRadar-before-Dex leads, `995` outcomes due at `1h`, and no matured
`6h/24h/72h/7d` outcomes. It reports `OUTCOME_TRACKING_OPERATIONAL=YES`,
`OUTCOME_STATUS=INSUFFICIENT_SAMPLES`, and `0` measured `2x/5x/10x` labels.
Those rows were produced by the earlier bounded run and are not re-counted as
a fresh PostgreSQL acceptance in this checkpoint.

## Acceptance interpretation

- The forward worker and exact horizon code already exist and remain the
  owner for launch/market/feature/decision/outcome projections.
- Missing or immature horizons remain unknown/not-yet-matured; this report
  does not zero-fill them.
- Re-run the existing Compose stack, migration target, worker, and restart
  comparison when Docker access is available. No second database is needed.

"""Bounded, read-only Pump.fun launch acceptance through MemeRadar."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import AsyncIterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _source_root in (
    ROOT / "packages" / "persistence" / "src",
    ROOT / "apps" / "worker" / "src",
):
    if str(_source_root) not in sys.path:
        sys.path.insert(0, str(_source_root))
from scripts.doctor_support import configure_paths  # noqa: E402

configure_paths(ROOT)

from memeradar_application.config import Settings  # noqa: E402
from memeradar_application.early_benchmark import DexScreenerBenchmarkBuilder  # noqa: E402
from memeradar_application.early_runtime import (  # noqa: E402
    EarlyRuntimeResult,
    EarlyRuntimeService,
)
from memeradar_application.early_worker import EarlyRuntimeStreamWorker  # noqa: E402
from memeradar_application.provider_contracts import (  # noqa: E402
    MarketDataRequest,
    ProviderRequestContext,
)
from memeradar_application.stream_integrity import (  # noqa: E402
    RawChainTransaction,
    StreamIntegrityCoordinator,
)
from memeradar_domain import (  # noqa: E402
    Chain,
    CommitmentState,
    NormalizedChainEvent,
    Provenance,
    TokenIdentity,
)
from memeradar_persistence import (  # noqa: E402
    ObservationRow,
    SqlAlchemyStreamStateStore,
    SqlAlchemyUnitOfWork,
    create_database_engine,
)
from memeradar_providers.composition import build_provider_bundle  # noqa: E402
from memeradar_providers.protocol_registry import (  # noqa: E402
    DEFAULT_PROTOCOL_REGISTRY,
    CanonicalProtocolDecoder,
)
from memeradar_providers.pump_fun_idl import (  # noqa: E402
    PUMP_FUN_CREATION_DOC_SOURCE,
    PUMP_FUN_IDL_REVISION,
    PUMP_FUN_IDL_SHA256,
    PUMP_FUN_IDL_SOURCE,
    PUMP_FUN_LOCAL_SCHEMA_VERSION,
)
from memeradar_providers.solana_raw_stream import (  # noqa: E402
    SOLANA_PUBLIC_WEBSOCKET_URL,
    SolanaRawTransactionSource,
)
from memeradar_worker.main import _BoundRuntimeRepositories  # noqa: E402

EXPECTED_PROTECTED_MODES = {
    "ANALYSIS_ONLY": True,
    "PAPER_TRADING": True,
    "MANUAL_EXECUTION": False,
    "AUTO_EXECUTION": False,
}


def validate_protected_modes(values: Mapping[str, object]) -> None:
    for name, expected in EXPECTED_PROTECTED_MODES.items():
        if values.get(name) is not expected:
            raise ValueError(f"{name} must remain {str(expected).lower()}")


def _value(source: object, field: str, default: object = None) -> object:
    if isinstance(source, Mapping):
        return source.get(field, default)
    return getattr(source, field, default)


def _timestamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def _payload(source: object) -> Mapping[str, object]:
    value = _value(source, "payload", {})
    return value if isinstance(value, Mapping) else {}


def build_acceptance_record(
    *,
    raw_event: object | None,
    canonical_decode: str,
    normalized_launch: str,
    discovered_persisted: str,
    discovered_at: datetime | None,
    dex_first_observation_at: datetime | None,
    dex_lookup_status: str,
) -> dict[str, object]:
    """Build the small JSON proof record without changing decision thresholds."""

    payload = _payload(raw_event) if raw_event is not None else {}
    instruction_type = payload.get("instruction_type", payload.get("instruction_name"))
    raw_status = "PASS" if raw_event is not None else "UNKNOWN"
    gates_pass = all(
        value == "PASS"
        for value in (raw_status, canonical_decode, normalized_launch, discovered_persisted)
    )
    return {
        "PUMPFUN_IDL_PINNED": {
            "status": "PASS",
            "source": PUMP_FUN_IDL_SOURCE,
            "creation_docs": PUMP_FUN_CREATION_DOC_SOURCE,
            "revision": PUMP_FUN_IDL_REVISION,
            "sha256": PUMP_FUN_IDL_SHA256,
            "local_schema_version": PUMP_FUN_LOCAL_SCHEMA_VERSION,
        },
        "REAL_CREATE_OBSERVED": "PASS" if instruction_type == "create" else "NO",
        "REAL_CREATE_V2_OBSERVED": "PASS" if instruction_type == "create_v2" else "NO",
        "REAL_LAUNCH_DECODED": normalized_launch,
        "DISCOVERED_PERSISTED": discovered_persisted,
        "DEXSCREENER_FIRST_OBSERVATION": dex_lookup_status,
        "LIVE_SHADOW_OPERATIONAL": "PASS" if gates_pass else "BLOCKED_EXTERNAL",
        "REAL_WORLD_ALPHA_VALIDATED": "NO",
        "RawChainTransaction": raw_status,
        "canonical_decode": canonical_decode,
        "normalized_launch": normalized_launch,
        "signature": _value(raw_event, "signature"),
        "slot": _value(raw_event, "slot"),
        "program_id": _value(raw_event, "program_id"),
        "discriminator": _value(raw_event, "discriminator_or_tag"),
        "instruction_type": instruction_type,
        "mint": payload.get("mint_address", payload.get("mint")),
        "creator": payload.get("creator"),
        "user": payload.get("user"),
        "name": payload.get("name"),
        "symbol": payload.get("symbol"),
        "provider_observed_at": payload.get("provider_observed_at"),
        "memeradar_ingested_at": payload.get("memeradar_ingested_at"),
        "MemeRadar_discovered_at": _timestamp(discovered_at),
        "DexScreener_first_successful_observation_at": _timestamp(
            dex_first_observation_at
        ),
        "dexscreener_status": dex_lookup_status,
    }


async def _discovered_snapshot(
    engine: Any,
    token_id: object,
) -> Mapping[str, object] | None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(ObservationRow).where(
                    ObservationRow.token_id == token_id,
                    ObservationRow.kind == "early.stage_snapshot",
                )
            )
        ).all()
    for row in rows:
        if row.normalized_payload.get("state") == "DISCOVERED":
            return row.normalized_payload
    return None


async def _dexscreener_lookup(
    provider_bundle: Any,
    event: NormalizedChainEvent,
) -> tuple[datetime | None, str, tuple[Mapping[str, object], ...], tuple[Provenance, ...]]:
    payload = event.normalized_payload
    mint = payload.get("mint_address", payload.get("mint"))
    if not isinstance(mint, str) or event.token_id is None:
        return None, "UNKNOWN", (), ()
    token_program = payload.get("token_program", "spl-token")
    token = TokenIdentity(
        id=event.token_id,
        chain=Chain.SOLANA,
        mint_address=mint,
        token_program=str(token_program),
    )
    provider_bundle.dexscreener.register_token(token)
    now = datetime.now(UTC)
    context = ProviderRequestContext(
        correlation_id=f"pumpfun-dexscreener:{event.signature}",
        requested_at=now,
        deadline_at=now + timedelta(seconds=10),
    )
    try:
        observations = await provider_bundle.dexscreener.snapshot(
            MarketDataRequest(context=context, token_ids=(token.id,))
        )
    except Exception:
        return None, "UNKNOWN", (), ()
    rows: list[Mapping[str, object]] = []
    provenance: list[Provenance] = []
    for observation in observations:
        observation_payload = observation.normalized_payload
        if observation_payload.get("mint_address") != mint:
            continue
        if observation_payload.get("pair_address") is None:
            continue
        rows.append(
            {
                "chain": "solana",
                "mint_address": mint,
                "observed_at": observation.observed_at,
                "event_type": "first_pair",
                "market_cap": observation_payload.get("market_cap"),
                "evidence_ref": observation.provenance.source_id,
            }
        )
        provenance.append(observation.provenance)
    if not rows:
        return None, "UNKNOWN", (), tuple(provenance)
    first = min(rows, key=lambda row: row["observed_at"])
    return first["observed_at"], "PASS", tuple(rows), tuple(provenance)


async def run_acceptance(
    timeout_seconds: float,
    output_path: Path | None = None,
) -> dict[str, object]:
    settings = Settings.from_env()
    modes = {
        "ANALYSIS_ONLY": settings.analysis_only,
        "PAPER_TRADING": settings.paper_trading,
        "MANUAL_EXECUTION": settings.manual_execution,
        "AUTO_EXECUTION": settings.auto_execution,
    }
    validate_protected_modes(modes)
    base = build_acceptance_record(
        raw_event=None,
        canonical_decode="UNKNOWN",
        normalized_launch="UNKNOWN",
        discovered_persisted="UNKNOWN",
        discovered_at=None,
        dex_first_observation_at=None,
        dex_lookup_status="UNKNOWN",
    )
    base.update({"started_at": datetime.now(UTC).isoformat(), "timeout_seconds": timeout_seconds})
    base["protected_modes"] = modes
    if not settings.database_url:
        base["blocker"] = "DATABASE_URL is not configured; durable DISCOVERED proof is unavailable"
        return _write_record(base, output_path)

    stop_event = asyncio.Event()
    provider_bundle = build_provider_bundle(settings)
    source = SolanaRawTransactionSource(
        provider_bundle.solana_rpc,
        websocket_url=settings.solana_stream_url or SOLANA_PUBLIC_WEBSOCKET_URL,
        commitment=CommitmentState.CONFIRMED,
        stop_event=stop_event,
    )
    engine = create_database_engine(settings.database_url)
    stores = _BoundRuntimeRepositories()
    runtime = EarlyRuntimeService(
        observation_store=stores,
        candidate_store=stores,
        feature_store=stores,
        risk_store=stores,
        score_store=stores,
        outbox_store=stores,
    )
    coordinator = StreamIntegrityCoordinator(
        chain=Chain.SOLANA,
        transport="solana-raw-stream",
        stream_id="pumpfun-live-acceptance-v1",
        decoder=CanonicalProtocolDecoder(DEFAULT_PROTOCOL_REGISTRY),
        state_store=SqlAlchemyStreamStateStore(engine),
        slot_continuity_expected=False,
    )
    current_raw: RawChainTransaction | None = None
    first: dict[str, object] = {}

    async def observed_source() -> AsyncIterable[RawChainTransaction]:
        nonlocal current_raw
        async for raw in source:
            current_raw = raw
            yield raw

    async def process_event(event: NormalizedChainEvent, *, stream_gap: bool) -> EarlyRuntimeResult:
        async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
            stores.bind(unit_of_work)
            try:
                result = await runtime.process(event, stream_gap=stream_gap)
                await unit_of_work.commit()
            finally:
                stores.clear()
        if event.event_type != "launch":
            return result
        discovered = await _discovered_snapshot(engine, event.token_id)
        dex_at, dex_status, dex_rows, dex_provenance = await _dexscreener_lookup(
            provider_bundle, event
        )
        mint = event.normalized_payload.get("mint_address", event.normalized_payload.get("mint"))
        if not isinstance(mint, str):
            return result
        token = TokenIdentity(
            id=event.token_id,
            chain=Chain.SOLANA,
            mint_address=mint,
            token_program=str(event.normalized_payload.get("token_program", "spl-token")),
        )
        benchmark = DexScreenerBenchmarkBuilder().measure(
            token,
            stage_snapshots={} if discovered is None else {"DISCOVERED": discovered},
            dexscreener_observations=dex_rows,
            provenance=dex_provenance,
        )
        first.update(
            record=build_acceptance_record(
                raw_event=current_raw,
                canonical_decode="PASS",
                normalized_launch="PASS",
                discovered_persisted="PASS" if discovered is not None else "FAIL",
                discovered_at=result.candidate.discovered_at,
                dex_first_observation_at=dex_at,
                dex_lookup_status=dex_status,
            ),
            benchmark=benchmark.to_mapping(),
        )
        stop_event.set()
        return result

    stream_error: str | None = None
    try:
        await asyncio.wait_for(
            EarlyRuntimeStreamWorker(coordinator, process_event).run(
                observed_source(),
                stop_event=stop_event,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        stream_error = "BOUNDED_TIMEOUT_NO_VERIFIED_LAUNCH"
    except Exception as exc:  # bounded acceptance reports provider blockers as evidence
        detail = str(exc).splitlines()[0][:240]
        stream_error = f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
    finally:
        await source.aclose()
        await provider_bundle.aclose()
        await engine.dispose()
    if first:
        record = dict(first["record"])
        record.update({"benchmark": first["benchmark"], "protected_modes": modes})
    else:
        record = dict(base)
        record["protected_modes"] = modes
    if stream_error is not None:
        record["blocker"] = stream_error
    return _write_record(record, output_path)


def _write_record(record: dict[str, object], output_path: Path | None) -> dict[str, object]:
    if output_path is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        output_path = Path("artifacts/research/pumpfun-live") / f"{stamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record["artifact_path"] = str(output_path)
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 5 <= args.timeout_seconds <= 900:
        parser.error("--timeout-seconds must be between 5 and 900")
    record = asyncio.run(run_acceptance(args.timeout_seconds, args.output))
    print(json.dumps(record, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

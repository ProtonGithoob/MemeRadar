"""Persist point-in-time wallet profiles and read them back for live decisions.

Profiles are append-only ``wallet.profile`` observations keyed by wallet and
``as_of``.  A live decision at time T reads, per buyer, the latest profile
with ``as_of <= T`` -- never a profile computed later -- so live features obey
the same no-lookahead rule as the research backtest.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from memeradar_application.wallet_intelligence import WALLET_PROFILE_VERSION, WalletProfile
from memeradar_domain import Observation, Provenance, QualityState
from memeradar_persistence import ObservationRow, SqlAlchemyUnitOfWork

PROFILE_KIND = "wallet.profile"
SIGNAL_FEATURES_KIND = "wallet.signal_features"


def profile_observation(profile: WalletProfile) -> Observation:
    source_id = f"wallet:profile:{profile.wallet}:{int(profile.as_of.timestamp())}"
    return Observation(
        id=uuid5(NAMESPACE_URL, f"memeradar:{PROFILE_KIND}:{source_id}"),
        kind=PROFILE_KIND,
        provenance=Provenance(
            provider="memeradar.reverse-wallet",
            source_id=source_id,
            observed_at=profile.as_of,
            parser_version=WALLET_PROFILE_VERSION,
        ),
        occurred_at=profile.as_of,
        observed_at=profile.as_of,
        ingested_at=profile.as_of,
        quality_state=QualityState.FRESH,
        normalized_payload={"wallet": profile.wallet, **profile.to_payload()},
    )


async def persist_profiles(engine: AsyncEngine, profiles: Iterable[WalletProfile]) -> int:
    count = 0
    async with SqlAlchemyUnitOfWork(engine) as unit_of_work:
        for profile in profiles:
            await unit_of_work.observations.add(profile_observation(profile))
            count += 1
        await unit_of_work.commit()
    return count


async def load_profile_categories(
    engine: AsyncEngine, wallets: Sequence[str], *, as_of: datetime
) -> dict[str, tuple[str, ...]]:
    """Latest categories per wallet from profiles computed at or before ``as_of``."""

    wanted = list(dict.fromkeys(wallets))[:500]
    if not wanted:
        return {}
    factory = async_sessionmaker(engine, expire_on_commit=False)
    wallet_field = ObservationRow.normalized_payload["wallet"].as_string()
    async with factory() as session:
        rows = (
            await session.scalars(
                select(ObservationRow)
                .where(
                    ObservationRow.kind == PROFILE_KIND,
                    ObservationRow.observed_at <= as_of,
                    wallet_field.in_(wanted),
                )
                .order_by(ObservationRow.observed_at)
            )
        ).all()
    latest: dict[str, tuple[str, ...]] = {}
    for row in rows:
        payload = row.normalized_payload
        categories = payload.get("categories")
        wallet = payload.get("wallet")
        if isinstance(wallet, str) and isinstance(categories, list):
            latest[wallet] = tuple(str(c) for c in categories)
    return latest


def tape_buyers(observations: Iterable[Observation]) -> list[str]:
    buyers: list[str] = []
    for observation in observations:
        payload = observation.normalized_payload
        if payload.get("event_type") == "trade_event" and payload.get("side") == "buy":
            wallet = payload.get("buyer_wallet")
            if isinstance(wallet, str):
                buyers.append(wallet)
    return list(dict.fromkeys(buyers))


def signal_features_observation(
    *, mint: str, offset_seconds: int, at: datetime, features: Mapping[str, object]
) -> Observation:
    source_id = f"wallet:signal:{mint}:{offset_seconds}"
    return Observation(
        id=uuid5(NAMESPACE_URL, f"memeradar:{SIGNAL_FEATURES_KIND}:{source_id}"),
        kind=SIGNAL_FEATURES_KIND,
        provenance=Provenance(
            provider="memeradar.reverse-wallet",
            source_id=source_id,
            observed_at=at,
            parser_version=WALLET_PROFILE_VERSION,
        ),
        occurred_at=at,
        observed_at=at,
        ingested_at=at,
        quality_state=QualityState.FRESH,
        normalized_payload={"mint": mint, "offset_seconds": offset_seconds, **features},
    )


__all__ = [
    "PROFILE_KIND",
    "SIGNAL_FEATURES_KIND",
    "load_profile_categories",
    "persist_profiles",
    "profile_observation",
    "signal_features_observation",
    "tape_buyers",
]

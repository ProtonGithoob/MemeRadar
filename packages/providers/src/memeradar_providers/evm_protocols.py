"""Strict, read-only EVM protocol identities and lifecycle normalization."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import ClassVar, Protocol

from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_domain import Chain, Observation, Provenance, QualityState, normalize_chain
from memeradar_domain.common import ensure_utc, require_text
from memeradar_domain.identities import require_evm_address

from .evm_rpc import EVM_CHAIN_IDS
from .transport import CapabilityUnavailableError, ProviderSchemaError

EVM_PROTOCOL_PARSER_VERSION = "evm-protocol-v1"
_TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")
_TOPIC = re.compile(r"^0x[0-9a-fA-F]{64}$")
_MISSING = object()


class EvmProtocolVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    TODO_VERIFY = "TODO_VERIFY"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    CONFLICTED = "CONFLICTED"


class EvmLogPort(Protocol):
    chain: Chain

    async def fetch_logs(
        self,
        *,
        addresses: Sequence[str],
        topics: Sequence[str],
        from_block: int | str,
        to_block: int | str,
        context: ProviderRequestContext,
    ) -> Sequence[Mapping[str, object]]: ...


@dataclass(frozen=True, slots=True)
class EvmProtocolDeployment:
    """Deployment identity; VERIFIED requires every on-chain identity proof."""

    protocol: str
    chain: Chain | str
    contract_address: str | None = None
    event_topics: Mapping[str, str] = field(default_factory=dict)
    runtime_code_hash: str | None = None
    sample_transaction: str | None = None
    verification_status: EvmProtocolVerificationStatus | str = (
        EvmProtocolVerificationStatus.TODO_VERIFY
    )
    verification_source: str | None = None

    def __post_init__(self) -> None:
        protocol = require_text(self.protocol, "protocol", max_length=128).lower()
        chain = normalize_chain(self.chain)
        if not chain.is_evm:
            raise ValueError("EVM protocol deployments require an EVM chain")
        object.__setattr__(self, "protocol", protocol)
        object.__setattr__(self, "chain", chain)
        address = (
            None
            if self.contract_address is None
            else require_evm_address(self.contract_address, "contract_address")
        )
        object.__setattr__(self, "contract_address", address)
        topics: dict[str, str] = {}
        if not isinstance(self.event_topics, Mapping):
            raise TypeError("event_topics must be a mapping")
        for name, topic in self.event_topics.items():
            normalized_name = require_text(str(name), "event_name", max_length=128).lower()
            normalized_topic = require_text(str(topic), "event_topic", max_length=66).lower()
            if _TOPIC.fullmatch(normalized_topic) is None:
                raise ValueError("event_topic must be a 32-byte hex topic")
            topics[normalized_name] = normalized_topic
        object.__setattr__(self, "event_topics", topics)
        status = EvmProtocolVerificationStatus(self.verification_status)
        object.__setattr__(self, "verification_status", status)
        source = (
            None
            if self.verification_source is None
            else require_text(self.verification_source, "verification_source", max_length=512)
        )
        object.__setattr__(self, "verification_source", source)
        if self.runtime_code_hash is not None:
            object.__setattr__(
                self,
                "runtime_code_hash",
                require_text(self.runtime_code_hash, "runtime_code_hash", max_length=128),
            )
        if self.sample_transaction is not None:
            sample = require_text(self.sample_transaction, "sample_transaction", max_length=66)
            if _TX_HASH.fullmatch(sample) is None:
                raise ValueError("sample_transaction must be a canonical transaction hash")
            object.__setattr__(self, "sample_transaction", sample.lower())
        if status is EvmProtocolVerificationStatus.VERIFIED:
            if address is None:
                raise ValueError("verified deployment requires contract_address")
            if not topics:
                raise ValueError("verified deployment requires event_topics")
            if self.runtime_code_hash is None:
                raise ValueError("verified deployment requires runtime_code_hash")
            if self.sample_transaction is None:
                raise ValueError("verified deployment requires sample_transaction")
            if source is None:
                raise ValueError("verified deployment requires verification_source")

    @property
    def chain_id(self) -> int:
        return EVM_CHAIN_IDS[normalize_chain(self.chain)]

    @property
    def authoritative_identity(self) -> bool:
        return self.verification_status is EvmProtocolVerificationStatus.VERIFIED


def _deployment(protocol: str, chain: Chain) -> EvmProtocolDeployment:
    return EvmProtocolDeployment(protocol=protocol, chain=chain)


# Addresses are intentionally absent until chain, bytecode, event and sample
# transaction verification is performed against a live network.
EVM_PROTOCOL_CANDIDATES: tuple[EvmProtocolDeployment, ...] = (
    _deployment("four.meme", Chain.BNB),
    _deployment("pancakeswap", Chain.BNB),
    _deployment("uniswap", Chain.ETHEREUM),
    _deployment("uniswap-v2", Chain.ETHEREUM),
    _deployment("uniswap-v3", Chain.ETHEREUM),
    _deployment("uniswap-v4", Chain.ETHEREUM),
    _deployment("uniswap", Chain.BASE),
    _deployment("uniswap-v3", Chain.BASE),
    _deployment("uniswap-v4", Chain.BASE),
    _deployment("aerodrome", Chain.BASE),
    _deployment("openlaunch", Chain.BASE),
    _deployment("uniswap", Chain.ROBINHOOD),
    _deployment("uniswap-v3", Chain.ROBINHOOD),
    _deployment("uniswap-v4", Chain.ROBINHOOD),
    _deployment("pons", Chain.ROBINHOOD),
    _deployment("par", Chain.ROBINHOOD),
    _deployment("noxa", Chain.ROBINHOOD),
    _deployment("the-odyssey", Chain.ROBINHOOD),
    _deployment("bags", Chain.ROBINHOOD),
    _deployment("o1", Chain.ROBINHOOD),
    _deployment("pools.trade", Chain.ROBINHOOD),
    _deployment("openlaunch", Chain.ROBINHOOD),
)


_EVENT_ALIASES = {
    "tokencreate": "token_created",
    "token_create": "token_created",
    "tokencreated": "token_created",
    "tokenpurchase": "trade",
    "token_purchase": "trade",
    "tokensale": "trade",
    "token_sale": "trade",
    "swap": "trade",
    "trade": "trade",
    "poolcreated": "pool_created",
    "pool_created": "pool_created",
    "initialize": "pool_created",
    "liquidityadded": "liquidity_added",
    "liquidity_added": "liquidity_added",
    "liquidityremoved": "liquidity_removed",
    "liquidity_removed": "liquidity_removed",
    "graduation": "graduation",
    "graduated": "graduation",
    "migration": "migration",
}
_LIFECYCLE_STATE = {
    "token_created": "TOKEN_CREATED",
    "pool_created": "TRADING",
    "trade": "TRADING",
    "graduation": "GRADUATING",
    "migration": "DEX_ACTIVE",
    "liquidity_added": "LIQUIDITY_ADDED",
    "liquidity_removed": "TRADING",
}


def _event_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unknown"
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", value.strip())
    return re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_").lower()


def _timestamp(value: object) -> datetime | None:
    if value is None or value is _MISSING:
        return None
    try:
        if isinstance(value, datetime):
            return ensure_utc(value, "occurred_at")
        if isinstance(value, int | float) and not isinstance(value, bool):
            return datetime.fromtimestamp(value, UTC)
        if isinstance(value, str):
            return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")), "occurred_at")
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    return None


def _raw_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


class EvmProtocolAdapter:
    """Normalize verified-address logs while preserving UNKNOWN identity evidence."""

    protocol: ClassVar[str] = "evm-protocol"
    default_chain: ClassVar[Chain] = Chain.ETHEREUM

    def __init__(
        self,
        *,
        deployments: Sequence[EvmProtocolDeployment] = (),
        chain: Chain | str | None = None,
    ) -> None:
        values = tuple(deployments)
        if any(item.protocol != self.protocol for item in values):
            raise ValueError("deployment protocol does not match adapter")
        inferred_chain = normalize_chain(
            chain or (values[0].chain if values else self.default_chain)
        )
        if any(item.chain is not inferred_chain for item in values):
            raise ValueError("deployment chain does not match adapter")
        self.chain = inferred_chain
        self.deployments = values
        self.provider_name = f"{self.protocol}:{self.chain.value}"
        self.capabilities = frozenset({"protocol_normalization"})

    def _identity(
        self,
        address: str,
        topic: str | None,
    ) -> EvmProtocolDeployment | None:
        for deployment in self.deployments:
            if deployment.contract_address != address:
                continue
            if topic is None or topic in deployment.event_topics.values():
                return deployment
            raise ProviderSchemaError("deployment identity event topic did not match")
        if self.deployments:
            raise ProviderSchemaError("deployment identity contract address did not match")
        return next(
            (
                item
                for item in EVM_PROTOCOL_CANDIDATES
                if item.protocol == self.protocol
                and item.chain is self.chain
                and item.verification_status is EvmProtocolVerificationStatus.VERIFIED
                and item.contract_address == address
            ),
            None,
        )

    def _event_type(
        self,
        raw: Mapping[str, object],
        deployment: EvmProtocolDeployment | None,
    ) -> str:
        explicit = _event_name(raw.get("event_name", raw.get("event_type", "unknown")))
        if explicit != "unknown":
            return _EVENT_ALIASES.get(explicit, explicit)
        topics = raw.get("topics")
        topic = (
            topics[0].lower()
            if isinstance(topics, Sequence)
            and topics
            and isinstance(topics[0], str)
            else None
        )
        if deployment is not None and topic is not None:
            for name, expected in deployment.event_topics.items():
                if expected == topic:
                    return name
        return "unknown"

    def parse(self, message: object, context: ProviderRequestContext) -> Observation:
        if not isinstance(context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        if not isinstance(message, Mapping):
            raise ProviderSchemaError("EVM protocol event must be a mapping")
        address = require_evm_address(str(message.get("address", "")), "contract_address")
        topics = message.get("topics", ())
        if not isinstance(topics, Sequence) or isinstance(topics, str | bytes | bytearray):
            raise ProviderSchemaError("EVM protocol topics were invalid")
        topic = topics[0].lower() if topics and isinstance(topics[0], str) else None
        if topic is not None and _TOPIC.fullmatch(topic) is None:
            raise ProviderSchemaError("EVM protocol topic was invalid")
        deployment = self._identity(address, topic)
        event_type = self._event_type(message, deployment)
        occurred_at = _timestamp(message.get("occurred_at", message.get("block_timestamp")))
        observed_at = ensure_utc(context.requested_at, "observed_at")
        if occurred_at is not None and occurred_at > observed_at:
            occurred_at = None
        tx_hash = message.get("transaction_hash", message.get("transactionHash"))
        if tx_hash is not None and (
            not isinstance(tx_hash, str) or _TX_HASH.fullmatch(tx_hash) is None
        ):
            raise ProviderSchemaError("EVM protocol transaction hash was invalid")
        quality = (
            QualityState.FRESH
            if deployment is not None and deployment.authoritative_identity
            else QualityState.UNKNOWN
        )
        source_id = str(
            tx_hash or message.get("source_id") or f"{address}:{message.get('log_index', '')}"
        )
        token_address = message.get("token_address", message.get("token"))
        pool_address = message.get("pool_address", message.get("pool"))
        payload: dict[str, object] = {
            "chain": self.chain.value,
            "chain_id": EVM_CHAIN_IDS[self.chain],
            "protocol": self.protocol,
            "contract_address": address,
            "event_type": event_type,
            "lifecycle_state": _LIFECYCLE_STATE.get(event_type, "UNKNOWN"),
            "token_address": (
                require_evm_address(token_address, "token_address")
                if isinstance(token_address, str)
                else None
            ),
            "pool_address": (
                require_evm_address(pool_address, "pool_address")
                if isinstance(pool_address, str)
                else None
            ),
            "transaction_hash": tx_hash,
            "log_index": message.get("log_index", message.get("logIndex")),
            "verification_status": (
                EvmProtocolVerificationStatus.TODO_VERIFY.value
                if deployment is None
                else EvmProtocolVerificationStatus(deployment.verification_status).value
            ),
            "identity_verified": deployment is not None and deployment.authoritative_identity,
            "authoritative": False,
            "collection_mode": "PRODUCTION",
        }
        for key in (
            "curve",
            "curve_version",
            "token_manager",
            "graduation",
            "migration_target",
            "pancake_pool",
            "pool_id",
            "quote_asset",
            "market_cap",
            "volume",
            "liquidity",
            "reserves",
            "price",
            "buy_amount",
            "sell_amount",
            "buy_flow",
            "sell_flow",
            "multi_market_state",
        ):
            if key in message:
                payload[key] = message[key]
        if deployment is None:
            payload["reason_codes"] = ("UNVERIFIED_PROTOCOL_DEPLOYMENT",)
        return Observation(
            kind="evm.protocol_event",
            provenance=Provenance(
                provider=self.provider_name,
                source_id=source_id,
                observed_at=observed_at,
                parser_version=EVM_PROTOCOL_PARSER_VERSION,
                raw_payload_hash=_raw_hash(dict(message)),
            ),
            occurred_at=occurred_at,
            observed_at=observed_at,
            ingested_at=observed_at,
            quality_state=quality,
            normalized_payload=payload,
        )


class FourMemeAdapter(EvmProtocolAdapter):
    protocol = "four.meme"
    default_chain = Chain.BNB


class PancakeSwapAdapter(EvmProtocolAdapter):
    protocol = "pancakeswap"
    default_chain = Chain.BNB


class UniswapAdapter(EvmProtocolAdapter):
    protocol = "uniswap"


class AerodromeAdapter(EvmProtocolAdapter):
    protocol = "aerodrome"
    default_chain = Chain.BASE


class OpenLaunchAdapter(EvmProtocolAdapter):
    protocol = "openlaunch"
    default_chain = Chain.BASE


class ParLaunchAdapter(EvmProtocolAdapter):
    protocol = "par"
    default_chain = Chain.ROBINHOOD


class EvmProtocolLogReader:
    """Fetch verified contract logs through the shared RPC adapter."""

    capabilities = frozenset({"pool_discovery", "trade_stream", "launch_discovery"})

    def __init__(self, rpc: EvmLogPort, parser: EvmProtocolAdapter) -> None:
        if not callable(getattr(rpc, "fetch_logs", None)):
            raise TypeError("rpc must expose fetch_logs")
        if not isinstance(parser, EvmProtocolAdapter):
            raise TypeError("parser must be an EvmProtocolAdapter")
        deployments = tuple(parser.deployments)
        if not deployments or not any(item.authoritative_identity for item in deployments):
            raise CapabilityUnavailableError(
                "protocol log discovery requires verified deployment identity"
            )
        rpc_chain = normalize_chain(getattr(rpc, "chain", ""))
        if rpc_chain is not parser.chain:
            raise ValueError("RPC and parser chains must match")
        self.rpc: EvmLogPort = rpc
        self.parser = parser
        self.provider_name = f"{parser.provider_name}:logs"

    async def read(
        self,
        *,
        from_block: int | str,
        to_block: int | str,
        context: object,
    ) -> tuple[Observation, ...]:
        if not isinstance(context, ProviderRequestContext):
            raise TypeError("context must be a ProviderRequestContext")
        addresses = tuple(
            item.contract_address
            for item in self.parser.deployments
            if item.authoritative_identity and item.contract_address is not None
        )
        topics = tuple(
            topic
            for item in self.parser.deployments
            if item.authoritative_identity
            for topic in item.event_topics.values()
        )
        logs = await self.rpc.fetch_logs(
            addresses=addresses,
            topics=topics,
            from_block=from_block,
            to_block=to_block,
            context=context,
        )
        return tuple(self.parser.parse(log, context) for log in logs)


__all__ = [
    "AerodromeAdapter",
    "EVM_PROTOCOL_CANDIDATES",
    "EVM_PROTOCOL_PARSER_VERSION",
    "EvmProtocolAdapter",
    "EvmProtocolDeployment",
    "EvmLogPort",
    "EvmProtocolLogReader",
    "EvmProtocolVerificationStatus",
    "FourMemeAdapter",
    "OpenLaunchAdapter",
    "PancakeSwapAdapter",
    "ParLaunchAdapter",
    "UniswapAdapter",
]

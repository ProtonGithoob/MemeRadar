"""Optional, read-only multi-chain token-security enrichment."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

import httpx

from memeradar_application.provider_contracts import (
    RiskDataRequest,
    RiskFinding,
    RiskSeverity,
)
from memeradar_domain import Chain, Provenance, QualityState, TokenIdentity, normalize_chain
from memeradar_domain.common import (
    bounded_decimal,
    ensure_ordered_timestamps,
    require_text,
)

from .rugcheck import RugCheckRestAdapter
from .transport import (
    CapabilityUnavailableError,
    ProviderError,
    ProviderSchemaError,
    ProviderTransport,
)

Clock = Callable[[], datetime]

GOPLUS_PROVIDER = "goplus"
GOPLUS_PARSER_VERSION = "goplus-token-security-v1"
TOKEN_SECURITY_FIELDS = (
    "is_honeypot",
    "is_blacklisted",
    "is_mintable",
    "is_proxy",
    "is_open_source",
    "buy_tax",
    "sell_tax",
)
_FIELD_CODES = {
    "is_honeypot": "TOKEN_SECURITY_HONEYPOT",
    "is_blacklisted": "TOKEN_SECURITY_BLACKLISTED",
    "is_mintable": "TOKEN_SECURITY_MINTABLE",
    "is_proxy": "TOKEN_SECURITY_PROXY",
    "is_open_source": "TOKEN_SECURITY_OPEN_SOURCE",
    "buy_tax": "TOKEN_SECURITY_BUY_TAX",
    "sell_tax": "TOKEN_SECURITY_SELL_TAX",
}
_FIELD_ALIASES = {
    "is_honeypot": ("is_honeypot", "isHoneypot"),
    "is_blacklisted": ("is_blacklisted", "isBlacklisted"),
    "is_mintable": ("is_mintable", "isMintable"),
    "is_proxy": ("is_proxy", "isProxy"),
    "is_open_source": ("is_open_source", "isOpenSource"),
    "buy_tax": ("buy_tax", "buyTax"),
    "sell_tax": ("sell_tax", "sellTax"),
}
_CHAIN_PATHS = {
    Chain.SOLANA: "/api/v1/solana/token_security",
    Chain.BNB: "/api/v1/token_security/56",
    Chain.ROBINHOOD: "/api/v1/token_security/4663",
}


def _boolean(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "false", "no"}:
            return False
        if normalized in {"1", "true", "yes"}:
            return True
    raise ProviderSchemaError(f"{field} was invalid")


def _tax(value: object, field: str) -> Decimal:
    try:
        return bounded_decimal(value, field, Decimal("0"), Decimal("100"))
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"{field} was invalid") from exc


def _value(payload: Mapping[str, object], field: str) -> object:
    for alias in _FIELD_ALIASES[field]:
        if alias in payload:
            return payload[alias]
    return None


def _severity(field: str, value: bool | Decimal) -> RiskSeverity:
    if field == "is_honeypot":
        return RiskSeverity.BLOCK if value is True else RiskSeverity.INFO
    if field == "is_open_source":
        return RiskSeverity.WARN if value is False else RiskSeverity.INFO
    if field in {"is_blacklisted", "is_mintable", "is_proxy"}:
        return RiskSeverity.WARN if value is True else RiskSeverity.INFO
    return RiskSeverity.WARN if value > 0 else RiskSeverity.INFO


def normalize_token_security(
    token: TokenIdentity,
    payload: Mapping[str, object],
    *,
    observed_at: datetime,
    ingested_at: datetime,
    parser_version: str = GOPLUS_PARSER_VERSION,
) -> tuple[RiskFinding, ...]:
    """Normalize bounded security fields while preserving absent data as UNKNOWN."""

    if not isinstance(token, TokenIdentity):
        raise TypeError("token must be a TokenIdentity")
    if not isinstance(payload, Mapping):
        raise ProviderSchemaError("token-security result was not an object")
    try:
        _, normalized_observed, _ = ensure_ordered_timestamps(
            None,
            observed_at,
            ingested_at,
        )
    except ValueError as exc:
        raise ProviderSchemaError("token-security timestamps were invalid") from exc
    source_id = f"token-security:{token.canonical_id}"
    provenance = Provenance(
        provider=GOPLUS_PROVIDER,
        source_id=source_id,
        observed_at=normalized_observed,
        parser_version=require_text(parser_version, "parser_version", max_length=64),
    )
    findings: list[RiskFinding] = []
    for field in TOKEN_SECURITY_FIELDS:
        raw_value = _value(payload, field)
        if raw_value is None:
            findings.append(
                RiskFinding(
                    code=_FIELD_CODES[field],
                    severity=RiskSeverity.UNKNOWN,
                    quality_state=QualityState.UNKNOWN,
                    detail=f"{field}=UNKNOWN",
                    evidence_refs=(source_id,),
                    provenance=provenance,
                )
            )
            continue
        normalized: bool | Decimal
        if field in {"buy_tax", "sell_tax"}:
            normalized = _tax(raw_value, field)
            detail = f"{field}_percent={normalized}"
        else:
            normalized = _boolean(raw_value, field)
            detail = f"{field}={str(normalized).lower()}"
        findings.append(
            RiskFinding(
                code=_FIELD_CODES[field],
                severity=_severity(field, normalized),
                quality_state=QualityState.FRESH,
                detail=detail,
                evidence_refs=(source_id,),
                provenance=provenance,
            )
        )
    return tuple(findings)


def _result_for_token(
    payload: Mapping[str, object],
    token: TokenIdentity,
) -> Mapping[str, object]:
    if payload.get("success") is False:
        raise ProviderError("provider response reported failure")
    raw_code = payload.get("code")
    if raw_code is not None and (
        isinstance(raw_code, bool) or not isinstance(raw_code, int) or raw_code != 1
    ):
        raise ProviderError("provider response reported failure")
    result = payload.get("result", payload.get("data", {}))
    if not isinstance(result, Mapping):
        raise ProviderSchemaError("token-security result was invalid")
    if any(field in result for field in TOKEN_SECURITY_FIELDS):
        return result
    token_key = token.mint_address.lower()
    for key, value in result.items():
        if isinstance(key, str) and key.lower() == token_key:
            if not isinstance(value, Mapping):
                raise ProviderSchemaError("token-security token result was invalid")
            return value
    return {}


class GoPlusTokenSecurityAdapter(RugCheckRestAdapter):
    """Read-only GoPlus-style adapter using the existing bounded risk transport."""

    provider_name = GOPLUS_PROVIDER
    capabilities = frozenset({"token_security", "risk_data"})

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        supported_chains: Sequence[Chain | str] = (
            Chain.SOLANA,
            Chain.BNB,
            Chain.ROBINHOOD,
        ),
        client: httpx.AsyncClient | None = None,
        transport: ProviderTransport | None = None,
        clock: Clock | None = None,
        parser_version: str = GOPLUS_PARSER_VERSION,
    ) -> None:
        if isinstance(supported_chains, str | bytes | bytearray):
            raise TypeError("supported_chains must be a sequence")
        normalized_chains = tuple(normalize_chain(chain) for chain in supported_chains)
        if not normalized_chains:
            raise ValueError("supported_chains must not be empty")
        if len(normalized_chains) != len(set(normalized_chains)):
            raise ValueError("supported_chains must not contain duplicates")
        super().__init__(
            base_url,
            api_key=api_key,
            client=client,
            transport=transport,
            clock=clock,
            parser_version=parser_version,
        )
        self._supported_chains = frozenset(normalized_chains)

    def __repr__(self) -> str:
        return (
            f"GoPlusTokenSecurityAdapter(base_url={self._base_url!r}, "
            f"api_key_configured={self._api_key is not None}, "
            f"supported_chains={tuple(item.value for item in self._supported_chains)!r})"
        )

    async def assess(self, request: RiskDataRequest) -> tuple[RiskFinding, ...]:
        if not isinstance(request, RiskDataRequest):
            raise TypeError("request must be a RiskDataRequest")
        chain = normalize_chain(request.token.chain)
        if chain not in self._supported_chains:
            raise CapabilityUnavailableError(
                f"token security is unavailable for chain {chain.value}"
            )
        observed_at, ingested_at = self._now_pair()
        address = quote(request.token.mint_address, safe="")
        path = f"{_CHAIN_PATHS[chain]}?contract_addresses={address}"
        response = await self._get(
            path,
            context=request.context,
        )
        if not isinstance(response.payload, Mapping):
            raise ProviderSchemaError("provider token-security response was invalid")
        return normalize_token_security(
            request.token,
            _result_for_token(response.payload, request.token),
            observed_at=observed_at,
            ingested_at=ingested_at,
            parser_version=self._parser_version,
        )


TokenSecurityRestAdapter = GoPlusTokenSecurityAdapter


__all__ = [
    "GOPLUS_PARSER_VERSION",
    "GOPLUS_PROVIDER",
    "GoPlusTokenSecurityAdapter",
    "TOKEN_SECURITY_FIELDS",
    "TokenSecurityRestAdapter",
    "normalize_token_security",
]

"""Network-free external-wallet fixture adapter.

No live GMGN/CabalSpy-style adapter is provided here: the repository has no
operator-supplied documented/legal endpoint contract for one.  This adapter
exists for replay and contract tests only and never opens a network connection.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from memeradar_application.external_wallet import (
    EXTERNAL_WALLET_PROVIDER,
    ExternalWalletIntelligencePort,
    ExternalWalletIntelligenceRequest,
    ExternalWalletIntelligenceResult,
    ExternalWalletLabel,
    ExternalWalletTokenSignal,
)
from memeradar_domain import Provenance, QualityState
from memeradar_domain.common import normalize_texts


class FixtureExternalWalletIntelligenceAdapter(ExternalWalletIntelligencePort):
    """Deterministic in-memory adapter used by keyless replay tests."""

    provider_name = EXTERNAL_WALLET_PROVIDER

    def __init__(
        self,
        *,
        labels: Sequence[ExternalWalletLabel] = (),
        token_signals: Sequence[ExternalWalletTokenSignal] = (),
    ) -> None:
        if isinstance(labels, str | bytes | bytearray):
            raise TypeError("labels must be a sequence")
        if isinstance(token_signals, str | bytes | bytearray):
            raise TypeError("token_signals must be a sequence")
        normalized_labels = tuple(labels)
        normalized_signals = tuple(token_signals)
        if any(not isinstance(value, ExternalWalletLabel) for value in normalized_labels):
            raise TypeError("labels must contain ExternalWalletLabel values")
        if any(not isinstance(value, ExternalWalletTokenSignal) for value in normalized_signals):
            raise TypeError("token_signals must contain ExternalWalletTokenSignal values")
        if len(normalized_labels) + len(normalized_signals) > 10_000:
            raise ValueError("fixture external-wallet evidence exceeds the configured bound")
        self._labels = tuple(
            sorted(
                normalized_labels,
                key=lambda item: (
                    item.wallet_address,
                    item.source,
                    item.raw_source_id,
                    item.observed_at,
                    item.label,
                ),
            )
        )
        self._token_signals = tuple(
            sorted(
                normalized_signals,
                key=lambda item: (
                    item.wallet_address or "",
                    item.source,
                    item.raw_source_id,
                    item.observed_at,
                    item.signal_type,
                ),
            )
        )
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    async def lookup(
        self,
        request: ExternalWalletIntelligenceRequest,
    ) -> ExternalWalletIntelligenceResult:
        if not isinstance(request, ExternalWalletIntelligenceRequest):
            raise TypeError("request must be an ExternalWalletIntelligenceRequest")
        self._calls += 1
        requested_wallets = set(request.wallet_addresses)
        labels = tuple(
            item
            for item in self._labels
            if not requested_wallets or item.wallet_address in requested_wallets
        )
        signals = tuple(
            item
            for item in self._token_signals
            if item.token == request.token
            and request.include_token_signals
            and (not requested_wallets or item.wallet_address in requested_wallets)
        )
        evidence: tuple[ExternalWalletLabel | ExternalWalletTokenSignal, ...] = (
            *labels,
            *signals,
        )
        as_of = max(
            (item.observed_at for item in evidence),
            default=request.context.requested_at,
        )
        expires_at = as_of + timedelta(minutes=5)
        provenance: list[Provenance] = []
        evidence_refs: list[str] = []
        states: list[QualityState] = []
        for item in evidence:
            provenance.append(item.provenance)
            evidence_refs.extend((*item.evidence_refs, item.raw_source_id))
            states.append(item.quality_state)
        reason_code = (
            "EXTERNAL_WALLET_INTELLIGENCE_RECEIVED" if evidence else "EXTERNAL_EVIDENCE_MISSING"
        )
        quality_priority = {
            QualityState.FRESH: 0,
            QualityState.STALE: 1,
            QualityState.UNKNOWN: 2,
            QualityState.CONFLICTED: 3,
            QualityState.INVALID: 4,
        }
        return ExternalWalletIntelligenceResult(
            provider=self.provider_name,
            token=request.token,
            as_of=as_of,
            expires_at=expires_at,
            labels=labels[: request.max_records],
            token_signals=signals[: max(0, request.max_records - len(labels))],
            provenance=tuple(
                sorted(
                    set(provenance),
                    key=lambda item: (item.provider, item.source_id, item.observed_at),
                )
            ),
            evidence_refs=normalize_texts(evidence_refs, "evidence_refs"),
            reason_codes=(reason_code,),
            quality_state=(
                max(states, key=lambda state: quality_priority[state])
                if states
                else QualityState.UNKNOWN
            ),
        )


__all__ = ["FixtureExternalWalletIntelligenceAdapter"]

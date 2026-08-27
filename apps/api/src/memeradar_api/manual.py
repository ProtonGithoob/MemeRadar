"""Authenticated analysis-only manual mint submission endpoint."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from memeradar_application.config import Settings
from memeradar_application.manual_submission import (
    ManualMintRequest,
    ManualMintSubmissionService,
)
from memeradar_application.provider_contracts import ProviderRequestContext
from memeradar_telemetry.logging import CORRELATION_ID_HEADER, resolve_correlation_id


class ManualMintPayload(BaseModel):
    """Strict request body accepting the public ``mint`` alias."""

    model_config = ConfigDict(extra="forbid")

    mint_address: str | None = Field(default=None, min_length=1, max_length=64)
    mint: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_one_mint(self) -> ManualMintPayload:
        if self.mint_address is None and self.mint is None:
            raise ValueError("mint or mint_address is required")
        if (
            self.mint_address is not None
            and self.mint is not None
            and self.mint_address.strip() != self.mint.strip()
        ):
            raise ValueError("mint and mint_address must match")
        self.mint_address = self.mint_address or self.mint
        return self


class ManualMintResponse(BaseModel):
    """Safe acknowledgement containing no credentials or execution material."""

    mint_address: str
    token_id: UUID
    source_id: str
    provider: str
    duplicate: bool
    execution_enabled: bool = False


def _authorize(settings: Settings, authorization: str | None) -> None:
    configured_token = settings.operator_api_token
    if configured_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="manual submission authentication is not configured",
        )
    expected = f"Bearer {configured_token}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="manual submission authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def build_manual_router(
    settings: Settings,
    service: ManualMintSubmissionService | None = None,
) -> APIRouter:
    """Build the authenticated manual-input router with an injectable service."""

    if not isinstance(settings, Settings):
        raise TypeError("settings must be a Settings instance")
    submission_service = service or ManualMintSubmissionService()
    router = APIRouter(prefix="/v1/manual", tags=["manual"])

    @router.post("/mints", response_model=ManualMintResponse)
    async def submit_mint(
        body: ManualMintPayload,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ManualMintResponse:
        _authorize(settings, authorization)
        mint_address = body.mint_address
        if mint_address is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mint or mint_address is required",
            )
        now = datetime.now(UTC)
        correlation_id = resolve_correlation_id(request.headers.get(CORRELATION_ID_HEADER))
        context = ProviderRequestContext(
            correlation_id=correlation_id,
            requested_at=now,
            deadline_at=now + timedelta(seconds=5),
        )
        try:
            result = submission_service.submit(
                ManualMintRequest(context=context, mint_address=mint_address)
            )
        except (TypeError, ValueError) as exc:
            del exc
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mint_address must be a canonical Solana address",
            ) from None
        candidate = result.candidate
        return ManualMintResponse(
            mint_address=candidate.token.mint_address,
            token_id=candidate.token.id,
            source_id=candidate.source_id,
            provider=candidate.provenance.provider,
            duplicate=result.duplicate,
            execution_enabled=False,
        )

    return router


__all__ = ["ManualMintPayload", "ManualMintResponse", "build_manual_router"]

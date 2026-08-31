"""Constant-time role-token authentication for operator control routes."""

from __future__ import annotations

import secrets
from collections.abc import Sequence

from fastapi import HTTPException, status

from memeradar_application.config import Settings
from memeradar_application.control import (
    ControlAction,
    ControlAuthorizationError,
    ControlPrincipal,
    ControlRole,
    authorize,
)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="control authentication failed",
        headers={"WWW-Authenticate": "Bearer"},
    )


class RoleTokenAuthenticator:
    """Resolve configured role tokens without retaining them in principals."""

    def __init__(self, settings: Settings) -> None:
        if not isinstance(settings, Settings):
            raise TypeError("settings must be a Settings instance")
        configured: list[tuple[ControlRole, str]] = []
        for role, token in (
            (ControlRole.VIEWER, settings.viewer_api_token),
            (ControlRole.OPERATOR, settings.operator_api_token),
            (ControlRole.ADMIN, settings.admin_api_token),
            (ControlRole.EXECUTION, settings.execution_api_token),
        ):
            if token is not None:
                configured.append((role, token))
        self._tokens: tuple[tuple[ControlRole, str], ...] = tuple(configured)

    @property
    def configured(self) -> bool:
        """Return whether at least one role credential exists."""

        return bool(self._tokens)

    def authenticate(self, authorization: str | None) -> ControlPrincipal:
        """Authenticate one bearer header and return a non-secret principal."""

        if not self._tokens:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="control authentication is not configured",
            )
        if authorization is None:
            raise _unauthorized()
        scheme, separator, credential = authorization.partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not credential
            or any(character.isspace() for character in credential)
        ):
            raise _unauthorized()
        matched_role: ControlRole | None = None
        for role, configured_token in self._tokens:
            if secrets.compare_digest(credential, configured_token):
                matched_role = role
        if matched_role is None:
            raise _unauthorized()
        return ControlPrincipal(subject=matched_role.value.lower(), role=matched_role)

    def require(
        self,
        authorization: str | None,
        action: ControlAction,
    ) -> ControlPrincipal:
        """Authenticate and enforce one explicit application permission."""

        principal = self.authenticate(authorization)
        try:
            authorize(principal, action)
        except ControlAuthorizationError as exc:
            del exc
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="control permission denied",
            ) from None
        return principal


__all__: Sequence[str] = ["RoleTokenAuthenticator"]

"""Provider-independent domain package."""

from .events import EventEnvelope, ReasonCode, normalize_reason_codes
from .evidence import Freshness, Observation, Provenance, QualityState
from .identities import Chain, PoolIdentity, TokenIdentity, require_solana_address
from .lifecycle import (
    Candidate,
    CandidateState,
    IdempotencyConflict,
    InvalidTransition,
    StateTransition,
)
from .operations import (
    Alert,
    AlertSeverity,
    AlertState,
    AlertType,
    ExitSignal,
    Position,
    PositionMode,
    PositionState,
)
from .snapshots import (
    FeatureSnapshot,
    RiskAssessment,
    RiskDisposition,
    ScoreSnapshot,
)

__version__ = "0.1.0"

__all__ = [
    "Alert",
    "AlertSeverity",
    "AlertState",
    "AlertType",
    "Candidate",
    "CandidateState",
    "Chain",
    "EventEnvelope",
    "ExitSignal",
    "FeatureSnapshot",
    "Freshness",
    "IdempotencyConflict",
    "InvalidTransition",
    "Observation",
    "PoolIdentity",
    "Position",
    "PositionMode",
    "PositionState",
    "Provenance",
    "QualityState",
    "ReasonCode",
    "RiskAssessment",
    "RiskDisposition",
    "ScoreSnapshot",
    "StateTransition",
    "TokenIdentity",
    "normalize_reason_codes",
    "require_solana_address",
]

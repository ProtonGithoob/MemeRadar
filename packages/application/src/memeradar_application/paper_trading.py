"""Compatibility facade for the repository's paper execution subsystem.

The implementation lives in :mod:`paper_execution`; this module keeps the
plan's paper-trading name available without introducing a second ledger or
execution path.
"""

from .paper_execution import (
    InMemoryPaperLedgerStore,
    PaperAutoExecutionDecision,
    PaperAutoExecutionGate,
    PaperExecutionEngine,
    PaperExecutionPolicy,
    PaperExecutionRejected,
    PaperFillModel,
    PaperIdempotencyConflict,
    PaperLedgerConflict,
    PaperLedgerStore,
    PaperOrderRequest,
    PaperReconciler,
    PaperReplayManifest,
    PaperReplayResult,
    PaperSizingInput,
    PaperSizingPolicy,
    ReconciliationReport,
    SizingResult,
)

PaperTradingEngine = PaperExecutionEngine

__all__ = [
    "InMemoryPaperLedgerStore",
    "PaperAutoExecutionDecision",
    "PaperAutoExecutionGate",
    "PaperExecutionEngine",
    "PaperExecutionPolicy",
    "PaperExecutionRejected",
    "PaperFillModel",
    "PaperIdempotencyConflict",
    "PaperLedgerConflict",
    "PaperLedgerStore",
    "PaperOrderRequest",
    "PaperReplayManifest",
    "PaperReplayResult",
    "PaperReconciler",
    "PaperSizingInput",
    "PaperSizingPolicy",
    "PaperTradingEngine",
    "ReconciliationReport",
    "SizingResult",
]

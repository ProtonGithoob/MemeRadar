"""Metadata contracts for the Sprint 9.1 paper ledger tables."""

from pathlib import Path

from sqlalchemy import UniqueConstraint

from memeradar_persistence import Base, CashLedgerRow, FillRow, OrderRow

ROOT = Path(__file__).resolve().parents[2]


def test_paper_rows_are_declared_with_required_audit_columns() -> None:
    assert {"orders", "fills", "cash_ledger"} <= set(Base.metadata.tables)
    assert {
        "portfolio_id",
        "candidate_id",
        "token_id",
        "mode",
        "side",
        "state",
        "idempotency_key",
        "requested_amount",
        "requested_at",
        "quote_snapshot",
        "risk_snapshot",
        "request_fingerprint",
        "policy_version",
        "config_hash",
        "fill_model_version",
    } <= {column.name for column in OrderRow.__table__.columns}
    assert {
        "order_id",
        "occurred_at",
        "input_amount",
        "quantity",
        "price",
        "quoted_price",
        "fee_breakdown",
        "slippage_bps",
        "source",
    } <= {column.name for column in FillRow.__table__.columns}
    assert {
        "portfolio_id",
        "sequence",
        "cash_delta",
        "balance_after",
        "entry_type",
        "order_id",
        "fill_id",
        "reason_codes",
    } <= {column.name for column in CashLedgerRow.__table__.columns}


def test_paper_idempotency_and_ledger_sequence_constraints_are_physical() -> None:
    order_constraints = OrderRow.__table__.constraints
    ledger_constraints = CashLedgerRow.__table__.constraints
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"idempotency_key"}
        for constraint in order_constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"idempotency_key"}
        for constraint in ledger_constraints
    )
    assert (ROOT / "infra" / "alembic" / "versions" / "0006_paper_execution.py").exists()

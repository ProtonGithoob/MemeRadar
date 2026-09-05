"""Persistence keys must preserve the domain's chain-qualified identities."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from memeradar_persistence import Base, PoolRow, TokenRow

NOW = datetime(2026, 9, 6, tzinfo=UTC)
EVM_ADDRESS = "0x" + "ab" * 20


def test_token_address_is_unique_per_chain() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    first_id, second_id = uuid4(), uuid4()

    with Session(engine) as session:
        session.add_all(
            [
                TokenRow(
                    id=first_id,
                    chain="bnb",
                    mint_address=EVM_ADDRESS,
                    token_program="erc20",
                    first_seen_at=NOW,
                ),
                TokenRow(
                    id=second_id,
                    chain="robinhood",
                    mint_address=EVM_ADDRESS,
                    token_program="erc20",
                    first_seen_at=NOW,
                ),
            ]
        )
        session.commit()


def test_pool_address_is_scoped_by_its_chain_qualified_token() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    first_token_id, second_token_id = uuid4(), uuid4()

    with Session(engine) as session:
        session.add_all(
            [
                TokenRow(
                    id=first_token_id,
                    chain="bnb",
                    mint_address="0x" + "01" * 20,
                    token_program="erc20",
                    first_seen_at=NOW,
                ),
                TokenRow(
                    id=second_token_id,
                    chain="robinhood",
                    mint_address="0x" + "02" * 20,
                    token_program="erc20",
                    first_seen_at=NOW,
                ),
                PoolRow(
                    token_id=first_token_id,
                    venue="fixture",
                    pool_address=EVM_ADDRESS,
                    quote_mint="0x" + "03" * 20,
                    first_seen_at=NOW,
                ),
                PoolRow(
                    token_id=second_token_id,
                    venue="fixture",
                    pool_address=EVM_ADDRESS,
                    quote_mint="0x" + "04" * 20,
                    first_seen_at=NOW,
                ),
            ]
        )
        session.commit()

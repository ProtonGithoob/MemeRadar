"""Database durability and runtime connection-boundary contracts."""

from unittest.mock import patch

from memeradar_persistence.uow import create_database_engine


def test_postgres_engine_has_bounded_pool_and_statement_timeouts() -> None:
    with patch("memeradar_persistence.uow.create_async_engine") as factory:
        create_database_engine("postgresql://user:password@localhost/memeradar")

    kwargs = factory.call_args.kwargs
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 5
    assert kwargs["pool_timeout"] == 30
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["connect_args"] == {
        "command_timeout": 30,
        "server_settings": {
            "statement_timeout": "30000",
            "idle_in_transaction_session_timeout": "60000",
        },
    }

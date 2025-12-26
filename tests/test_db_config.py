import pytest
from unittest.mock import MagicMock
from sqlalchemy import event
from src.db import _set_sqlite_pragma, engine, async_engine


@pytest.mark.asyncio
async def test_sqlite_pragmas_event_listener():
    """
    Verify that _set_sqlite_pragma executes the correct PRAGMA statements
    and is registered as an event listener.
    """
    # 1. Verify function logic
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connection.cursor.return_value = mock_cursor

    _set_sqlite_pragma(mock_connection, None)

    # Check calls
    assert mock_cursor.execute.call_count == 2
    mock_cursor.execute.assert_any_call("PRAGMA foreign_keys=ON")
    mock_cursor.execute.assert_any_call("PRAGMA journal_mode=WAL")
    mock_cursor.close.assert_called_once()

    # 2. Verify registration (indirectly, via checking if it's in the event
    # system)
    # SQLAlchemy's event.contains is useful here
    assert event.contains(engine, "connect", _set_sqlite_pragma)
    assert event.contains(
        async_engine.sync_engine, "connect", _set_sqlite_pragma
    )

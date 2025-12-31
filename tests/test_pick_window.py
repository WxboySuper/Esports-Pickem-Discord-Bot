import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import discord
from datetime import datetime, timezone, timedelta

from sqlalchemy.dialects import sqlite

import src.commands.pick as pick


@pytest.mark.asyncio
@patch("src.commands.pick.get_session")
@patch("src.commands.pick.datetime")
async def test_pick_uses_pick_window(mock_datetime, mock_get_session):
    """Ensure the pick command builds a query that uses
    PICK_WINDOW_DAYS as cutoff.
    """
    # Freeze 'now' to a known point
    fixed_now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = fixed_now

    # Capture the statement passed to session.exec
    captured = {}

    def fake_exec(stmt):
        captured["stmt"] = stmt

        class R:
            def all(self):
                return []

            def first(self):
                return None

        return R()

    # Provide mock session and interaction fixtures locally
    mock_session = MagicMock()
    mock_session.exec.side_effect = fake_exec
    mock_get_session.return_value.__enter__.return_value = mock_session

    mock_interaction = AsyncMock(spec=discord.Interaction)
    mock_interaction.response = AsyncMock()
    mock_interaction.followup = AsyncMock()
    mock_interaction.user = MagicMock()

    await pick.pick.callback(mock_interaction)

    assert "stmt" in captured, "No statement was executed by pick command"

    # Compile the captured SQLAlchemy statement and examine bound params
    compiled = captured["stmt"].compile(dialect=sqlite.dialect())
    params = compiled.params

    # Expect the pick cutoff (now + PICK_WINDOW_DAYS) to be present
    expected_cutoff = fixed_now + timedelta(days=pick.PICK_WINDOW_DAYS)

    found = any(
        (isinstance(v, datetime) and v == expected_cutoff)
        for v in params.values()
    )
    err = (
        f"Expected cutoff {expected_cutoff!r} not found in stmt params: "
        f"{params}"
    )
    assert found, err

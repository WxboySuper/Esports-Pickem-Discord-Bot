import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError
import discord

from src.commands.pick import PickView
from src.models import Match


@pytest.fixture
def mock_match():
    # Use a dummy match for testing
    return Match(
        id=100,
        team1="TeamA",
        team2="TeamB",
        scheduled_time=MagicMock(),  # Will need to mock timestamp access if used
        contest_id=10,
        best_of=1,
    )


@pytest.mark.asyncio
@patch("src.commands.pick.get_session")
@patch("src.commands.pick.crud")
async def test_pick_race_condition_handled(
    mock_crud, mock_get_session, mock_match
):
    """
    Test that an IntegrityError (simulating a race condition) during pick creation
    is caught and handled by updating the existing pick instead.
    """
    # Arrange
    view = PickView(matches=[mock_match], user_picks={}, user_id=123)
    # Ensure current match is valid and not started
    mock_match.scheduled_time = MagicMock()
    # Mock timestamp to be in the future relative to now
    mock_match.scheduled_time.timestamp.return_value = 1700000000
    # Patch datetime.now to be before the match
    with patch("src.commands.pick.datetime") as mock_dt:
        mock_now = MagicMock()
        mock_dt.now.return_value = mock_now
        # Make comparison false so match hasn't started (now >= scheduled is False)
        mock_now.__ge__.return_value = False

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.response = AsyncMock()
        mock_interaction.user.name = "Racer"

        # Mock Database Session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # User exists
        mock_crud.get_user_by_discord_id.return_value = MagicMock(id=1)

        # First check: No pick exists
        mock_session.exec.return_value.first.side_effect = [None, MagicMock()]
        # The first call returns None (check for existing),
        # The second call (inside except block) returns the Pick that "won the race"

        # Simulate IntegrityError on create_pick
        mock_crud.create_pick.side_effect = IntegrityError(
            None, None, Exception("Unique violation")
        )

        # Act
        await view.on_team1(mock_interaction)

        # Assert
        # 1. create_pick was attempted and failed
        mock_crud.create_pick.assert_called_once()

        # 2. session.rollback was called
        mock_session.rollback.assert_called_once()

        # 3. session.exec was called again to fetch the existing pick
        assert mock_session.exec.call_count >= 2

        # 4. The existing pick was updated (session.add called with it)
        # We can't easily assert the specific object passed to add without capturing the second side_effect return
        assert mock_session.add.called
        assert mock_session.commit.called

        # 5. Local state updated
        assert view.user_picks[100] == "TeamA"

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
async def test_pick_view_delegates_to_upsert(
    mock_crud, mock_get_session, mock_match
):
    """
    Test that PickView.handle_pick delegates pick creation/update to
    crud.upsert_pick, ensuring the complexity and race handling are offloaded.
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
        mock_interaction.user.name = "Picker"

        # Mock Database Session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # User exists
        mock_crud.get_user_by_discord_id.return_value = MagicMock(id=1)

        # Act
        await view.on_team1(mock_interaction)

        # Assert
        # Verify that upsert_pick was called correctly
        mock_crud.upsert_pick.assert_called_once()
        call_args = mock_crud.upsert_pick.call_args
        assert call_args[0][0] == mock_session  # Session passed

        # Verify params
        # Since crud is mocked, PickCreateParams is a mock constructor.
        # We check that the mock constructor was called with correct args.
        mock_crud.PickCreateParams.assert_called_once()
        create_args = mock_crud.PickCreateParams.call_args[1]
        assert create_args["user_id"] == 1
        assert create_args["match_id"] == 100
        assert create_args["chosen_team"] == "TeamA"

        # Verify local state update
        assert view.user_picks[100] == "TeamA"

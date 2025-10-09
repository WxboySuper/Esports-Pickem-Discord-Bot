# tests/test_new_commands.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import discord

from src.commands import pick, picks, stats, matches, result, leaderboard
from src.models import User, Contest, Match, Pick as PickModel, Result as ResultModel

# --- Mocks and Test Data ---

@pytest.fixture
def mock_interaction():
    """Fixture for a mock discord.Interaction."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = 123
    interaction.user.name = "TestUser"
    interaction.user.display_name = "TestUser"
    interaction.user.avatar.url = "http://example.com/avatar.png"
    interaction.guild.id = 456
    return interaction

@pytest.fixture
def mock_session():
    """Fixture for a mock database session."""
    return MagicMock()

@pytest.fixture
def mock_bot():
    """Fixture for a mock bot instance."""
    bot = AsyncMock()
    bot.tree.add_command = MagicMock()
    return bot

# --- Test Cases ---

@pytest.mark.asyncio
@patch("src.commands.pick.get_session")
async def test_pick_command_no_active_matches(mock_get_session, mock_interaction, mock_session):
    """Test the /pick command when there are no active matches."""
    mock_get_session.return_value = iter([mock_session])
    mock_session.exec.return_value.all.return_value = []

    await pick.pick.callback(mock_interaction)

    mock_interaction.response.send_message.assert_called_once_with(
        "There are no active matches available to pick.", ephemeral=True
    )

@pytest.mark.asyncio
@patch("src.commands.picks.get_session")
async def test_picks_view_active_no_picks(mock_get_session, mock_interaction, mock_session):
    """Test /picks view-active when the user has no picks."""
    mock_get_session.return_value = iter([mock_session])
    # Simulate user not found or has no picks
    with patch("src.commands.picks.crud.get_user_by_discord_id") as mock_get_user:
        mock_get_user.return_value = None
        await picks.view_active.callback(mock_interaction)
        mock_interaction.response.send_message.assert_called_with("You have no active picks.", ephemeral=True)

@pytest.mark.asyncio
@patch("src.commands.stats.get_session")
async def test_stats_command_new_user(mock_get_session, mock_interaction, mock_session):
    """Test /stats command for a user with no picks."""
    mock_get_session.return_value = iter([mock_session])
    with patch("src.commands.stats.crud.get_user_by_discord_id") as mock_get_user:
        mock_get_user.return_value = None
        await stats.stats.callback(mock_interaction, user=None)
        mock_interaction.response.send_message.assert_called_with("You have not made any picks yet.", ephemeral=True)

@pytest.mark.asyncio
@patch("src.commands.matches.get_session")
async def test_matches_view_by_day_no_matches(mock_get_session, mock_interaction, mock_session):
    """Test /matches view-by-day when no matches are scheduled."""
    mock_get_session.return_value = iter([mock_session])
    with patch("src.commands.matches.crud.get_matches_by_date") as mock_get_matches:
        mock_get_matches.return_value = []
        await matches.view_by_day.callback(mock_interaction)

        # Check that an embed with "No matches found." is sent
        _, kwargs = mock_interaction.response.send_message.call_args
        assert "No matches found" in kwargs['embed'].description

@pytest.mark.asyncio
@patch("src.commands.leaderboard.get_session")
async def test_leaderboard_command_empty(mock_get_session, mock_interaction, mock_session):
    """Test /leaderboard command when the leaderboard is empty."""
    mock_get_session.return_value = iter([mock_session])
    with patch("src.commands.leaderboard.get_leaderboard_data") as mock_get_data:
        mock_get_data.return_value = []
        await leaderboard.leaderboard.callback(mock_interaction)

        _, kwargs = mock_interaction.response.send_message.call_args
        assert "The leaderboard is empty" in kwargs['embed'].description

@pytest.mark.asyncio
@patch("src.commands.result.get_session")
@patch("src.commands.result.ADMIN_IDS", [999]) # Non-admin user
async def test_enter_result_not_admin(mock_get_session, mock_interaction, mock_session):
    """Test that a non-admin cannot use /enter_result."""
    mock_get_session.return_value = iter([mock_session])

    await result.enter_result.callback(mock_interaction, match_id=1, winner="Team A")

    mock_interaction.response.send_message.assert_called_once_with(
        "You do not have permission to use this command.", ephemeral=True
    )

@pytest.mark.asyncio
@patch("src.commands.result.get_session")
@patch("src.commands.result.ADMIN_IDS", [123]) # Admin user
async def test_enter_result_success(mock_get_session, mock_interaction, mock_session):
    """Test successful entry of a match result."""
    mock_get_session.return_value = iter([mock_session])

    # Mock data
    test_match = Match(id=1, contest_id=1, team1="Team A", team2="Team B", scheduled_time=datetime.now(timezone.utc))
    test_picks = [
        PickModel(id=1, user_id=1, match_id=1, chosen_team="Team A"),
        PickModel(id=2, user_id=2, match_id=1, chosen_team="Team B"),
    ]

    with patch("src.commands.result.crud") as mock_crud:
        mock_crud.get_match_by_id.return_value = test_match
        mock_crud.get_result_for_match.return_value = None # No existing result
        mock_crud.list_picks_for_match.return_value = test_picks

        await result.enter_result.callback(mock_interaction, match_id=1, winner="Team A")

        # Assertions
        mock_crud.create_result.assert_called_once_with(mock_session, match_id=1, winner="Team A")
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_called_once()

        # Check if picks were scored correctly
        assert test_picks[0].status == "correct"
        assert test_picks[0].score == 10
        assert test_picks[1].status == "incorrect"
        assert test_picks[1].score == 0

        mock_interaction.followup.send.assert_called_once()
        args, _ = mock_interaction.followup.send.call_args
        assert "Result for match" in args[0]
        assert "Processed and scored 2 user picks" in args[0]

# --- Setup Function Tests ---

@pytest.mark.asyncio
async def test_all_setups(mock_bot):
    """Test that all setup functions run without errors."""
    await pick.setup(mock_bot)
    mock_bot.tree.add_command.assert_called_with(pick.pick)

    await picks.setup(mock_bot)
    mock_bot.tree.add_command.assert_called_with(picks.picks_group)

    await stats.setup(mock_bot)
    mock_bot.tree.add_command.assert_called_with(stats.stats)

    await matches.setup(mock_bot)
    mock_bot.tree.add_command.assert_called_with(matches.matches_group)

    await result.setup(mock_bot)
    mock_bot.tree.add_command.assert_called_with(result.enter_result)

    # Leaderboard setup needs the bot instance
    await leaderboard.setup(mock_bot)
    assert mock_bot.tree.add_command.call_count == 7 # 5 above + 2 in leaderboard
import pytest
from unittest.mock import MagicMock, patch
from src.commands.leaderboard import get_leaderboard_data


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def mock_bot():
    with patch("src.commands.leaderboard.get_bot_instance") as mock:
        yield mock


@pytest.mark.asyncio
async def test_get_leaderboard_data_uses_sql_filter_small_guild(
    mock_session, mock_bot
):
    # Setup guild with small number of members
    guild = MagicMock()
    guild.members = [MagicMock(id=123), MagicMock(id=456)]
    mock_bot.return_value.get_guild.return_value = guild

    # Mock session.exec().all() to return empty list
    mock_session.exec.return_value.all.return_value = []

    # Spy on _apply_guild_filter to verify arguments
    with patch("src.commands.leaderboard._apply_guild_filter") as mock_apply:
        mock_apply.return_value = []

        await get_leaderboard_data(mock_session, guild_id=999)

        # Verify session.exec was called
        assert mock_session.exec.called
        args, _ = mock_session.exec.call_args
        query = args[0]

        # Check that query contains WHERE clause with IN
        # Compiling the query to string to check for IN clause
        # Note: This depends on the dialect, but usually works for standard SQL
        query_str = str(query)
        # Checking if "user.discord_id IN" or similar is present
        # Or check if WHERE clause is present
        assert "WHERE" in query_str
        # Inspecting the where clause logic is hard on compiled string,
        # but we can check if _apply_guild_filter was called with guild_id=None
        # because our optimization plan says we pass None if filtered in SQL.

        mock_apply.assert_called_once()
        call_args = mock_apply.call_args
        # args: (results, guild_id, is_accuracy_based)
        # We expect guild_id to be None
        assert call_args[0][1] is None


@pytest.mark.asyncio
async def test_get_leaderboard_data_fallback_large_guild(
    mock_session, mock_bot
):
    # Setup guild with large number of members (> 900)
    guild = MagicMock()
    # Create 901 members
    guild.members = [MagicMock(id=i) for i in range(901)]
    mock_bot.return_value.get_guild.return_value = guild

    mock_session.exec.return_value.all.return_value = []

    with patch("src.commands.leaderboard._apply_guild_filter") as mock_apply:
        mock_apply.return_value = []

        await get_leaderboard_data(mock_session, guild_id=999)

        # Verify _apply_guild_filter was called with the original guild_id
        # (999) because we fell back to Python filtering
        mock_apply.assert_called_once()
        call_args = mock_apply.call_args
        assert call_args[0][1] == 999

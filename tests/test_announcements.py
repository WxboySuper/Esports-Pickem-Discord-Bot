import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from src.announcements import (
    get_admin_channel,
    send_admin_update,
    ADMIN_CHANNEL_NAME,
)


@pytest.fixture
def mock_guild():

    guild = MagicMock(spec=discord.Guild)
    guild.text_channels = []
    guild.create_text_channel = AsyncMock()
    guild.default_role = MagicMock()
    guild.me = MagicMock()
    guild.id = 12345
    return guild


@pytest.fixture
def mock_channel():
    channel = AsyncMock(spec=discord.TextChannel)
    channel.name = ADMIN_CHANNEL_NAME
    return channel


@pytest.mark.asyncio
async def test_get_admin_channel_existing(mock_guild, mock_channel):
    """Test retrieving an existing admin channel."""
    mock_guild.text_channels = [mock_channel]

    result = await get_admin_channel(mock_guild)

    assert result == mock_channel
    mock_guild.create_text_channel.assert_not_called()


@pytest.mark.asyncio
async def test_get_admin_channel_create(mock_guild):
    """Test creating an admin channel if it doesn't exist."""
    new_channel = AsyncMock(spec=discord.TextChannel)
    mock_guild.create_text_channel.return_value = new_channel

    result = await get_admin_channel(mock_guild)

    assert result == new_channel
    mock_guild.create_text_channel.assert_called_once()
    args, kwargs = mock_guild.create_text_channel.call_args
    assert args[0] == ADMIN_CHANNEL_NAME
    assert kwargs["overwrites"][mock_guild.default_role].send_messages is False
    assert kwargs["overwrites"][mock_guild.me].send_messages is True


@pytest.mark.asyncio
async def test_get_admin_channel_create_forbidden(mock_guild):
    """Test get_admin_channel returns None when creation is forbidden."""
    mock_guild.create_text_channel.side_effect = discord.Forbidden(
        MagicMock(), "Forbidden"
    )

    result = await get_admin_channel(mock_guild)

    assert result is None
    mock_guild.create_text_channel.assert_called_once()


@pytest.mark.asyncio
@patch("src.announcements.get_bot_instance")
@patch("src.announcements.os.getenv")
async def test_send_admin_update_success(
    mock_getenv, mock_get_bot, mock_guild, mock_channel
):
    """Test successful admin update sending."""
    mock_bot = MagicMock()
    mock_get_bot.return_value = mock_bot
    mock_bot.get_guild.return_value = mock_guild
    mock_getenv.return_value = "12345"

    with patch(
        "src.announcements.get_admin_channel",
        new=AsyncMock(return_value=mock_channel),
    ) as mock_get_channel:
        await send_admin_update("Test message")

        mock_get_bot.assert_called_once()
        mock_bot.get_guild.assert_called_once_with(12345)
        mock_get_channel.assert_called_once_with(mock_guild)
        mock_channel.send.assert_called_once_with("Test message")


@pytest.mark.asyncio
@patch("src.announcements.get_bot_instance")
@patch("src.announcements.os.getenv")
async def test_send_admin_update_with_mention(
    mock_getenv, mock_get_bot, mock_guild, mock_channel
):
    """Test admin update with user mention."""
    mock_bot = MagicMock()
    mock_get_bot.return_value = mock_bot
    mock_bot.get_guild.return_value = mock_guild
    mock_getenv.return_value = "12345"

    with patch(
        "src.announcements.get_admin_channel",
        new=AsyncMock(return_value=mock_channel),
    ):
        await send_admin_update("Test message", mention_user_id=999)

        mock_channel.send.assert_called_once_with("<@999> Test message")


@pytest.mark.asyncio
@patch("src.announcements.get_bot_instance")
async def test_send_admin_update_no_bot(mock_get_bot):
    """Test send_admin_update when bot instance is missing."""
    mock_get_bot.return_value = None

    await send_admin_update("Test")

    # Should just return without error
    mock_get_bot.assert_called_once()


@pytest.mark.asyncio
@patch("src.announcements.get_bot_instance")
@patch("src.announcements.os.getenv")
async def test_send_admin_update_no_env_var(mock_getenv, mock_get_bot):
    """Test send_admin_update when DEVELOPER_GUILD_ID is not set."""
    mock_get_bot.return_value = MagicMock()
    mock_getenv.return_value = None

    await send_admin_update("Test")

    mock_getenv.assert_called_with("DEVELOPER_GUILD_ID")


@pytest.mark.asyncio
@patch("src.announcements.get_bot_instance")
@patch("src.announcements.os.getenv")
async def test_send_admin_update_guild_not_found(mock_getenv, mock_get_bot):
    """Test send_admin_update when guild is not found."""
    mock_bot = MagicMock()
    mock_bot.get_guild.return_value = None
    mock_get_bot.return_value = mock_bot
    mock_getenv.return_value = "12345"

    with patch("src.announcements.get_admin_channel") as mock_get_channel:
        await send_admin_update("Test")

        mock_bot.get_guild.assert_called_once_with(12345)
        mock_get_channel.assert_not_called()


@pytest.mark.asyncio
@patch("src.announcements.get_bot_instance")
@patch("src.announcements.os.getenv")
async def test_send_admin_update_no_channel(
    mock_getenv, mock_get_bot, mock_guild
):
    """Test send_admin_update when admin channel cannot be found/created."""
    mock_bot = MagicMock()
    mock_get_bot.return_value = mock_bot
    mock_bot.get_guild.return_value = mock_guild
    mock_getenv.return_value = "12345"

    with patch(
        "src.announcements.get_admin_channel", new=AsyncMock(return_value=None)
    ):
        await send_admin_update("Test")
        # Should gracefully return without error
        pass


@pytest.mark.asyncio
@patch("src.announcements.get_bot_instance")
@patch("src.announcements.os.getenv")
async def test_send_admin_update_send_failure(
    mock_getenv, mock_get_bot, mock_guild, mock_channel
):
    """Test send_admin_update handling send exception."""
    mock_bot = MagicMock()
    mock_get_bot.return_value = mock_bot
    mock_bot.get_guild.return_value = mock_guild
    mock_getenv.return_value = "12345"

    mock_channel.send.side_effect = discord.HTTPException(
        response=MagicMock(), message="Failed"
    )

    with patch(
        "src.announcements.get_admin_channel",
        new=AsyncMock(return_value=mock_channel),
    ):
        # Should catch exception and log it, not raise
        await send_admin_update("Test")

        mock_channel.send.assert_called_once()

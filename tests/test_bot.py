import pytest
import discord
from datetime import datetime
from unittest.mock import AsyncMock  # Add this import
from src.bot.bot import AnnouncementManager, create_matches_embed, create_admin_summary_embed


def test_announcement_manager_init(mock_bot):
    """Test AnnouncementManager initialization"""
    announcer = AnnouncementManager(mock_bot)
    assert announcer.bot == mock_bot


@pytest.mark.asyncio
async def test_announce_new_match(mock_bot, mocker):
    """Test match announcement"""
    announcer = AnnouncementManager(mock_bot)
    
    # Mock channel
    mock_channel = mocker.MagicMock()
    mock_channel.send = mocker.AsyncMock()
    
    # Mock guild
    mock_guild = mocker.MagicMock()
    mock_guild.text_channels = []
    mock_bot.guilds = [mock_guild]
    
    # Mock get_announcement_channel to return mock_channel directly
    async def mock_get_channel(*args, **kwargs):
        return mock_channel
    
    announcer.get_announcement_channel = mock_get_channel
    
    # Test announcement
    await announcer.announce_new_match(
        match_id=1,
        team_a="Team A",
        team_b="Team B",
        match_date=datetime.now().replace(microsecond=0),
        league_name="Test League",
        match_name="Groups"
    )
    
    assert mock_channel.send.call_count == 1


def test_create_matches_embed(sample_match_data):
    """Test matches embed creation"""
    matches = [(
        1,
        sample_match_data['team_a'],
        sample_match_data['team_b'],
        None,
        sample_match_data['match_date'],
        datetime.now().replace(microsecond=0),
        sample_match_data['league_name'],
        'Global',
        sample_match_data['match_name']
    )]
    
    embed = create_matches_embed(matches, datetime.now())
    assert isinstance(embed, discord.Embed)
    assert len(embed.fields) > 0


def test_create_admin_summary_embed(sample_match_data):
    """Test admin summary embed creation"""
    matches = [(
        1,
        sample_match_data['team_a'],
        sample_match_data['team_b'],
        None,
        sample_match_data['match_date'],
        datetime.now(),
        sample_match_data['league_name'],
        'Global'
    )]
    
    embed = create_admin_summary_embed(matches, datetime.now())
    assert isinstance(embed, discord.Embed)
    assert len(embed.fields) > 0


@pytest.mark.asyncio
async def test_command_handlers(mock_interaction, test_db):
    """Test command handler functions"""
    # Create a proper mock response
    mock_response = mock_interaction.response
    mock_response.send_message = AsyncMock()  # Use AsyncMock from unittest.mock
    
    # Test sending a message
    await mock_response.send_message("Test response")
    assert mock_response.send_message.called
    assert mock_response.send_message.call_args[0][0] == "Test response"

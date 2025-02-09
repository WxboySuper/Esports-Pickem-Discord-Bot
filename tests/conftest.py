import pytest
import os
from datetime import datetime
from src.utils.db import PickemDB
import asyncio
import discord

@pytest.fixture(scope="function")
async def test_db():
    """Create a temporary test database"""
    db_path = f"test_pickem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db"
    
    db = PickemDB(db_path)
    yield db
    
    # Close any open connections
    db = None
    
    # Wait a bit to ensure connections are closed
    await asyncio.sleep(0.1)
    
    # Cleanup
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass  # Ignore if file is still locked

@pytest.fixture
def sample_match_data():
    """Provide sample match data for tests"""
    now = datetime.now().replace(microsecond=0)  # Remove microseconds
    return {
        'team_a': 'Team A',
        'team_b': 'Team B',
        'match_date': now,
        'match_name': 'Groups',
        'league_name': 'Test League'
    }

@pytest.fixture
def mock_bot(mocker):
    """Create a mock bot instance"""
    mock = mocker.MagicMock(spec=discord.Client)
    mock.guilds = []
    mock.user = mocker.MagicMock(spec=discord.ClientUser)
    mock.user.name = "Test Bot"
    return mock

@pytest.fixture
def mock_interaction(mocker):
    """Create a mock Discord interaction"""
    interaction = mocker.MagicMock(spec=discord.Interaction)
    interaction.guild_id = 123
    interaction.user = mocker.MagicMock(spec=discord.Member)
    interaction.user.id = 456
    interaction.user.display_name = "Test User"
    interaction.guild = mocker.MagicMock(spec=discord.Guild)
    interaction.guild.name = "Test Guild"
    interaction.response = mocker.AsyncMock()
    return interaction

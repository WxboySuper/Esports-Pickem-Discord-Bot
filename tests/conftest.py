import unittest
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import discord
import sqlite3
from src.utils.db import PickemDB

class BaseTestCase(unittest.TestCase):
    """Base test case class with shared setup and helper methods"""

    def setUp(self):
        """Set up test environment before each test"""
        # Create unique test database path
        self.db_path = f"test_pickem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db"
        self.db = PickemDB(self.db_path)

        # Store patches for cleanup
        self.patches = []

        # Create sample data and mocks
        self._create_sample_data()
        self._create_mocks()

    def tearDown(self):
        """Clean up after each test"""
        # Close database connection
        if hasattr(self, 'db') and self.db is not None:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None

        # Remove test database file
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except (PermissionError, OSError):
                # If file is locked, try to close any remaining connections
                try:
                    sqlite3.connect(self.db_path).close()
                    os.remove(self.db_path)
                except Exception:
                    pass

        # Clean up patches
        for p in self.patches:
            p.stop()
        self.patches.clear()

        # Clean up mocks
        self.mock_bot = None
        self.mock_interaction = None

    def _create_sample_data(self):
        """Create sample test data"""
        now = datetime.now().replace(microsecond=0)
        self.sample_match_data = {
            'team_a': 'Team A',
            'team_b': 'Team B',
            'match_date': now,
            'match_name': 'Groups',
            'league_name': 'Test League'
        }

    def _create_mocks(self):
        """Create mock objects used in tests"""
        # Create mock bot
        self.mock_bot = MagicMock(spec=discord.Client)
        self.mock_bot.guilds = []
        self.mock_bot.user = MagicMock(spec=discord.ClientUser)
        self.mock_bot.user.name = "Test Bot"

        # Create mock interaction
        self.mock_interaction = MagicMock(spec=discord.Interaction)
        self.mock_interaction.guild_id = 123
        self.mock_interaction.user = MagicMock(spec=discord.Member)
        self.mock_interaction.user.id = 456
        self.mock_interaction.user.display_name = "Test User"
        self.mock_interaction.guild = MagicMock(spec=discord.Guild)
        self.mock_interaction.guild.name = "Test Guild"
        self.mock_interaction.response = AsyncMock()

    def create_patch(self, *args, **kwargs):
        """Helper to create a patch that will be automatically cleaned up"""
        patcher = patch(*args, **kwargs)
        self.patches.append(patcher)
        return patcher.start()

if __name__ == '__main__':
    unittest.main()

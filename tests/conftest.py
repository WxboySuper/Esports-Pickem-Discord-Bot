import unittest
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import discord
import sqlite3
from src.utils.db import PickemDB
import psutil
import time

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
                # Close any open cursors
                if hasattr(self.db, '_cursor') and self.db._cursor is not None:
                    self.db._cursor.close()
                # Close the connection
                if hasattr(self.db, '_conn') and self.db._conn is not None:
                    self.db._conn.close()
                self.db = None
            except Exception as e:
                print(f"Error closing database: {e}")

        # Remove test database file with retry logic
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Force close any remaining connections
                    connections = []
                    for proc in psutil.process_iter(['pid', 'open_files']):
                        try:
                            for file in proc.open_files():
                                if self.db_path in file.path:
                                    connections.append(proc)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    # Terminate processes holding the file
                    for proc in connections:
                        try:
                            proc.terminate()
                        except psutil.NoSuchProcess:
                            pass

                    # Try to remove the file
                    os.remove(self.db_path)
                    break
                except (PermissionError, OSError) as e:
                    if attempt == max_retries - 1:
                        print(f"Failed to remove database file after {max_retries} attempts: {e}")
                    else:
                        time.sleep(0.1)

        # Clean up mocks and patches
        self.mock_bot = None
        self.mock_interaction = None
        for p in self.patches:
            p.stop()
        self.patches.clear()

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

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from datetime import datetime
from src.bot.bot import AnnouncementManager, create_matches_embed, create_admin_summary_embed
import os
import sqlite3

class TestBot(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        self.mock_bot = MagicMock()
        self.mock_bot.guilds = []
        self.mock_bot.user = MagicMock()
        self.mock_bot.user.name = "Test Bot"

        self.sample_match_data = {
            'team_a': 'Team A',
            'team_b': 'Team B',
            'match_date': datetime.now().replace(microsecond=0),
            'match_name': 'Groups',
            'league_name': 'Test League'
        }

        # Store any patches we create so we can clean them up
        self.patches = []

    def tearDown(self):
        """Clean up test database after each test"""
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

    def test_announcement_manager_init(self):
        """Test AnnouncementManager initialization"""
        announcer = AnnouncementManager(self.mock_bot)
        self.assertEqual(announcer.bot, self.mock_bot)

    async def test_announce_new_match(self):
        """Test match announcement"""
        announcer = AnnouncementManager(self.mock_bot)

        # Mock channel
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        # Mock guild
        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        self.mock_bot.guilds = [mock_guild]

        # Test announcement
        success = await announcer.announce_new_match(
            match_id=1,
            team_a=self.sample_match_data['team_a'],
            team_b=self.sample_match_data['team_b'],
            match_date=self.sample_match_data['match_date'],
            league_name=self.sample_match_data['league_name'],
            match_name=self.sample_match_data['match_name']
        )

        self.assertTrue(success)
        self.assertEqual(mock_channel.send.call_count, 1)

    def test_create_matches_embed(self):
        """Test matches embed creation"""
        matches = [(
            1,
            self.sample_match_data['team_a'],
            self.sample_match_data['team_b'],
            None,
            self.sample_match_data['match_date'],
            datetime.now(),
            self.sample_match_data['league_name'],
            'Global',
            self.sample_match_data['match_name']
        )]

        embed = create_matches_embed(matches, datetime.now())
        self.assertIsInstance(embed, discord.Embed)
        self.assertGreater(len(embed.fields), 0)

    def test_create_admin_summary_embed(self):
        """Test admin summary embed creation"""
        matches = [(
            1,
            self.sample_match_data['team_a'],
            self.sample_match_data['team_b'],
            None,
            self.sample_match_data['match_date'],
            datetime.now(),
            self.sample_match_data['league_name'],
            'Global',
            self.sample_match_data['match_name']
        )]

        embed = create_admin_summary_embed(matches, datetime.now())
        self.assertIsInstance(embed, discord.Embed)
        self.assertGreater(len(embed.fields), 0)

    def create_patch(self, *args, **kwargs):
        """Helper to create a patch that will be automatically cleaned up"""
        patcher = patch(*args, **kwargs)
        self.patches.append(patcher)
        return patcher.start()

if __name__ == '__main__':
    unittest.main()

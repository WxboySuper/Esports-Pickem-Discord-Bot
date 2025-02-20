import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from datetime import datetime
from src.bot.bot import AnnouncementManager, create_matches_embed, create_admin_summary_embed

class TestBot(unittest.IsolatedAsyncioTestCase):  # Change to IsolatedAsyncioTestCase
    async def asyncSetUp(self):  # Change to asyncSetUp
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

    async def asyncTearDown(self):  # Add proper async teardown
        """Clean up test environment after each test"""
        # Clean up any patches
        for p in self.patches:
            p.stop()
        self.patches.clear()

        # Cancel any pending tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    async def test_announcement_manager_init(self):  # Make test methods async
        """Test AnnouncementManager initialization"""
        announcer = AnnouncementManager(self.mock_bot)
        self.assertEqual(announcer.bot, self.mock_bot)

    async def test_announce_new_match(self):
        """Test match announcement"""
        announcer = AnnouncementManager(self.mock_bot)

        # Mock channel and send method
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock()

        # Mock guild and get_announcement_channel
        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        self.mock_bot.guilds = [mock_guild]

        # Mock get_announcement_channel
        with patch.object(AnnouncementManager, 'get_announcement_channel', return_value=mock_channel):
            success = await announcer.announce_new_match(
                match_id=1,
                team_a=self.sample_match_data['team_a'],
                team_b=self.sample_match_data['team_b'],
                match_date=self.sample_match_data['match_date'],
                league_name=self.sample_match_data['league_name'],
                match_name=self.sample_match_data['match_name']
            )

            self.assertTrue(success)
            mock_channel.send.assert_awaited_once()

            # Verify embed content
            call_args = mock_channel.send.call_args
            self.assertIsNotNone(call_args)
            _, kwargs = call_args
            embed = kwargs.get('embed')
            self.assertIsInstance(embed, discord.Embed)
            self.assertEqual(embed.title, "🎮 New Match Scheduled!")

    async def test_create_matches_embed(self):
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

    async def test_create_admin_summary_embed(self):
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

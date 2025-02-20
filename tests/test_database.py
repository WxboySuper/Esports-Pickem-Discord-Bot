import unittest
import os
from datetime import datetime, timedelta
import sqlite3
from unittest.mock import MagicMock, patch
from src.utils.db import PickemDB
from src.utils.bot_instance import BotInstance

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Set up test database before each test"""
        # Create a mock bot instance
        self.mock_bot = MagicMock()
        self.mock_user = MagicMock()
        self.mock_user.name = "Test User"
        self.mock_bot.get_user.return_value = self.mock_user

        # Create sample match data
        self.sample_match_data = {
            'team_a': 'Team A',
            'team_b': 'Team B',
            'match_date': datetime.now().replace(microsecond=0),
            'match_name': 'Groups',
            'league_name': 'Test League'
        }

        # Generate unique test database name using timestamp
        self.db_path = f"test_pickem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db"

        # Store patches for cleanup
        self.patches = []

        # Patch BotInstance
        self.bot_patcher = self.create_patch(
            'src.utils.bot_instance.BotInstance.get_bot',
            return_value=self.mock_bot
        )

        # Initialize database
        self.db = PickemDB(self.db_path)

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

    def create_patch(self, *args, **kwargs):
        """Helper to create a patch that will be automatically cleaned up"""
        patcher = patch(*args, **kwargs)
        self.patches.append(patcher)
        return patcher.start()

    def test_db_initialization(self):
        """Test database initialization"""
        self.assertIsNotNone(self.db)
        self.assertIsInstance(self.db.db_path, str)
        self.assertTrue(self.db.db_path.startswith("test_pickem_"))
        self.assertTrue(self.db.db_path.endswith(".db"))

    def test_add_match(self):
        """Test adding a match"""
        match_id = self.db.add_match(
            league_id=1,
            team_a=self.sample_match_data['team_a'],
            team_b=self.sample_match_data['team_b'],
            match_date=self.sample_match_data['match_date'],
            match_name=self.sample_match_data['match_name'],
            is_active=1
        )
        self.assertIsNotNone(match_id)
        self.assertGreater(match_id, 0)

    def test_make_pick(self):
        """Test making a pick"""
        # Add a match first
        match_id = self.db.add_match(
            league_id=1,
            team_a=self.sample_match_data['team_a'],
            team_b=self.sample_match_data['team_b'],
            match_date=datetime.now() + timedelta(days=1),
            match_name=self.sample_match_data['match_name'],
            is_active=1
        )

        # Make a pick
        success = self.db.make_pick(
            guild_id=123,
            user_id=456,
            match_id=match_id,
            pick=self.sample_match_data['team_a']
        )
        self.assertTrue(success)

        # Verify pick
        pick = self.db.get_user_pick(123, 456, match_id)
        self.assertEqual(pick, self.sample_match_data['team_a'])

    def test_update_match_result(self):
        """Test updating match result"""
        # Add a match
        match_id = self.db.add_match(
            league_id=1,
            team_a=self.sample_match_data['team_a'],
            team_b=self.sample_match_data['team_b'],
            match_date=datetime.now(),
            match_name=self.sample_match_data['match_name'],
            is_active=1
        )
        
        # Update result
        success = self.db.update_match_result(match_id, self.sample_match_data['team_a'])
        self.assertTrue(success)

    def test_get_leaderboard(self):
        """Test leaderboard functionality"""
        # Add matches with all correct picks
        match_ids = []
        base_date = datetime.now() - timedelta(hours=1)
        
        for i in range(10):
            match_id = self.db.add_match(
                league_id=1,
                team_a=f"Team A{i}",
                team_b=f"Team B{i}",
                match_date=base_date + timedelta(minutes=i),
                match_name=self.sample_match_data['match_name'],
                is_active=1
            )
            match_ids.append(match_id)
            
            # Verify match was created
            self.assertIsNotNone(match_id, f"Failed to create match {i}")
            
            # Make pick and verify database state
            with sqlite3.connect(self.db.db_path) as conn:
                c = conn.cursor()

                # Verify match exists and is open
                match_exists = c.execute("""
                    SELECT COUNT(*) FROM matches
                    WHERE match_id = ? AND winner IS NULL
                """, (match_id,)).fetchone()[0]
                self.assertEqual(match_exists, 1, f"Match {match_id} not found or already closed")

                # Make pick
                pick_success = self.db.make_pick(123, 456, match_id, f"Team A{i}")
                self.assertTrue(pick_success, f"Failed to make pick for match {match_id}")

                # Verify pick was recorded
                pick_recorded = c.execute("""
                    SELECT COUNT(*) FROM picks
                    WHERE match_id = ? AND guild_id = ? AND user_id = ?
                """, (match_id, 123, 456)).fetchone()[0]
                self.assertEqual(pick_recorded, 1, f"Pick not found for match {match_id}")
            
            # Update match result
            result_success = self.db.update_match_result(match_id, f"Team A{i}")
            self.assertTrue(result_success, f"Failed to update result for match {match_id}")

        # Get leaderboard and verify results
        leaderboard = self.db.get_leaderboard_by_timeframe(123, 'all')
        self.assertGreater(len(leaderboard), 0, "Leaderboard should have entries")
        
        # Verify first entry
        entry = leaderboard[0]
        self.assertEqual(entry[0], 456, "Expected user_id 456")
        self.assertEqual(entry[1], 10, "Expected 10 completed picks")
        self.assertEqual(entry[2], 10, "Expected 10 correct picks")
        self.assertEqual(entry[3], 1.0, "Expected perfect accuracy")

    def test_invalid_operations(self):
        """Test handling of invalid operations"""
        # Test invalid match ID
        self.assertIsNone(self.db.get_match_details(999))
        
        # Test invalid pick
        self.assertFalse(self.db.make_pick(123, 456, 999, "Invalid Team"))

if __name__ == '__main__':
    unittest.main()

import unittest
import os
from datetime import datetime, timedelta
import sqlite3
from unittest.mock import MagicMock, patch
from src.utils.db import PickemDB


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Set up test database before each test"""
        # Create sample match data before database initialization
        self.sample_match_data = {
            'team_a': 'Team A',
            'team_b': 'Team B',
            'match_date': datetime.now().replace(microsecond=0) + timedelta(days=1),
            'match_name': 'Groups',
            'league_name': 'Test League'
        }

        # Use memory database for faster tests
        self.db_path = ":memory:"
        self.db = None

        # Create patches for cleanup
        self.patches = []

        # Create a mock bot
        self.mock_bot = MagicMock()
        self.mock_bot.announcer = MagicMock()

        # Patch BotInstance before database initialization
        self.bot_patcher = self.create_patch(
            'src.utils.bot_instance.BotInstance.get_bot',
            return_value=self.mock_bot
        )

        try:
            # Initialize database with in-memory connection
            self.db = PickemDB(self.db_path)

            # Create tables explicitly and commit immediately
            self.db._cursor.executescript('''
                CREATE TABLE IF NOT EXISTS leagues (
                    league_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    region TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS matches (
                    match_id INTEGER PRIMARY KEY,
                    league_id INTEGER NOT NULL,
                    team_a TEXT NOT NULL,
                    team_b TEXT NOT NULL,
                    winner TEXT,
                    match_date TIMESTAMP,
                    match_name TEXT NOT NULL DEFAULT 'Groups',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (league_id) REFERENCES leagues (league_id)
                );

                CREATE TABLE IF NOT EXISTS picks (
                    pick_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    match_id INTEGER NOT NULL,
                    pick TEXT NOT NULL,
                    is_correct BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches (match_id),
                    UNIQUE(guild_id, user_id, match_id)
                );
            ''')
            self.db._conn.commit()

            # Add default league
            self.db._cursor.execute("""
                INSERT INTO leagues (name, description, region)
                VALUES (?, ?, ?)
            """, ("Test League", "Test League Description", "Test Region"))
            self.db._conn.commit()

            # Store league ID
            self.league_id = self.db._cursor.lastrowid

            # Verify tables exist
            tables = self.db._cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('leagues', 'matches', 'picks')
            """).fetchall()

            if len(tables) != 3:
                raise sqlite3.OperationalError("Failed to create all required tables")

        except Exception as e:
            self.fail(f"Failed to set up test database: {str(e)}")

    def tearDown(self):
        """Clean up test database after each test"""
        # Close database connection
        if hasattr(self, 'db') and self.db is not None:
            try:
                if hasattr(self.db, '_cursor') and self.db._cursor is not None:
                    self.db._cursor.close()
                if hasattr(self.db, '_conn') and self.db._conn is not None:
                    self.db._conn.close()
                self.db = None
            except Exception as e:
                print(f"Error closing database: {e}")

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
        try:
            # Skip file existence check for in-memory database
            if self.db_path != ":memory:":
                self.assertTrue(os.path.exists(self.db_path), "Database file was not created")

            # Verify db object properties
            self.assertIsNotNone(self.db, "Database object is None")
            self.assertIsInstance(self.db.db_path, str, "Database path is not a string")

            # Use the existing connection from PickemDB instead of creating new one
            cursor = self.db._cursor

            # Check for required tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            self.assertIn('leagues', tables, "leagues table not found")
            self.assertIn('matches', tables, "matches table not found")
            self.assertIn('picks', tables, "picks table not found")

            # Verify table schemas
            cursor.execute("PRAGMA table_info(leagues)")
            league_columns = {row[1] for row in cursor.fetchall()}
            self.assertIn('league_id', league_columns)
            self.assertIn('name', league_columns)

            cursor.execute("PRAGMA table_info(matches)")
            match_columns = {row[1] for row in cursor.fetchall()}
            self.assertIn('match_id', match_columns)
            self.assertIn('team_a', match_columns)
            self.assertIn('team_b', match_columns)

            cursor.execute("PRAGMA table_info(picks)")
            pick_columns = {row[1] for row in cursor.fetchall()}
            self.assertIn('pick_id', pick_columns)
            self.assertIn('user_id', pick_columns)
            self.assertIn('match_id', pick_columns)

        except Exception as e:
            self.fail(f"Test failed with error: {e}")

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
        # Add a user with no correct picks
        no_picks_match = self.db.add_match(
            league_id=1,
            team_a="Team X",
            team_b="Team Y",
            match_date=base_date - timedelta(minutes=5),
            match_name=self.sample_match_data['match_name'],
            is_active=1
        )
        self.db.make_pick(123, 789, no_picks_match, "Team X")
        self.db.update_match_result(no_picks_match, "Team Y")
        # Add users with tied scores
        for user_id in [111, 222]:
            match_id = self.db.add_match(
                league_id=1,
                team_a="Team Tie",
                team_b="Team Other",
                match_date=base_date - timedelta(minutes=10),
                match_name=self.sample_match_data['match_name'],
                is_active=1
            )
            self.db.make_pick(123, user_id, match_id, "Team Tie")
            self.db.update_match_result(match_id, "Team Tie")
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
            # Verify match exists and is open using instance connection
            match_exists = self.db._cursor.execute("""
                SELECT COUNT(*) FROM matches
                WHERE match_id = ? AND winner IS NULL
            """, (match_id,)).fetchone()[0]
            self.assertEqual(match_exists, 1, f"Match {match_id} not found or already closed")
            # Make pick
            pick_success = self.db.make_pick(123, 456, match_id, f"Team A{i}")
            self.assertTrue(pick_success, f"Failed to make pick for match {match_id}")
            # Verify pick was recorded using instance connection
            pick_recorded = self.db._cursor.execute("""
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
        # Verify tied users
        tied_entries = [entry for entry in leaderboard if entry[0] in [111, 222]]
        self.assertEqual(len(tied_entries), 2, "Expected two tied users")
        self.assertEqual(tied_entries[0][2], tied_entries[1][2], "Tied users should have same correct picks")
        # Verify user with no correct picks
        no_picks_entry = next((entry for entry in leaderboard if entry[0] == 789), None)
        self.assertIsNotNone(no_picks_entry, "User with no correct picks should be in leaderboard")
        self.assertEqual(no_picks_entry[2], 0, "Expected 0 correct picks")

    def test_invalid_operations(self):
        """Test handling of invalid operations"""
        # Test invalid match ID
        self.assertIsNone(self.db.get_match_details(999))

        # Test invalid pick
        self.assertFalse(self.db.make_pick(123, 456, 999, "Invalid Team"))

if __name__ == '__main__':
    unittest.main()

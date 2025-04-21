import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from src.database.models.picks import Pick
from src.database.models.user import User # Added import
from src.database.models.match import Match # Added import
from datetime import datetime, timezone # Added import

class TestPick(unittest.IsolatedAsyncioTestCase):

    # --- Tests for Pick.create ---
    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_create_pick_success(self, mock_log, mock_get_user, mock_get_match):
        mock_db = AsyncMock()
        mock_db.execute.return_value = 1 # Simulate successful insertion with pick ID 1

        # Mock User and Match existence
        mock_user = MagicMock(spec=User)
        mock_user.user_id = 100
        mock_get_user.return_value = mock_user

        mock_match = MagicMock(spec=Match)
        mock_match.match_id = 200
        mock_get_match.return_value = mock_match

        user_id = 100
        match_id = 200
        pick_selection = "team1"

        pick = await Pick.create(
            db=mock_db,
            user_id=user_id,
            match_id=match_id,
            pick_selection=pick_selection
        )

        self.assertIsNotNone(pick)
        self.assertEqual(pick.pick_id, 1)
        self.assertEqual(pick.user_id, user_id)
        self.assertEqual(pick.match_id, match_id)
        self.assertEqual(pick.pick_selection, pick_selection)
        self.assertIsInstance(pick.pick_timestamp, datetime)
        # Check if timestamp is timezone-aware (UTC)
        self.assertIsNotNone(pick.pick_timestamp.tzinfo)
        self.assertEqual(pick.pick_timestamp.tzinfo, timezone.utc)
        self.assertIsNone(pick.is_correct)
        self.assertIsNone(pick.points_earned)

        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_get_match.assert_called_once_with(mock_db, match_id)

        expected_query = """
            INSERT INTO Picks (user_id, match_id, pick_selection, pick_timestamp)
            VALUES (?, ?, ?, ?)
        """.strip()
        # We can't assert the exact timestamp, so check the call structure
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1][0], user_id)
        self.assertEqual(call_args[1][1], match_id)
        self.assertEqual(call_args[1][2], pick_selection)
        self.assertIsInstance(call_args[1][3], datetime) # Check timestamp type

        mock_log.info.assert_any_call(f"Creating pick for user {user_id} on match {match_id} with selection {pick_selection}")
        mock_log.info.assert_any_call(f"Pick successfully created with ID {pick.pick_id}")
        mock_log.debug.assert_called_once_with("Validating user and match existence for pick creation")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_create_pick_invalid_user_id(self, mock_log, mock_get_user, mock_get_match):
        """Test that creating a pick with invalid user_id raises ValueError"""
        mock_db = AsyncMock()
        
        with self.assertRaises(ValueError) as context:
            await Pick.create(
                db=mock_db,
                user_id=0,  # Invalid user_id
                match_id=1,
                pick_selection="team1"
            )
        
        self.assertEqual(str(context.exception), "Invalid user_id or match_id provided.")
        mock_get_user.assert_not_called()
        mock_get_match.assert_not_called()
        mock_log.error.assert_called_with("Invalid user_id or match_id provided.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_create_pick_invalid_match_id(self, mock_log, mock_get_user, mock_get_match):
        """Test that creating a pick with invalid match_id raises ValueError"""
        mock_db = AsyncMock()
        
        with self.assertRaises(ValueError) as context:
            await Pick.create(
                db=mock_db,
                user_id=1,
                match_id=-1,  # Invalid match_id
                pick_selection="team1"
            )
        
        self.assertEqual(str(context.exception), "Invalid user_id or match_id provided.")
        mock_get_user.assert_not_called()
        mock_get_match.assert_not_called()
        mock_log.error.assert_called_with("Invalid user_id or match_id provided.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_create_pick_nonexistent_user(self, mock_log, mock_get_user, mock_get_match):
        """Test that creating a pick for non-existent user raises ValueError"""
        mock_db = AsyncMock()
        mock_get_user.return_value = None  # User not found
        
        with self.assertRaises(ValueError) as context:
            await Pick.create(
                db=mock_db,
                user_id=999,
                match_id=1,
                pick_selection="team1"
            )
        
        self.assertEqual(str(context.exception), "User with ID 999 does not exist.")
        mock_get_user.assert_called_once_with(mock_db, 999)
        mock_get_match.assert_not_called()
        mock_log.error.assert_called_with("User with ID 999 does not exist.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_create_pick_nonexistent_match(self, mock_log, mock_get_user, mock_get_match):
        """Test that creating a pick for non-existent match raises ValueError"""
        mock_db = AsyncMock()
        # Mock successful user validation
        mock_user = MagicMock(spec=User)
        mock_user.user_id = 1
        mock_get_user.return_value = mock_user
        
        # Mock match not found
        mock_get_match.return_value = None
        
        with self.assertRaises(ValueError) as context:
            await Pick.create(
                db=mock_db,
                user_id=1,
                match_id=999,
                pick_selection="team1"
            )
        
        self.assertEqual(str(context.exception), "Match with ID 999 does not exist.")
        mock_get_user.assert_called_once_with(mock_db, 1)
        mock_get_match.assert_called_once_with(mock_db, 999)
        mock_log.error.assert_called_with("Match with ID 999 does not exist.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_create_pick_database_error(self, mock_log, mock_get_user, mock_get_match):
        """Test that database error during pick creation is handled properly"""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Database error")

        # Mock successful user and match validation
        mock_user = MagicMock(spec=User)
        mock_user.user_id = 1
        mock_get_user.return_value = mock_user

        mock_match = MagicMock(spec=Match)
        mock_match.match_id = 1
        mock_get_match.return_value = mock_match

        with self.assertRaises(RuntimeError) as context:
            await Pick.create(
                db=mock_db,
                user_id=1,
                match_id=1,
                pick_selection="team1"
            )

        self.assertEqual(str(context.exception), "Database error creating pick: Database error")
        mock_get_user.assert_called_once_with(mock_db, 1)
        mock_get_match.assert_called_once_with(mock_db, 1)
        mock_log.error.assert_called_with("Database error creating pick for user 1 on match 1: Database error")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_create_pick_no_id_returned(self, mock_log, mock_get_user, mock_get_match):
        """Test handling of case where database insert succeeds but no ID is returned"""
        mock_db = AsyncMock()
        mock_db.execute.return_value = None  # Simulate no ID returned

        # Mock successful user and match validation
        mock_user = MagicMock(spec=User)
        mock_user.user_id = 1
        mock_get_user.return_value = mock_user

        mock_match = MagicMock(spec=Match)
        mock_match.match_id = 1
        mock_get_match.return_value = mock_match

        with self.assertRaises(RuntimeError) as context:
            await Pick.create(
                db=mock_db,
                user_id=1,
                match_id=1,
                pick_selection="team1"
            )

        self.assertEqual(str(context.exception), "Failed to create pick for user 1 on match 1 - no ID returned.")
        mock_get_user.assert_called_once_with(mock_db, 1)
        mock_get_match.assert_called_once_with(mock_db, 1)
        mock_log.error.assert_called_with("Failed to create pick for user 1 on match 1 - no ID returned.")

    # --- Tests for Pick.get_by_id ---
    @patch("src.database.models.picks.log")
    async def test_get_by_id_success(self, mock_log):
        """Test successful retrieval of a pick by ID"""
        mock_db = AsyncMock()
        pick_id = 1
        expected_data = {
            "pick_id": pick_id,
            "user_id": 100,
            "match_id": 200,
            "pick_selection": "team1",
            "pick_timestamp": datetime.now(timezone.utc),
            "is_correct": True,
            "points_earned": 10
        }
        mock_db.fetch_one.return_value = expected_data

        pick = await Pick.get_by_id(mock_db, pick_id)

        self.assertIsNotNone(pick)
        self.assertEqual(pick.pick_id, expected_data["pick_id"])
        self.assertEqual(pick.user_id, expected_data["user_id"])
        self.assertEqual(pick.match_id, expected_data["match_id"])
        self.assertEqual(pick.pick_selection, expected_data["pick_selection"])
        self.assertEqual(pick.pick_timestamp, expected_data["pick_timestamp"])
        self.assertEqual(pick.is_correct, expected_data["is_correct"])
        self.assertEqual(pick.points_earned, expected_data["points_earned"])

        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE pick_id = ?
        """.strip()
        mock_db.fetch_one.assert_called_once()
        call_args = mock_db.fetch_one.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (pick_id,))

        mock_log.debug.assert_called_once_with("Validating pick_id for retrieval")
        mock_log.info.assert_any_call(f"Retrieving pick with ID: {pick_id}")
        mock_log.info.assert_any_call(f"Pick with ID {pick_id} retrieved successfully.")

    @patch("src.database.models.picks.log")
    async def test_get_by_id_invalid_id(self, mock_log):
        """Test that retrieving a pick with invalid ID raises ValueError"""
        mock_db = AsyncMock()
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_id(mock_db, 0)  # Invalid pick_id
        
        self.assertEqual(str(context.exception), "Invalid pick_id provided.")
        mock_db.fetch_one.assert_not_called()
        mock_log.error.assert_called_with("Invalid pick_id provided.")

    @patch("src.database.models.picks.log")
    async def test_get_by_id_not_found(self, mock_log):
        """Test handling of non-existent pick ID"""
        mock_db = AsyncMock()
        pick_id = 999
        mock_db.fetch_one.return_value = None  # Simulate no pick found

        pick = await Pick.get_by_id(mock_db, pick_id)

        self.assertIsNone(pick)
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE pick_id = ?
        """.strip()
        mock_db.fetch_one.assert_called_once()
        call_args = mock_db.fetch_one.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (pick_id,))

        mock_log.warning.assert_called_once_with(f"No pick found with ID {pick_id}")

    @patch("src.database.models.picks.log")
    async def test_get_by_id_database_error(self, mock_log):
        """Test handling of database error during pick retrieval"""
        mock_db = AsyncMock()
        pick_id = 1
        mock_db.fetch_one.side_effect = Exception("Database error")

        with self.assertRaises(RuntimeError) as context:
            await Pick.get_by_id(mock_db, pick_id)

        self.assertEqual(str(context.exception), "Error retrieving pick: Database error")
        mock_log.error.assert_called_with(f"Error retrieving pick with ID {pick_id}: Database error")

        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE pick_id = ?
        """.strip()
        mock_db.fetch_one.assert_called_once()
        call_args = mock_db.fetch_one.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (pick_id,))

    # --- Tests for Pick.get_by_user_id ---

    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_id_success(self, mock_log, mock_get_user):
        """Test successful retrieval of picks for a user"""
        mock_db = AsyncMock()
        user_id = 100
        
        # Mock User existence
        mock_user = MagicMock(spec=User)
        mock_user.user_id = user_id
        mock_get_user.return_value = mock_user

        # Create test data
        test_picks = [
            {
                "pick_id": 1,
                "user_id": user_id,
                "match_id": 200,
                "pick_selection": "team1",
                "pick_timestamp": datetime.now(timezone.utc),
                "is_correct": True,
                "points_earned": 10
            },
            {
                "pick_id": 2,
                "user_id": user_id,
                "match_id": 201,
                "pick_selection": "team2",
                "pick_timestamp": datetime.now(timezone.utc),
                "is_correct": False,
                "points_earned": 0
            }
        ]
        mock_db.fetch_many.return_value = test_picks

        picks = await Pick.get_by_user_id(mock_db, user_id)

        self.assertIsNotNone(picks)
        self.assertEqual(len(picks), 2)
        for i, pick in enumerate(picks):
            self.assertIsInstance(pick, Pick)
            self.assertEqual(pick.pick_id, test_picks[i]["pick_id"])
            self.assertEqual(pick.user_id, test_picks[i]["user_id"])
            self.assertEqual(pick.match_id, test_picks[i]["match_id"])
            self.assertEqual(pick.pick_selection, test_picks[i]["pick_selection"])
            self.assertEqual(pick.pick_timestamp, test_picks[i]["pick_timestamp"])
            self.assertEqual(pick.is_correct, test_picks[i]["is_correct"])
            self.assertEqual(pick.points_earned, test_picks[i]["points_earned"])

        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (user_id,))

        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_log.debug.assert_called_once_with("Validating user_id for pick retrieval")
        mock_log.info.assert_any_call(f"Retrieving picks for user with ID: {user_id}")
        mock_log.info.assert_any_call(f"Picks for user {user_id} retrieved successfully.")

    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_id_invalid_id(self, mock_log, mock_get_user):
        """Test that retrieving picks with invalid user_id raises ValueError"""
        mock_db = AsyncMock()
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_user_id(mock_db, 0)  # Invalid user_id
        
        self.assertEqual(str(context.exception), "Invalid user_id provided.")
        mock_get_user.assert_not_called()
        mock_db.fetch_many.assert_not_called()
        mock_log.error.assert_called_with("Invalid user_id provided.")

    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_id_nonexistent_user(self, mock_log, mock_get_user):
        """Test that retrieving picks for non-existent user raises ValueError"""
        mock_db = AsyncMock()
        user_id = 999
        mock_get_user.return_value = None  # User not found
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_user_id(mock_db, user_id)
        
        self.assertEqual(str(context.exception), f"User with ID {user_id} does not exist.")
        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_db.fetch_many.assert_not_called()
        mock_log.error.assert_called_with(f"User with ID {user_id} does not exist.")

    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_id_no_picks(self, mock_log, mock_get_user):
        """Test handling of case where user exists but has no picks"""
        mock_db = AsyncMock()
        user_id = 100

        # Mock User existence
        mock_user = MagicMock(spec=User)
        mock_user.user_id = user_id
        mock_get_user.return_value = mock_user

        # Mock empty result
        mock_db.fetch_many.return_value = []

        picks = await Pick.get_by_user_id(mock_db, user_id)

        self.assertEqual(picks, [])
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (user_id,))

        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_log.warning.assert_called_once_with(f"No picks found for user with ID {user_id}")

    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_id_database_error(self, mock_log, mock_get_user):
        """Test handling of database error during picks retrieval"""
        mock_db = AsyncMock()
        user_id = 100

        # Mock User existence
        mock_user = MagicMock(spec=User)
        mock_user.user_id = user_id
        mock_get_user.return_value = mock_user

        # Mock database error
        mock_db.fetch_many.side_effect = Exception("Database error")

        with self.assertRaises(RuntimeError) as context:
            await Pick.get_by_user_id(mock_db, user_id)

        self.assertEqual(str(context.exception), "Error retrieving picks: Database error")
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (user_id,))

        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_log.error.assert_called_with(f"Error retrieving picks for user with ID {user_id}: Database error")

    # --- Tests for Pick.get_by_match_id ---

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_match_id_success(self, mock_log, mock_get_match):
        """Test successful retrieval of picks for a match"""
        mock_db = AsyncMock()
        match_id = 200
        
        # Mock Match existence
        mock_match = MagicMock(spec=Match)
        mock_match.match_id = match_id
        mock_get_match.return_value = mock_match

        # Create test data
        test_picks = [
            {
                "pick_id": 1,
                "user_id": 100,
                "match_id": match_id,
                "pick_selection": "team1",
                "pick_timestamp": datetime.now(timezone.utc),
                "is_correct": True,
                "points_earned": 10
            },
            {
                "pick_id": 2,
                "user_id": 101,
                "match_id": match_id,
                "pick_selection": "team2",
                "pick_timestamp": datetime.now(timezone.utc),
                "is_correct": False,
                "points_earned": 0
            }
        ]
        mock_db.fetch_many.return_value = test_picks

        picks = await Pick.get_by_match_id(mock_db, match_id)

        self.assertIsNotNone(picks)
        self.assertEqual(len(picks), 2)
        for i, pick in enumerate(picks):
            self.assertIsInstance(pick, Pick)
            self.assertEqual(pick.pick_id, test_picks[i]["pick_id"])
            self.assertEqual(pick.user_id, test_picks[i]["user_id"])
            self.assertEqual(pick.match_id, test_picks[i]["match_id"])
            self.assertEqual(pick.pick_selection, test_picks[i]["pick_selection"])
            self.assertEqual(pick.pick_timestamp, test_picks[i]["pick_timestamp"])
            self.assertEqual(pick.is_correct, test_picks[i]["is_correct"])
            self.assertEqual(pick.points_earned, test_picks[i]["points_earned"])

        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE match_id = ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (match_id,))

        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_log.debug.assert_called_once_with("Validating match_id for pick retrieval")
        mock_log.info.assert_any_call(f"Retrieving picks for match with ID: {match_id}")
        mock_log.info.assert_any_call(f"Picks for match {match_id} retrieved successfully.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_match_id_invalid_id(self, mock_log, mock_get_match):
        """Test that retrieving picks with invalid match_id raises ValueError"""
        mock_db = AsyncMock()
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_match_id(mock_db, 0)  # Invalid match_id
        
        self.assertEqual(str(context.exception), "Invalid match_id provided.")
        mock_get_match.assert_not_called()
        mock_db.fetch_many.assert_not_called()
        mock_log.error.assert_called_with("Invalid match_id provided.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_match_id_nonexistent_match(self, mock_log, mock_get_match):
        """Test that retrieving picks for non-existent match raises ValueError"""
        mock_db = AsyncMock()
        match_id = 999
        mock_get_match.return_value = None  # Match not found
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_match_id(mock_db, match_id)
        
        self.assertEqual(str(context.exception), f"Match with ID {match_id} does not exist.")
        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_db.fetch_many.assert_not_called()
        mock_log.error.assert_called_with(f"Match with ID {match_id} does not exist.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_match_id_no_picks(self, mock_log, mock_get_match):
        """Test handling of case where match exists but has no picks"""
        mock_db = AsyncMock()
        match_id = 200

        # Mock Match existence
        mock_match = MagicMock(spec=Match)
        mock_match.match_id = match_id
        mock_get_match.return_value = mock_match

        # Mock empty result
        mock_db.fetch_many.return_value = []

        picks = await Pick.get_by_match_id(mock_db, match_id)

        self.assertEqual(picks, [])
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE match_id = ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (match_id,))

        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_log.warning.assert_called_once_with(f"No picks found for match with ID {match_id}")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_match_id_database_error(self, mock_log, mock_get_match):
        """Test handling of database error during picks retrieval"""
        mock_db = AsyncMock()
        match_id = 200

        # Mock Match existence
        mock_match = MagicMock(spec=Match)
        mock_match.match_id = match_id
        mock_get_match.return_value = mock_match

        # Mock database error
        mock_db.fetch_many.side_effect = Exception("Database error")

        with self.assertRaises(RuntimeError) as context:
            await Pick.get_by_match_id(mock_db, match_id)

        self.assertEqual(str(context.exception), "Error retrieving picks: Database error")
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE match_id = ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (match_id,))

        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_log.error.assert_called_with(f"Error retrieving picks for match with ID {match_id}: Database error")

    # --- Tests for Pick.get_by_user_and_match ---

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_and_match_success(self, mock_log, mock_get_user, mock_get_match):
        """Test successful retrieval of a pick by user and match IDs"""
        mock_db = AsyncMock()
        user_id = 100
        match_id = 200
        
        # Mock User and Match existence
        mock_user = MagicMock(spec=User)
        mock_user.user_id = user_id
        mock_get_user.return_value = mock_user

        mock_match = MagicMock(spec=Match)
        mock_match.match_id = match_id
        mock_get_match.return_value = mock_match

        # Create test data
        test_pick = {
            "pick_id": 1,
            "user_id": user_id,
            "match_id": match_id,
            "pick_selection": "team1",
            "pick_timestamp": datetime.now(timezone.utc),
            "is_correct": True,
            "points_earned": 10
        }
        mock_db.fetch_one.return_value = test_pick

        pick = await Pick.get_by_user_and_match(mock_db, user_id, match_id)

        self.assertIsNotNone(pick)
        self.assertEqual(pick.pick_id, test_pick["pick_id"])
        self.assertEqual(pick.user_id, test_pick["user_id"])
        self.assertEqual(pick.match_id, test_pick["match_id"])
        self.assertEqual(pick.pick_selection, test_pick["pick_selection"])
        self.assertEqual(pick.pick_timestamp, test_pick["pick_timestamp"])
        self.assertEqual(pick.is_correct, test_pick["is_correct"])
        self.assertEqual(pick.points_earned, test_pick["points_earned"])

        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ? AND match_id = ?
        """.strip()
        mock_db.fetch_one.assert_called_once()
        call_args = mock_db.fetch_one.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (user_id, match_id))

        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_log.debug.assert_called_once_with("Validating user_id and match_id for pick retrieval")
        mock_log.info.assert_any_call(f"Retrieving pick for user {user_id} on match {match_id}")
        mock_log.info.assert_any_call(f"Pick for user {user_id} on match {match_id} retrieved successfully.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_and_match_invalid_user_id(self, mock_log, mock_get_user, mock_get_match):
        """Test that retrieving a pick with invalid user_id raises ValueError"""
        mock_db = AsyncMock()
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_user_and_match(mock_db, 0, 1)  # Invalid user_id
        
        self.assertEqual(str(context.exception), "Invalid user_id or match_id provided.")
        mock_get_user.assert_not_called()
        mock_get_match.assert_not_called()
        mock_db.fetch_one.assert_not_called()
        mock_log.error.assert_called_with("Invalid user_id or match_id provided.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_and_match_invalid_match_id(self, mock_log, mock_get_user, mock_get_match):
        """Test that retrieving a pick with invalid match_id raises ValueError"""
        mock_db = AsyncMock()
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_user_and_match(mock_db, 1, -1)  # Invalid match_id
        
        self.assertEqual(str(context.exception), "Invalid user_id or match_id provided.")
        mock_get_user.assert_not_called()
        mock_get_match.assert_not_called()
        mock_db.fetch_one.assert_not_called()
        mock_log.error.assert_called_with("Invalid user_id or match_id provided.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_and_match_nonexistent_user(self, mock_log, mock_get_user, mock_get_match):
        """Test that retrieving a pick for non-existent user raises ValueError"""
        mock_db = AsyncMock()
        user_id = 999
        match_id = 1
        mock_get_user.return_value = None  # User not found
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_user_and_match(mock_db, user_id, match_id)
        
        self.assertEqual(str(context.exception), f"User with ID {user_id} does not exist.")
        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_get_match.assert_not_called()
        mock_db.fetch_one.assert_not_called()
        mock_log.error.assert_called_with(f"User with ID {user_id} does not exist.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_and_match_nonexistent_match(self, mock_log, mock_get_user, mock_get_match):
        """Test that retrieving a pick for non-existent match raises ValueError"""
        mock_db = AsyncMock()
        user_id = 1
        match_id = 999

        # Mock successful user validation
        mock_user = MagicMock(spec=User)
        mock_user.user_id = user_id
        mock_get_user.return_value = mock_user
        
        mock_get_match.return_value = None  # Match not found
        
        with self.assertRaises(ValueError) as context:
            await Pick.get_by_user_and_match(mock_db, user_id, match_id)
        
        self.assertEqual(str(context.exception), f"Match with ID {match_id} does not exist.")
        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_db.fetch_one.assert_not_called()
        mock_log.error.assert_called_with(f"Match with ID {match_id} does not exist.")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_and_match_not_found(self, mock_log, mock_get_user, mock_get_match):
        """Test handling of case where user and match exist but no pick is found"""
        mock_db = AsyncMock()
        user_id = 100
        match_id = 200

        # Mock User and Match existence
        mock_user = MagicMock(spec=User)
        mock_user.user_id = user_id
        mock_get_user.return_value = mock_user

        mock_match = MagicMock(spec=Match)
        mock_match.match_id = match_id
        mock_get_match.return_value = mock_match

        # Mock no pick found
        mock_db.fetch_one.return_value = None

        pick = await Pick.get_by_user_and_match(mock_db, user_id, match_id)

        self.assertIsNone(pick)
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ? AND match_id = ?
        """.strip()
        mock_db.fetch_one.assert_called_once()
        call_args = mock_db.fetch_one.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (user_id, match_id))

        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_log.warning.assert_called_once_with(f"No pick found for user {user_id} on match {match_id}")

    @patch("src.database.models.picks.Match.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.User.get_by_id", new_callable=AsyncMock)
    @patch("src.database.models.picks.log")
    async def test_get_by_user_and_match_database_error(self, mock_log, mock_get_user, mock_get_match):
        """Test handling of database error during pick retrieval"""
        mock_db = AsyncMock()
        user_id = 100
        match_id = 200

        # Mock User and Match existence
        mock_user = MagicMock(spec=User)
        mock_user.user_id = user_id
        mock_get_user.return_value = mock_user

        mock_match = MagicMock(spec=Match)
        mock_match.match_id = match_id
        mock_get_match.return_value = mock_match

        # Mock database error
        mock_db.fetch_one.side_effect = Exception("Database error")

        with self.assertRaises(RuntimeError) as context:
            await Pick.get_by_user_and_match(mock_db, user_id, match_id)

        self.assertEqual(str(context.exception), "Error retrieving pick: Database error")
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            WHERE user_id = ? AND match_id = ?
        """.strip()
        mock_db.fetch_one.assert_called_once()
        call_args = mock_db.fetch_one.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (user_id, match_id))

        mock_get_user.assert_called_once_with(mock_db, user_id)
        mock_get_match.assert_called_once_with(mock_db, match_id)
        mock_log.error.assert_called_with(f"Error retrieving pick for user {user_id} on match {match_id}: Database error")

    # --- Tests for Pick.get_all ---

    @patch("src.database.models.picks.log")
    async def test_get_all_success(self, mock_log):
        """Test successful retrieval of picks with limit and offset"""
        mock_db = AsyncMock()
        limit = 2
        offset = 1

        # Create test data
        test_picks = [
            {
                "pick_id": 2,
                "user_id": 100,
                "match_id": 200,
                "pick_selection": "team1",
                "pick_timestamp": datetime.now(timezone.utc),
                "is_correct": True,
                "points_earned": 10
            },
            {
                "pick_id": 3,
                "user_id": 101,
                "match_id": 201,
                "pick_selection": "team2",
                "pick_timestamp": datetime.now(timezone.utc),
                "is_correct": False,
                "points_earned": 0
            }
        ]
        mock_db.fetch_many.return_value = test_picks

        picks = await Pick.get_all(mock_db, limit=limit, offset=offset)

        self.assertIsNotNone(picks)
        self.assertEqual(len(picks), 2)
        for i, pick in enumerate(picks):
            self.assertIsInstance(pick, Pick)
            self.assertEqual(pick.pick_id, test_picks[i]["pick_id"])
            self.assertEqual(pick.user_id, test_picks[i]["user_id"])
            self.assertEqual(pick.match_id, test_picks[i]["match_id"])
            self.assertEqual(pick.pick_selection, test_picks[i]["pick_selection"])
            self.assertEqual(pick.pick_timestamp, test_picks[i]["pick_timestamp"])
            self.assertEqual(pick.is_correct, test_picks[i]["is_correct"])
            self.assertEqual(pick.points_earned, test_picks[i]["points_earned"])

        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (limit, offset))

        mock_log.info.assert_any_call(f"Retrieving all picks with limit {limit} and offset {offset}")
        mock_log.info.assert_any_call("All picks retrieved successfully.")

    @patch("src.database.models.picks.log")
    async def test_get_all_default_params(self, mock_log):
        """Test get_all with default limit and offset parameters"""
        mock_db = AsyncMock()
        default_limit = 100
        default_offset = 0

        test_picks = [
            {
                "pick_id": 1,
                "user_id": 100,
                "match_id": 200,
                "pick_selection": "team1",
                "pick_timestamp": datetime.now(timezone.utc),
                "is_correct": True,
                "points_earned": 10
            }
        ]
        mock_db.fetch_many.return_value = test_picks

        picks = await Pick.get_all(mock_db)  # Use default parameters

        self.assertEqual(len(picks), 1)
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (default_limit, default_offset))

        mock_log.info.assert_any_call(f"Retrieving all picks with limit {default_limit} and offset {default_offset}")
        mock_log.info.assert_any_call("All picks retrieved successfully.")

    @patch("src.database.models.picks.log")
    async def test_get_all_empty_result(self, mock_log):
        """Test handling of empty result"""
        mock_db = AsyncMock()
        mock_db.fetch_many.return_value = []  # No picks found

        picks = await Pick.get_all(mock_db)

        self.assertEqual(picks, [])
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (100, 0))  # Default values

        mock_log.warning.assert_called_once_with("No picks found in the database")

    @patch("src.database.models.picks.log")
    async def test_get_all_database_error(self, mock_log):
        """Test handling of database error during picks retrieval"""
        mock_db = AsyncMock()
        mock_db.fetch_many.side_effect = Exception("Database error")

        with self.assertRaises(RuntimeError) as context:
            await Pick.get_all(mock_db)

        self.assertEqual(str(context.exception), "Error retrieving all picks: Database error")
        expected_query = """
            SELECT pick_id, user_id, match_id, pick_selection, pick_timestamp, is_correct, points_earned
            FROM Picks
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once()
        call_args = mock_db.fetch_many.call_args[0]
        self.assertEqual(call_args[0], expected_query)
        self.assertEqual(call_args[1], (100, 0))  # Default values

        mock_log.error.assert_called_with("Error retrieving all picks: Database error")

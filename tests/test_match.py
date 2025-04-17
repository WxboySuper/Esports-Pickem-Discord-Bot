import unittest
import json
from unittest.mock import patch, AsyncMock
from src.database.models.match import Match

class TestMatch(unittest.IsolatedAsyncioTestCase):

    # --- Tests for Match.create ---

    @patch("src.database.models.match.log")
    async def test_create_match_success(self, mock_log):
        mock_db = AsyncMock()
        mock_db.execute.return_value = 1 # Simulate successful insertion with match ID 1
        metadata = {"key": "value"}

        match = await Match.create(
            db=mock_db,
            team1_id=10, team1_name="Team A",
            team2_id=20, team2_name="Team B",
            region="NA", tournament="Summer Split",
            match_date="2025-07-01", match_time="18:00:00",
            match_metadata=metadata
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.match_id, 1)
        self.assertEqual(match.team1_id, 10)
        self.assertEqual(match.team1_name, "Team A")
        self.assertEqual(match.team2_id, 20)
        self.assertEqual(match.team2_name, "Team B")
        self.assertEqual(match.region, "NA")
        self.assertEqual(match.tournament, "Summer Split")
        self.assertEqual(match.match_date, "2025-07-01")
        self.assertEqual(match.match_time, "18:00:00")
        self.assertEqual(match.match_metadata, metadata)
        self.assertFalse(match.is_complete)
        expected_query = """
            INSERT INTO matches (team1_id, team1_name, team2_id, team2_name, region, tournament, match_date, match_time, match_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """.strip()  # Strip leading/trailing whitespace
        expected_params = (10, "Team A", 20, "Team B", "NA", "Summer Split", "2025-07-01", "18:00:00", json.dumps(metadata))
        mock_db.execute.assert_called_once_with(expected_query, expected_params)  # Remove redundant strip() call
        mock_log.info.assert_called()

    @patch("src.database.models.match.log")
    async def test_create_match_failure(self, mock_log):
        mock_db = AsyncMock()
        mock_db.execute.return_value = None # Simulate failed insertion

        match = await Match.create(
            db=mock_db,
            team1_id=10, team1_name="Team A",
            team2_id=20, team2_name="Team B",
            region="NA", tournament="Summer Split",
            match_date="2025-07-01", match_time="18:00:00"
        )

        self.assertIsNone(match)
        mock_db.execute.assert_called_once()
        mock_log.error.assert_called_with("Failed to create match.")

    @patch("src.database.models.match.log")
    async def test_create_match_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB error")

        match = await Match.create(
            db=mock_db,
            team1_id=10, team1_name="Team A",
            team2_id=20, team2_name="Team B",
            region="NA", tournament="Summer Split",
            match_date="2025-07-01", match_time="18:00:00"
        )

        self.assertIsNone(match)
        mock_db.execute.assert_called_once()
        mock_log.error.assert_called_with("Error creating match: DB error")

    # --- Tests for Match.get_by_id ---

    @patch("src.database.models.match.log")
    async def test_get_by_id_success(self, mock_log):
        mock_db = AsyncMock()
        metadata = {"info": "extra"}
        mock_db.fetch_one.return_value = {
            "match_id": 5,
            "team1_id": 10, "team1_name": "Team A",
            "team2_id": 20, "team2_name": "Team B",
            "region": "NA", "tournament": "Summer Split",
            "match_date": "2025-07-01", "match_time": "18:00:00",
            "result": "team1", "is_complete": True,
            "match_metadata": json.dumps(metadata)
        }

        match = await Match.get_by_id(mock_db, 5)

        self.assertIsNotNone(match)
        self.assertEqual(match.match_id, 5)
        self.assertEqual(match.team1_name, "Team A")
        self.assertEqual(match.result, "team1")
        self.assertTrue(match.is_complete)
        self.assertEqual(match.match_metadata, metadata)
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM matches WHERE match_id = ?", (5,))
        mock_log.info.assert_called_with("Retrieving match with ID 5")

    @patch("src.database.models.match.log")
    async def test_get_by_id_not_found(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = None

        match = await Match.get_by_id(mock_db, 99)

        self.assertIsNone(match)
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM matches WHERE match_id = ?", (99,))
        mock_log.warning.assert_called_with("No match found with ID 99")

    @patch("src.database.models.match.log")
    async def test_get_by_id_invalid_input(self, mock_log):
        mock_db = AsyncMock()
        match = await Match.get_by_id(mock_db, -1)
        self.assertIsNone(match)
        mock_log.error.assert_called_with("Invalid match_id provided.")
        mock_db.fetch_one.assert_not_called()

    @patch("src.database.models.match.log")
    async def test_get_by_id_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.side_effect = Exception("Fetch error")

        match = await Match.get_by_id(mock_db, 5)

        self.assertIsNone(match)
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM matches WHERE match_id = ?", (5,))
        mock_log.error.assert_called_with("Error retrieving match with ID 5: Fetch error")

    @patch("src.database.models.match.log")
    async def test_get_by_id_json_decode_error(self, mock_log):
        """Test handling of JSONDecodeError when fetching a match by ID."""
        mock_db = AsyncMock()
        invalid_metadata_json = '{"key": "value", invalid json}'
        mock_db.fetch_one.return_value = {
            "match_id": 6,
            "team1_id": 11, "team1_name": "Team C",
            "team2_id": 21, "team2_name": "Team D",
            "region": "EU", "tournament": "Spring Split",
            "match_date": "2025-04-01", "match_time": "17:00:00",
            "result": None, "is_complete": False,
            "match_metadata": invalid_metadata_json
        }

        match = await Match.get_by_id(mock_db, 6)

        self.assertIsNotNone(match)
        self.assertEqual(match.match_id, 6)
        self.assertIsNone(match.match_metadata) # Metadata should be None after decode error
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM matches WHERE match_id = ?", (6,))
        mock_log.warning.assert_called_once_with("Failed to decode metadata for match 6")

    # --- Tests for Match.get_upcoming ---

    @patch("src.database.models.match.log")
    async def test_get_upcoming_success(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_many.return_value = [
            {
                "match_id": 1, "team1_name": "Team C", "team2_name": "Team D",
                "match_date": "2025-07-02", "match_time": "15:00:00", "is_complete": False, "result": None,
                 "team1_id": 30, "team2_id": 40, "region": "EU", "tournament": "Playoffs", "match_metadata": None
            },
            {
                "match_id": 2, "team1_name": "Team E", "team2_name": "Team F",
                "match_date": "2025-07-02", "match_time": "18:00:00", "is_complete": False, "result": None,
                 "team1_id": 50, "team2_id": 60, "region": "EU", "tournament": "Playoffs", "match_metadata": json.dumps({"stream": "twitch"})
            }
        ]

        matches = await Match.get_upcoming(mock_db, limit=10, offset=0)

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].match_id, 1)
        self.assertEqual(matches[0].team1_name, "Team C")
        expected_query = """
            SELECT * FROM matches
            WHERE is_complete = 0
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()  # Strip leading/trailing whitespace
        mock_db.fetch_many.assert_called_once_with(expected_query, (10, 0))  # Remove redundant strip() call
        mock_log.info.assert_called_with("Retrieving upcoming matches with limit 10 and offset 0")

    @patch("src.database.models.match.log")
    async def test_get_upcoming_empty(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_many.return_value = []

        matches = await Match.get_upcoming(mock_db)

        self.assertEqual(len(matches), 0)
        mock_db.fetch_many.assert_called_once()
        mock_log.info.assert_called_with("No upcoming matches found.")

    @patch("src.database.models.match.log")
    async def test_get_upcoming_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_many.side_effect = Exception("Fetch many error")

        matches = await Match.get_upcoming(mock_db)

        self.assertEqual(len(matches), 0)
        mock_db.fetch_many.assert_called_once()
        mock_log.error.assert_called_with("Error retrieving upcoming matches: Fetch many error")

    @patch("src.database.models.match.log")
    async def test_get_upcoming_json_decode_error(self, mock_log):
        """Test handling of JSONDecodeError when fetching upcoming matches."""
        mock_db = AsyncMock()
        valid_metadata = {"stream": "youtube"}
        invalid_metadata_json = '{"info": bad json}'
        mock_db.fetch_many.return_value = [
            {
                "match_id": 7, "team1_name": "Team G", "team2_name": "Team H",
                "match_date": "2025-08-01", "match_time": "16:00:00", "is_complete": False, "result": None,
                 "team1_id": 70, "team2_id": 80, "region": "KR", "tournament": "LCK Finals", "match_metadata": json.dumps(valid_metadata)
            },
            {
                "match_id": 8, "team1_name": "Team I", "team2_name": "Team J",
                "match_date": "2025-08-02", "match_time": "19:00:00", "is_complete": False, "result": None,
                 "team1_id": 90, "team2_id": 100, "region": "KR", "tournament": "LCK Finals", "match_metadata": invalid_metadata_json
            }
        ]

        matches = await Match.get_upcoming(mock_db, limit=5)

        self.assertEqual(len(matches), 2)
        # Check the first match (valid metadata)
        self.assertEqual(matches[0].match_id, 7)
        self.assertEqual(matches[0].match_metadata, valid_metadata)
        # Check the second match (invalid metadata)
        self.assertEqual(matches[1].match_id, 8)
        self.assertIsNone(matches[1].match_metadata) # Metadata should be None

        expected_query = """
            SELECT * FROM matches
            WHERE is_complete = 0
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once_with(expected_query, (5, 0))
        mock_log.warning.assert_called_once_with("Failed to decode metadata for match 8")
        # Ensure info log for retrieval was also called
        mock_log.info.assert_any_call("Retrieving upcoming matches with limit 5 and offset 0")

    # --- Tests for Match.update_result ---

    @patch("src.database.models.match.log")
    async def test_update_result_success(self, mock_log):
        expected_query = "UPDATE matches SET result = ?, is_complete = ? WHERE match_id = ?"
        mock_db = AsyncMock()
        # Assume execute returns non-None on success for this test case
        mock_db.execute.return_value = 1 # Or some non-None value indicating success

        success = await Match.update_result(mock_db, match_id=15, result="team2", is_complete=True)

        self.assertTrue(success)
        expected_query = "UPDATE matches SET result = ?, is_complete = ? WHERE match_id = ?"
        mock_db.execute.assert_called_once_with(expected_query, ("team2", True, 15))
        mock_log.info.assert_called_with("Match 15 result updated successfully.")

    @patch("src.database.models.match.log")
    async def test_update_result_not_found_or_fail(self, mock_log):
        mock_db = AsyncMock()
        # Simulate execute failing or finding no rows (returning None)
        mock_db.execute.return_value = None

        success = await Match.update_result(mock_db, match_id=16, result="draw")

        self.assertFalse(success)
        expected_query = "UPDATE matches SET result = ?, is_complete = ? WHERE match_id = ?"
        mock_db.execute.assert_called_once_with(expected_query, ("draw", True, 16))
        mock_log.warning.assert_called_with("No rows affected. Match 16 may not exist or update failed.")

    @patch("src.database.models.match.log")
    async def test_update_result_invalid_id(self, mock_log):
        mock_db = AsyncMock()
        success = await Match.update_result(mock_db, match_id=-5, result="team1")
        self.assertFalse(success)
        mock_log.error.assert_called_with("Invalid match_id provided for update.")
        mock_db.execute.assert_not_called()

    @patch("src.database.models.match.log")
    async def test_update_result_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Update error")

        success = await Match.update_result(mock_db, match_id=17, result="team1")

        self.assertFalse(success)
        expected_query = "UPDATE matches SET result = ?, is_complete = ? WHERE match_id = ?"
        mock_db.execute.assert_called_once_with(expected_query, ("team1", True, 17))
        mock_log.error.assert_called_with("Error updating result for match 17: Update error")

    # --- Tests for Match.delete_match ---

    @patch("src.database.models.match.log")
    async def test_delete_match_success(self, mock_log):
        """Test successful deletion of a match."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = 1 # Simulate 1 row affected

        result = await Match.delete_match(mock_db, 10)

        self.assertTrue(result)
        mock_db.execute.assert_called_once_with("DELETE FROM matches WHERE match_id = ?", (10,))
        # Assert that info was called exactly twice
        self.assertEqual(mock_log.info.call_count, 2)
        # Assert that the specific messages were logged at least once
        mock_log.info.assert_any_call("Deleting match with ID 10")
        mock_log.info.assert_any_call("Match 10 deleted successfully.")

    @patch("src.database.models.match.log")
    async def test_delete_match_not_found(self, mock_log):
        """Test deleting a match that does not exist."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = 0 # Simulate 0 rows affected

        result = await Match.delete_match(mock_db, 99)

        self.assertFalse(result)
        mock_db.execute.assert_called_once_with("DELETE FROM matches WHERE match_id = ?", (99,))
        mock_log.info.assert_called_once_with("Deleting match with ID 99")
        mock_log.warning.assert_called_once_with("No rows affected. Match 99 may not exist or deletion failed.")

    @patch("src.database.models.match.log")
    async def test_delete_match_invalid_id(self, mock_log):
        """Test deleting a match with an invalid ID."""
        mock_db = AsyncMock()

        result = await Match.delete_match(mock_db, 0)

        self.assertFalse(result)
        mock_db.execute.assert_not_called()
        mock_log.error.assert_called_once_with("Invalid match_id provided for deletion.")

    @patch("src.database.models.match.log")
    async def test_delete_match_exception(self, mock_log):
        """Test exception during match deletion."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB Delete Error")

        result = await Match.delete_match(mock_db, 11)

        self.assertFalse(result)
        mock_db.execute.assert_called_once_with("DELETE FROM matches WHERE match_id = ?", (11,))
        mock_log.info.assert_called_once_with("Deleting match with ID 11")
        mock_log.error.assert_called_once_with("Error deleting match 11: DB Delete Error")

    # --- Tests for Match.get_by_day ---

    @patch("src.database.models.match.log")
    async def test_get_by_day_success(self, mock_log):
        """Test retrieving matches for a specific day."""
        mock_db = AsyncMock()
        test_date = "2025-05-10"
        mock_rows = [
            {
                "match_id": 12, "team1_name": "Team K", "team2_name": "Team L",
                "match_date": test_date, "match_time": "14:00:00", "is_complete": False, "result": None,
                "team1_id": 110, "team2_id": 120, "region": "NA", "tournament": "Summer Playoffs", "match_metadata": None
            },
            {
                "match_id": 13, "team1_name": "Team M", "team2_name": "Team N",
                "match_date": test_date, "match_time": "17:00:00", "is_complete": False, "result": None,
                "team1_id": 130, "team2_id": 140, "region": "NA", "tournament": "Summer Playoffs", "match_metadata": json.dumps({"stream": "twitch"})
            }
        ]
        mock_db.fetch_many.return_value = mock_rows

        matches = await Match.get_by_day(mock_db, test_date)

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].match_id, 12)
        self.assertEqual(matches[0].match_date, test_date)
        self.assertIsNone(matches[0].match_metadata)
        self.assertEqual(matches[1].match_id, 13)
        self.assertEqual(matches[1].match_date, test_date)
        self.assertEqual(matches[1].match_metadata, {"stream": "twitch"})

        expected_query = "SELECT * FROM matches WHERE match_date = ? ORDER BY match_time"
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_date,))
        mock_log.info.assert_called_once_with(f"Retrieving matches for date {test_date}")

    @patch("src.database.models.match.log")
    async def test_get_by_day_no_matches(self, mock_log):
        """Test retrieving matches for a day with no scheduled matches."""
        mock_db = AsyncMock()
        test_date = "2025-05-11"
        mock_db.fetch_many.return_value = []

        matches = await Match.get_by_day(mock_db, test_date)

        self.assertEqual(len(matches), 0)
        expected_query = "SELECT * FROM matches WHERE match_date = ? ORDER BY match_time"
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_date,))
        mock_log.info.assert_any_call(f"Retrieving matches for date {test_date}")
        mock_log.info.assert_any_call(f"No matches found for date {test_date}.")

    @patch("src.database.models.match.log")
    async def test_get_by_day_json_decode_error(self, mock_log):
        """Test handling JSONDecodeError when retrieving matches by day."""
        mock_db = AsyncMock()
        test_date = "2025-05-12"
        mock_rows = [
            {
                "match_id": 14, "team1_name": "Team O", "team2_name": "Team P",
                "match_date": test_date, "match_time": "15:00:00", "is_complete": False, "result": None,
                "team1_id": 150, "team2_id": 160, "region": "EU", "tournament": "LEC Finals", "match_metadata": '{"invalid json'
            }
        ]
        mock_db.fetch_many.return_value = mock_rows

        matches = await Match.get_by_day(mock_db, test_date)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_id, 14)
        self.assertIsNone(matches[0].match_metadata) # Should be None after decode error
        mock_log.warning.assert_called_once_with("Failed to decode metadata for match 14")
        expected_query = "SELECT * FROM matches WHERE match_date = ? ORDER BY match_time"
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_date,))
        mock_log.info.assert_called_once_with(f"Retrieving matches for date {test_date}")

    @patch("src.database.models.match.log")
    async def test_get_by_day_exception(self, mock_log):
        """Test database exception when retrieving matches by day."""
        mock_db = AsyncMock()
        test_date = "2025-05-13"
        mock_db.fetch_many.side_effect = Exception("DB Fetch Error")

        matches = await Match.get_by_day(mock_db, test_date)

        self.assertEqual(len(matches), 0)
        expected_query = "SELECT * FROM matches WHERE match_date = ? ORDER BY match_time"
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_date,))
        mock_log.info.assert_called_once_with(f"Retrieving matches for date {test_date}")
        mock_log.error.assert_called_once_with(f"Error retrieving matches for date {test_date}: DB Fetch Error")

    # --- Tests for Match.get_by_tournament ---

    @patch("src.database.models.match.log")
    async def test_get_by_tournament_success(self, mock_log):
        """Test retrieving matches for a specific tournament."""
        mock_db = AsyncMock()
        test_tournament = "World Championship"
        mock_rows = [
            {
                "match_id": 15, "team1_name": "Team Q", "team2_name": "Team R", "match_date": "2025-10-01",
                "match_time": "10:00:00", "is_complete": False, "result": None, "team1_id": 170, "team2_id": 180,
                "region": "INT", "tournament": test_tournament, "match_metadata": None
            },
            {
                "match_id": 16, "team1_name": "Team S", "team2_name": "Team T", "match_date": "2025-10-01",
                "match_time": "13:00:00", "is_complete": False, "result": None, "team1_id": 190, "team2_id": 200,
                "region": "INT", "tournament": test_tournament, "match_metadata": json.dumps({"venue": "Arena"})
            }
        ]
        mock_db.fetch_many.return_value = mock_rows

        matches = await Match.get_by_tournament(mock_db, test_tournament, limit=5, offset=0)

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].match_id, 15)
        self.assertEqual(matches[0].tournament, test_tournament)
        self.assertIsNone(matches[0].match_metadata)
        self.assertEqual(matches[1].match_id, 16)
        self.assertEqual(matches[1].tournament, test_tournament)
        self.assertEqual(matches[1].match_metadata, {"venue": "Arena"})

        expected_query = """
            SELECT * FROM matches
            WHERE tournament = ?
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_tournament, 5, 0))
        mock_log.info.assert_called_once_with(f"Retrieving matches for tournament '{test_tournament}' with limit 5 and offset 0")

    @patch("src.database.models.match.log")
    async def test_get_by_tournament_no_matches(self, mock_log):
        """Test retrieving matches for a tournament with no matches."""
        mock_db = AsyncMock()
        test_tournament = "NonExistent Cup"
        mock_db.fetch_many.return_value = []

        matches = await Match.get_by_tournament(mock_db, test_tournament)

        self.assertEqual(len(matches), 0)
        expected_query = """
            SELECT * FROM matches
            WHERE tournament = ?
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()
        # Default limit=100, offset=0
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_tournament, 100, 0))
        mock_log.info.assert_any_call(f"Retrieving matches for tournament '{test_tournament}' with limit 100 and offset 0")
        mock_log.info.assert_any_call(f"No matches found for tournament '{test_tournament}'.")

    @patch("src.database.models.match.log")
    async def test_get_by_tournament_empty_name(self, mock_log):
        """Test retrieving matches with an empty tournament name."""
        mock_db = AsyncMock()

        matches = await Match.get_by_tournament(mock_db, "")

        self.assertEqual(len(matches), 0)
        mock_db.fetch_many.assert_not_called()
        mock_log.error.assert_called_once_with("Tournament name cannot be empty.")

    @patch("src.database.models.match.log")
    async def test_get_by_tournament_json_decode_error(self, mock_log):
        """Test handling JSONDecodeError when retrieving matches by tournament."""
        mock_db = AsyncMock()
        test_tournament = "Regional Finals"
        mock_rows = [
            {
                "match_id": 17, "team1_name": "Team U", "team2_name": "Team V", "match_date": "2025-09-15",
                "match_time": "18:00:00", "is_complete": False, "result": None, "team1_id": 210, "team2_id": 220,
                "region": "LPL", "tournament": test_tournament, "match_metadata": '{"bad json"}'
            }
        ]
        mock_db.fetch_many.return_value = mock_rows

        matches = await Match.get_by_tournament(mock_db, test_tournament)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_id, 17)
        self.assertIsNone(matches[0].match_metadata)
        mock_log.warning.assert_called_once_with("Failed to decode metadata for match 17")
        expected_query = """
            SELECT * FROM matches
            WHERE tournament = ?
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_tournament, 100, 0))
        mock_log.info.assert_called_once_with(f"Retrieving matches for tournament '{test_tournament}' with limit 100 and offset 0")

    @patch("src.database.models.match.log")
    async def test_get_by_tournament_exception(self, mock_log):
        """Test database exception when retrieving matches by tournament."""
        mock_db = AsyncMock()
        test_tournament = "MSI"
        mock_db.fetch_many.side_effect = Exception("DB Query Error")

        matches = await Match.get_by_tournament(mock_db, test_tournament)

        self.assertEqual(len(matches), 0)
        expected_query = """
            SELECT * FROM matches
            WHERE tournament = ?
            ORDER BY match_date, match_time
            LIMIT ? OFFSET ?
        """.strip()
        mock_db.fetch_many.assert_called_once_with(expected_query, (test_tournament, 100, 0))
        mock_log.info.assert_called_once_with(f"Retrieving matches for tournament '{test_tournament}' with limit 100 and offset 0")
        mock_log.error.assert_called_once_with(f"Error retrieving matches for tournament '{test_tournament}': DB Query Error")


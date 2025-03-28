import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from src.database.models.user import User

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = MagicMock()

    def tearDown(self):
        self.db.reset_mock()
    
    @patch("src.database.models.user.log")
    async def test_create_user_success(self, mock_log):
        mock_db = AsyncMock()
        mock_db.execute.return_value = 1  # Simulate successful insertion with user ID 1

        user = await User.create(mock_db, 12345, 67890, "test_user")

        self.assertIsNotNone(user)
        self.assertEqual(user.db_id, 1)
        self.assertEqual(user.discord_user_id, 12345)
        self.assertEqual(user.discord_guild_id, 67890)
        self.assertEqual(user.username, "test_user")
        mock_db.execute.assert_called_once_with(
            """
            INSERT INTO users (discord_user_id, discord_guild_id, username)
            VALUES (?, ?, ?)
        """,
            (12345, 67890, "test_user")
        )
        mock_log.info.assert_called()

    @patch("src.database.models.user.log")
    async def test_create_user_failure(self, mock_log):
        mock_db = AsyncMock()
        mock_db.execute.return_value = None  # Simulate failed insertion

        user = await User.create(mock_db, 12345, 67890, "test_user")

        self.assertIsNone(user)
        mock_db.execute.assert_called_once_with(
            """
            INSERT INTO users (discord_user_id, discord_guild_id, username)
            VALUES (?, ?, ?)
        """,
            (12345, 67890, "test_user")
        )
        mock_log.error.assert_called()

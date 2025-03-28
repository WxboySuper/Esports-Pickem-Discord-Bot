import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from src.database.models.user import User

class TestUser(unittest.IsolatedAsyncioTestCase):
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

    @patch("src.database.models.user.log")
    async def test_get_by_id_success(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = {
            "db_id": 1,
            "discord_user_id": 12345,
            "discord_guild_id": 67890,
            "username": "test_user",
            "created_at": "2023-01-01T00:00:00",
            "last_active": "2023-01-02T00:00:00"
        }

        user = await User.get_by_id(mock_db, 1)

        self.assertIsNotNone(user)
        self.assertEqual(user.db_id, 1)
        self.assertEqual(user.discord_user_id, 12345)
        self.assertEqual(user.discord_guild_id, 67890)
        self.assertEqual(user.username, "test_user")
        self.assertEqual(user.created_at, "2023-01-01T00:00:00")
        self.assertEqual(user.last_active, "2023-01-02T00:00:00")
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM users WHERE id = ?", (1,))
        mock_log.info.assert_not_called()

    @patch("src.database.models.user.log")
    async def test_get_by_id_not_found(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = None

        user = await User.get_by_id(mock_db, 1)

        self.assertIsNone(user)
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM users WHERE id = ?", (1,))
        mock_log.info.assert_not_called()

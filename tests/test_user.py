import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from src.database.models.user import User

class TestUser(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = MagicMock()

    def tearDown(self):
        self.db.reset_mock()

    # --- Tests for User.create ---

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
    async def test_create_user_invalid_input(self, mock_log):
        mock_db = AsyncMock()

        user = await User.create(mock_db, -1, 67890, "test_user")
        self.assertIsNone(user)
        mock_log.error.assert_called_with("Invalid discord_user_id or discord_guild_id provided.")

    @patch("src.database.models.user.log")
    async def test_create_user_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Database error")

        user = await User.create(mock_db, 12345, 67890, "test_user")

        self.assertIsNone(user)
        mock_log.error.assert_called_with("Error creating user test_user: Database error")

    # --- Tests for User.get_by_id ---
    @patch("src.database.models.user.log")
    async def test_get_by_id_success(self, mock_log):
        mock_db = AsyncMock()
        # Correct the key from 'db_id' to 'id' to match the implementation
        mock_db.fetch_one.return_value = {
            "id": 1, # Changed key from "db_id" to "id"
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
        mock_log.info.assert_called_with("Retrieving user with ID 1")

    @patch("src.database.models.user.log")
    async def test_get_by_id_not_found(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = None

        user = await User.get_by_id(mock_db, 1)

        self.assertIsNone(user)
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM users WHERE id = ?", (1,))
        mock_log.info.assert_called_with("Retrieving user with ID 1")

    @patch("src.database.models.user.log")
    async def test_get_by_id_invalid_input(self, mock_log):
        mock_db = AsyncMock()

        user = await User.get_by_id(mock_db, -1)
        self.assertIsNone(user)
        mock_log.error.assert_called_with("Invalid user_id provided.")

    @patch("src.database.models.user.log")
    async def test_get_by_id_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.side_effect = Exception("Database error")

        user = await User.get_by_id(mock_db, 1)

        self.assertIsNone(user)
        mock_log.error.assert_called_with("Error retrieving user with ID 1: Database error")

    # --- Tests for User.get_by_discord_user_id ---

    @patch("src.database.models.user.log")
    async def test_get_by_discord_user_id_success(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = {
            "id": 1, # Changed key from "db_id" to "id"
            "discord_user_id": 12345,
            "discord_guild_id": 67890,
            "username": "test_user",
            "created_at": "2023-01-01T00:00:00",
            "last_active": "2023-01-02T00:00:00"
        }

        user = await User.get_by_discord_user_id(mock_db, 12345)

        self.assertIsNotNone(user)
        self.assertEqual(user.db_id, 1)
        self.assertEqual(user.discord_user_id, 12345)
        self.assertEqual(user.discord_guild_id, 67890)
        self.assertEqual(user.username, "test_user")
        self.assertEqual(user.created_at, "2023-01-01T00:00:00")
        self.assertEqual(user.last_active, "2023-01-02T00:00:00")
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM users WHERE discord_user_id = ?", (12345,))
        mock_log.info.assert_called_with("Retrieving user with Discord user ID 12345")

    @patch("src.database.models.user.log")
    async def test_get_by_discord_user_id_not_found(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.return_value = None

        user = await User.get_by_discord_user_id(mock_db, 12345)

        self.assertIsNone(user)
        mock_db.fetch_one.assert_called_once_with("SELECT * FROM users WHERE discord_user_id = ?", (12345,))
        mock_log.info.assert_called_with("Retrieving user with Discord user ID 12345")

    @patch("src.database.models.user.log")
    async def test_get_by_discord_user_id_invalid_input(self, mock_log):
        mock_db = AsyncMock()

        user = await User.get_by_discord_user_id(mock_db, -1)
        self.assertIsNone(user)
        mock_log.error.assert_called_with("Invalid discord_user_id provided.")

    @patch("src.database.models.user.log")
    async def test_get_by_discord_user_id_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_one.side_effect = Exception("Database error")

        user = await User.get_by_discord_user_id(mock_db, 12345)

        self.assertIsNone(user)
        mock_log.error.assert_called_with("Error retrieving user with Discord user ID 12345: Database error")

    # --- Tests for User.get_all ---

    @patch("src.database.models.user.log")
    async def test_get_all_users_success(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_many.return_value = [
            {
                "id": 1, # Changed key from "db_id" to "id"
                "discord_user_id": 12345,
                "discord_guild_id": 67890,
                "username": "test_user1",
                "created_at": "2023-01-01T00:00:00",
                "last_active": "2023-01-02T00:00:00"
            },
            {
                "id": 2, # Changed key from "db_id" to "id"
                "discord_user_id": 54321,
                "discord_guild_id": 98765,
                "username": "test_user2",
                "created_at": "2023-01-03T00:00:00",
                "last_active": "2023-01-04T00:00:00"
            }
        ]

        users = await User.get_all(mock_db)

        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].db_id, 1) # Assertion remains the same, checks the User object attribute
        self.assertEqual(users[0].discord_user_id, 12345)
        self.assertEqual(users[0].discord_guild_id, 67890)
        self.assertEqual(users[0].username, "test_user1")
        self.assertEqual(users[0].created_at, "2023-01-01T00:00:00")
        self.assertEqual(users[0].last_active, "2023-01-02T00:00:00")
        self.assertEqual(users[1].db_id, 2) # Assertion remains the same, checks the User object attribute
        self.assertEqual(users[1].discord_user_id, 54321)
        self.assertEqual(users[1].discord_guild_id, 98765)
        self.assertEqual(users[1].username, "test_user2")
        self.assertEqual(users[1].created_at, "2023-01-03T00:00:00")
        self.assertEqual(users[1].last_active, "2023-01-04T00:00:00")
        mock_db.fetch_many.assert_called_once_with('SELECT * FROM users LIMIT ? OFFSET ?', (100, 0))
        mock_log.info.assert_called_with('Retrieving all users from the database with limit 100 and offset 0')

    @patch("src.database.models.user.log")
    async def test_get_all_users_empty(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_many.return_value = []

        users = await User.get_all(mock_db)

        self.assertEqual(len(users), 0)
        mock_db.fetch_many.assert_called_once_with('SELECT * FROM users LIMIT ? OFFSET ?', (100, 0))
        mock_log.info.assert_called_with('Retrieving all users from the database with limit 100 and offset 0')
        mock_log.warning.assert_called_with('No users found in the database')

    @patch("src.database.models.user.log")
    async def test_get_all_users_pagination(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_many.return_value = [
            {
                "id": 1, # Changed key from "db_id" to "id"
                "discord_user_id": 12345,
                "discord_guild_id": 67890,
                "username": "test_user1",
                "created_at": "2023-01-01T00:00:00",
                "last_active": "2023-01-02T00:00:00"
            },
            {
                "id": 2, # Changed key from "db_id" to "id"
                "discord_user_id": 54321,
                "discord_guild_id": 98765,
                "username": "test_user2",
                "created_at": "2023-01-03T00:00:00",
                "last_active": "2023-01-04T00:00:00"
            }
        ]

        users = await User.get_all(mock_db, limit=2, offset=0)

        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].db_id, 1) # Assertion remains the same, checks the User object attribute
        self.assertEqual(users[1].db_id, 2) # Assertion remains the same, checks the User object attribute
        mock_db.fetch_many.assert_called_once_with("SELECT * FROM users LIMIT ? OFFSET ?", (2, 0))
        mock_log.info.assert_called_with("Retrieving all users from the database with limit 2 and offset 0")

    @patch("src.database.models.user.log")
    async def test_get_all_users_exception(self, mock_log):
        mock_db = AsyncMock()
        mock_db.fetch_many.side_effect = Exception("Database error")

        users = await User.get_all(mock_db, limit=2, offset=0)

        self.assertEqual(users, [])
        mock_log.error.assert_called_with("Error retrieving all users from the database: Database error")

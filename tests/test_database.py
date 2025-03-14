import unittest
from unittest.mock import patch, AsyncMock
from src.database.database import Database
import os
import aiosqlite

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = Database(db_path = "data/test.db")
        
    def tearDown(self):
        os.remove("data/test.db")

    async def test_initialize(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        # Set up mock methods
        mock_db.execute = AsyncMock()
        mock_db.executescript = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("aiosqlite.connect") as mock_connect:
            # Configure the mock to return our mock_db when used as a context manager
            mock_connect.return_value.__aenter__.return_value = mock_db

            await self.db.initialize()

            mock_db.execute.assert_called_once_with("PRAGMA foreign_keys = ON")
            mock_db.executescript.assert_called_once()
            mock_db.commit.assert_called_once()

    async def test_initialize_no_schema(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        # Set up mock methods
        mock_db.execute = AsyncMock()
        mock_db.executescript = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("aiosqlite.connect") as mock_connect:
            # Configure the mock to return our mock_db when used as a context manager
            mock_connect.return_value.__aenter__.return_value = mock_db

            # Set the schema path to a non-existent file
            self.db.schema_path = "data/schema.sql"

            await self.db.initialize()

            mock_db.execute.assert_called_once_with("PRAGMA foreign_keys = ON")
            mock_db.executescript.assert_not_called()
            mock_db.commit.assert_not_called()

    async def test_initialize_exception(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        # Set up mock methods
        mock_db.execute = AsyncMock(side_effect=Exception("Test exception"))
        mock_db.executescript = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("aiosqlite.connect") as mock_connect:
            # Configure the mock to return our mock_db when used as a context manager
            mock_connect.return_value.__aenter__.return_value = mock_db

            await self.db.initialize()

            mock_db.execute.assert_called_once_with("PRAGMA foreign_keys = ON")
            mock_db.executescript.assert_not_called()
            mock_db.commit.assert_not_called()

    async def test_get_connection(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        with patch("aiosqlite.connect", new_callable=AsyncMock) as mock_connect:
            # Make the connect function return our mock_db when awaited
            mock_connect.return_value = mock_db

            conn = await self.db._get_connection()

            # Verify connect was called with the correct path
            mock_connect.assert_called_once_with(self.db.db_path)

            # Verify the row_factory was set
            self.assertEqual(mock_db.row_factory, aiosqlite.Row)

            # Verify the connection was returned
            self.assertEqual(conn, mock_db)
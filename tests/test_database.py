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

    async def test_execute(self):
        # Create a mock database connection and cursor
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 123

        # Set up mock db methods
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        mock_db.commit = AsyncMock()

        # Set up _get_connection to return a mock that works with async with
        with patch.object(self.db, '_get_connection', new_callable=AsyncMock) as mock_get_connection:
            # Configure the mock connection to work as a context manager
            mock_get_connection.return_value.__aenter__.return_value = mock_db

            # Call the method being tested
            result = await self.db.execute("SELECT * FROM test")

            # Verify the query was executed with correct parameters
            mock_db.execute.assert_called_once_with("SELECT * FROM test", ())
            mock_db.commit.assert_called_once()

            # Verify the lastrowid was returned
            self.assertEqual(result, 123)

    async def test_execute_exception(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        # Set up mock methods
        mock_db.execute = AsyncMock(side_effect=Exception("Test exception"))
        mock_db.commit = AsyncMock()

        # Set up _get_connection to return a mock that works with async with
        with patch.object(self.db, '_get_connection', new_callable=AsyncMock) as mock_get_connection:
            # Configure the mock connection to work as a context manager
            mock_get_connection.return_value.__aenter__.return_value = mock_db

            # Call the method being tested
            result = await self.db.execute("SELECT * FROM test")

            # Verify the query was executed with correct parameters
            mock_db.execute.assert_called_once_with("SELECT * FROM test", ())
            mock_db.commit.assert_not_called()

            # Verify None was returned
            self.assertEqual(result, None)

    async def test_execute_many(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        # Set up mock methods
        mock_db.executemany = AsyncMock()
        mock_db.commit = AsyncMock()

        # Set up _get_connection to return a mock that works with async with
        with patch.object(self.db, '_get_connection', new_callable=AsyncMock) as mock_get_connection:
            # Configure the mock connection to work as a context manager
            mock_get_connection.return_value.__aenter__.return_value = mock_db

            # Call the method being tested
            result = await self.db.execute_many("INSERT INTO test VALUES (?)", [(1,), (2,), (3,)])

            # Verify the query was executed with correct parameters
            mock_db.executemany.assert_called_once_with("INSERT INTO test VALUES (?)", [(1,), (2,), (3,)])
            mock_db.commit.assert_called_once()

            # Verify True was returned
            self.assertEqual(result, True)

    async def test_execute_many_exception(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        # Set up mock methods
        mock_db.executemany = AsyncMock(side_effect=Exception("Test exception"))
        mock_db.commit = AsyncMock()

        # Set up _get_connection to return a mock that works with async with
        with patch.object(self.db, '_get_connection', new_callable=AsyncMock) as mock_get_connection:
            # Configure the mock connection to work as a context manager
            mock_get_connection.return_value.__aenter__.return_value = mock_db

            # Call the method being tested
            result = await self.db.execute_many("INSERT INTO test VALUES (?)", [(1,), (2,), (3,)])

            # Verify the query was executed with correct parameters
            mock_db.executemany.assert_called_once_with("INSERT INTO test VALUES (?)", [(1,), (2,), (3,)])
            mock_db.commit.assert_not_called()

            # Verify False was returned
            self.assertEqual(result, False)

    async def test_fetch_one(self):
        # Create a mock database connection and cursor
        mock_db = AsyncMock()
        mock_cursor = AsyncMock()

        # Create a mock row that acts like aiosqlite.Row
        mock_row = {"id": 1, "name": "test"}

        # Set up fetchone as AsyncMock that returns our mock row
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)

        # Set up mock db methods
        mock_db.execute = AsyncMock(return_value=mock_cursor)

        # Set up _get_connection to return a mock that works with async with
        with patch.object(self.db, '_get_connection', new_callable=AsyncMock) as mock_get_connection:
            # Configure the mock connection to work as a context manager
            mock_get_connection.return_value.__aenter__.return_value = mock_db

            # Call the method being tested
            result = await self.db.fetch_one("SELECT * FROM test")

            # Verify the query was executed with correct parameters
            mock_db.execute.assert_called_once_with("SELECT * FROM test", ())

            # Verify the row was returned as a dictionary
            self.assertEqual(result, {"id": 1, "name": "test"})

    async def test_fetch_one_exception(self):
        # Create a mock database connection
        mock_db = AsyncMock()

        # Set up mock methods
        mock_db.execute = AsyncMock(side_effect=Exception("Test exception"))

        # Set up _get_connection to return a mock that works with async with
        with patch.object(self.db, '_get_connection', new_callable=AsyncMock) as mock_get_connection:
            # Configure the mock connection to work as a context manager
            mock_get_connection.return_value.__aenter__.return_value = mock_db

            # Call the method being tested
            result = await self.db.fetch_one("SELECT * FROM test")

            # Verify the query was executed with correct parameters
            mock_db.execute.assert_called_once_with("SELECT * FROM test", ())

            # Verify None was returned
            self.assertEqual(result, None)

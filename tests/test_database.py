import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from src.database.database import Database
import os
import aiosqlite
import uuid
from src.utils.logging_config import configure_logging

log = configure_logging()

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create a unique database file for each test to ensure isolation
        # Use UUID to generate a unique name
        self.test_db_path = f"data/test/test_{uuid.uuid4().hex}.db"
        self.db = Database(db_path=self.test_db_path, pool_size=3)

    async def asyncSetUp(self):
        # This runs after setUp but before each test
        # Initialize the database for tests that need it
        self.db_initialized = False
        
    async def asyncTearDown(self):
        # This runs after each test but before tearDown
        # Ensure all database connections are properly closed
        await self.db.close_all_connections()
        
    def tearDown(self):
        # Remove the database file
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except PermissionError:
                # On Windows, sometimes the file handle isn't released immediately
                # Just log this rather than failing the test
                print(f"Could not delete {self.test_db_path}, will be cleaned up later.")

    # Helper to initialize database when needed
    async def init_db_if_needed(self):
        if not self.db_initialized:
            await self.db.initialize()
            self.db_initialized = True

    async def test_initialize(self):
        # Create a mock database connection
        mock_conn = AsyncMock()
        
        # Set up mock methods for the connection
        mock_conn.execute = AsyncMock()
        mock_conn.executescript = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.close = AsyncMock()

        # Mock cursor functionality
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0,))
        mock_conn.execute.return_value = mock_cursor
        
        # Fix: Patch the _create_connection method directly
        with patch.object(self.db, '_create_connection', return_value=mock_conn):
            success = await self.db.initialize()

            self.assertTrue(success)
            # No need to check for PRAGMA foreign_keys here as it's now in _create_connection
            mock_conn.executescript.assert_called_once()
            mock_conn.commit.assert_called_once()
            mock_conn.close.assert_called_once()

    async def test_create_connection(self):
        """Test that _create_connection properly sets up PRAGMA foreign_keys"""
        # Fix: Make the mock connect function return a coroutine that returns mock_conn
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        
        # Create a mock for aiosqlite.connect that returns a coroutine
        async def mock_connect(*args, **kwargs):
            return mock_conn
            
        with patch('aiosqlite.connect', mock_connect):
            conn = await self.db._create_connection()
            
            # This is where PRAGMA foreign_keys should be called now
            mock_conn.execute.assert_called_with("PRAGMA foreign_keys = ON")
            # Make sure we got back the expected connection
            self.assertEqual(conn, mock_conn)

    async def test_initialize_no_schema(self):
        # Create a mock database connection
        mock_conn = AsyncMock()
        
        # Set up mock methods
        mock_conn.execute = AsyncMock()
        mock_conn.executescript = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.close = AsyncMock()

        # Mock cursor functionality
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0,))
        mock_conn.execute.return_value = mock_cursor

        # Fix: Patch the _create_connection method directly
        with patch.object(self.db, '_create_connection', return_value=mock_conn):
            # Set the schema path to a non-existent file
            self.db.schema_path = "nonexistent_directory/nonexistent_file.sql"

            success = await self.db.initialize()

            self.assertTrue(success)
            # We're no longer checking for PRAGMA here since it moved to _create_connection
            mock_conn.executescript.assert_not_called()
            mock_conn.close.assert_called_once()

    async def test_initialize_exception(self):
        # Patch _create_connection to raise an exception
        with patch.object(self.db, '_create_connection', side_effect=Exception("Test exception")):
            success = await self.db.initialize()
            self.assertFalse(success)

    async def test_schema_version_tracking(self):
        # Initialize real database for this test
        await self.init_db_if_needed()

        # Check the schema_version table directly using a separate connection
        conn = await aiosqlite.connect(self.test_db_path)
        conn.row_factory = aiosqlite.Row
        try:
            cursor = await conn.execute("SELECT MAX(version) as version FROM schema_version")
            row = await cursor.fetchone()
            
            self.assertIsNotNone(row, "Schema version table is empty or not created.")
            self.assertEqual(row["version"], 2)
        finally:
            await conn.close()

    async def test_connection_pooling(self):
        # Initialize the pool
        await self.db._initialize_pool()
        
        try:
            # Check pool size
            self.assertEqual(len(self.db._connection_pool), 3)
            
            # Get connections from pool
            conn1 = await self.db._get_connection()
            conn2 = await self.db._get_connection()
            conn3 = await self.db._get_connection()
            
            # Pool should be empty now
            self.assertEqual(len(self.db._connection_pool), 0)
            
            # Release connections back to pool
            await self.db._release_connection(conn1)
            await self.db._release_connection(conn2)
            await self.db._release_connection(conn3)
            
            # Pool should be refilled
            self.assertEqual(len(self.db._connection_pool), 3)
        finally:
            # Make sure pool is closed even if test fails
            await self.db.close_all_connections()

    async def test_get_connection(self):
        # Test the _get_connection method directly
        conn = await self.db._get_connection()
        
        try:
            # Verify it's a valid connection
            self.assertIsInstance(conn, aiosqlite.Connection)
        finally:
            # Always close the connection
            await conn.close()

    async def test_execute(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Create a test table
        result = await self.db.execute(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)"
        )
        self.assertIsNotNone(result)
        
        # Insert data
        rowid = await self.db.execute(
            "INSERT INTO test_table (name) VALUES (?)",
            ("Test Name",)
        )
        self.assertIsNotNone(rowid)
        self.assertGreater(rowid, 0)

    async def test_execute_exception(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Try invalid SQL
        result = await self.db.execute("SELECT * FROM nonexistent_table")
        self.assertIsNone(result)

    async def test_execute_many(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Create a test table
        await self.db.execute(
            "CREATE TABLE IF NOT EXISTS test_bulk (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        # Prepare bulk data
        data = [("value1",), ("value2",), ("value3",)]
        
        # Insert using execute_many
        success = await self.db.execute_many(
            "INSERT INTO test_bulk (value) VALUES (?)",
            data
        )
        
        self.assertTrue(success)
        
        # Verify the insertions
        rows = await self.db.fetch_many("SELECT * FROM test_bulk ORDER BY id")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["value"], "value1")
        self.assertEqual(rows[1]["value"], "value2")
        self.assertEqual(rows[2]["value"], "value3")

    async def test_execute_many_exception(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Try invalid SQL
        success = await self.db.execute_many(
            "INSERT INTO nonexistent_table (value) VALUES (?)",
            [("test",)]
        )
        
        self.assertFalse(success)

    async def test_fetch_one(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Create a test table with data
        await self.db.execute(
            "CREATE TABLE IF NOT EXISTS test_fetch (id INTEGER PRIMARY KEY, name TEXT)"
        )
        await self.db.execute("INSERT INTO test_fetch (name) VALUES (?)", ("Test Name",))
        
        # Fetch the inserted row
        row = await self.db.fetch_one("SELECT * FROM test_fetch WHERE id = 1")
        
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], 1)
        self.assertEqual(row["name"], "Test Name")

    async def test_fetch_one_exception(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Try invalid SQL
        row = await self.db.fetch_one("SELECT * FROM nonexistent_table")
        
        self.assertIsNone(row)

    async def test_fetch_one_not_found(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Create a test table with no data
        await self.db.execute(
            "CREATE TABLE IF NOT EXISTS test_empty (id INTEGER PRIMARY KEY, name TEXT)"
        )
        
        # Try to fetch non-existent row
        row = await self.db.fetch_one("SELECT * FROM test_empty WHERE id = 1")
        
        self.assertIsNone(row)

    async def test_fetch_many(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Create a test table with data
        await self.db.execute(
            "CREATE TABLE IF NOT EXISTS test_fetch_many (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        # Insert multiple rows
        values = [("value1",), ("value2",), ("value3",)]
        await self.db.execute_many("INSERT INTO test_fetch_many (value) VALUES (?)", values)
        
        # Fetch all rows
        rows = await self.db.fetch_many("SELECT * FROM test_fetch_many ORDER BY id")
        
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["value"], "value1")
        self.assertEqual(rows[1]["value"], "value2")
        self.assertEqual(rows[2]["value"], "value3")

    async def test_fetch_many_exception(self):
        # Initialize the database
        await self.init_db_if_needed()
        
        # Try invalid SQL
        rows = await self.db.fetch_many("SELECT * FROM nonexistent_table")
        
        self.assertEqual(rows, [])

    async def test_close_all_connections(self):
        """Test that all connections are properly closed"""
        # Initialize the pool
        await self.db._initialize_pool()
        
        # Get connections from pool and store their references
        conn1 = await self.db._get_connection()
        conn2 = await self.db._get_connection()
        
        # Keep one connection out of the pool and return one to the pool
        await self.db._release_connection(conn1)
        
        # For aiosqlite, we need to make sure we have the connection working first
        try:
            await conn2.execute("SELECT 1")
        except Exception as e:
            self.fail(f"Connection should be usable before closing: {e}")
            
        # Close all connections (including both pooled and active)
        await self.db.close_all_connections()
        
        # Verify the pool state
        self.assertEqual(len(self.db._connection_pool), 0)
        self.assertFalse(self.db._pool_initialized)
        
        # The connection should be closed, which makes this property inaccessible
        self.assertTrue(conn2._connection is None or 
                        not hasattr(conn2, '_connection'), 
                        "Connection should be closed")
                      
        # Additional verification - try to execute and expect a failure
        # This should raise an exception like "Cannot operate on a closed database"
        try:
            await conn2.execute("SELECT 1")
            # If we get here, the connection wasn't closed
            self.fail("Connection should be closed and raise an exception when used")
        except Exception:
            # This is expected - any exception confirms the connection is closed
            pass

    async def test_initialize_pool_already_initialized(self):
        """Test that _initialize_pool doesn't reinitialize if already initialized"""
        # First initialize the pool
        await self.db._initialize_pool()
        
        # Store the initial connection objects for comparison
        initial_connections = list(self.db._connection_pool)
        
        # Call initialize again
        await self.db._initialize_pool()
        
        # Verify the pool didn't change
        self.assertEqual(len(self.db._connection_pool), 3)
        self.assertEqual(initial_connections, self.db._connection_pool)
        
        # Clean up
        await self.db.close_all_connections()

    async def test_get_connection_pool_empty(self):
        """Test getting a connection when the pool is empty"""
        # Initialize the pool
        await self.db._initialize_pool()
        
        # Empty the pool by getting all connections
        conn1 = await self.db._get_connection()
        conn2 = await self.db._get_connection()
        conn3 = await self.db._get_connection()
        
        # Pool should be empty now
        self.assertEqual(len(self.db._connection_pool), 0)
        
        # Get one more connection - this should create a new one
        conn4 = await self.db._get_connection()
        
        # Verify we got a valid connection
        self.assertIsInstance(conn4, aiosqlite.Connection)
        
        # Clean up
        await self.db._release_connection(conn1)
        await self.db._release_connection(conn2)
        await self.db._release_connection(conn3)
        await self.db._release_connection(conn4)

    async def test_release_connection_pool_full(self):
        """Test releasing a connection when the pool is already full"""
        # Initialize the pool
        await self.db._initialize_pool()
        
        # Create an extra connection outside the pool
        extra_conn = await aiosqlite.connect(self.test_db_path)
        
        # Add this connection to the tracking set
        self.db._all_connections.add(extra_conn)
        
        # Release the connection - it should be closed since the pool is full
        await self.db._release_connection(extra_conn)
        
        # Verify pool size is still 3
        self.assertEqual(len(self.db._connection_pool), 3)
        
        # Verify the connection is no longer in tracking
        self.assertNotIn(extra_conn, self.db._all_connections)

    async def test_release_connection_exception(self):
        """Test exception handling in the _release_connection method"""
        # Create a connection that will raise an exception when closed
        bad_conn = AsyncMock()
        bad_conn.__bool__ = lambda x: True  # Make it truthy
        bad_conn.close = AsyncMock(side_effect=Exception("Test exception on close"))
        
        # Create a mock pool that raises an exception when appended to
        mock_pool = MagicMock()
        mock_pool.append.side_effect = Exception("Test exception on append")
        
        # Save the original pool and replace with our mock
        original_pool = self.db._connection_pool
        self.db._connection_pool = mock_pool
        
        try:
            # This should not raise an exception to the caller
            await self.db._release_connection(bad_conn)
            
            # Verify error handling closed the connection
            bad_conn.close.assert_called_once()
            
            # Verify append was attempted
            mock_pool.append.assert_called_once()
        finally:
            # Restore the original pool
            self.db._connection_pool = original_pool

    async def test_release_connection_none(self):
        """Test that _release_connection handles None connections gracefully"""
        # This should not raise an exception
        await self.db._release_connection(None)
        
        # Nothing to verify - just ensuring no exception is raised

    async def test_close_all_connections_with_exception(self):
        """Test that close_all_connections handles exceptions when closing connections"""
        # Initialize the pool
        await self.db._initialize_pool()
        
        # Create a connection that will raise an exception when closed
        bad_conn = AsyncMock()
        bad_conn.close = AsyncMock(side_effect=Exception("Test close exception"))
        
        # Add the bad connection to the pool
        self.db._connection_pool.append(bad_conn)
        
        # Add another bad connection to the tracking set
        tracked_bad_conn = AsyncMock()
        tracked_bad_conn.close = AsyncMock(side_effect=Exception("Test tracked close exception"))
        self.db._all_connections.add(tracked_bad_conn)
        
        # Close all connections - this should not raise exceptions
        await self.db.close_all_connections()
        
        # Verify all close methods were called
        bad_conn.close.assert_called_once()
        tracked_bad_conn.close.assert_called_once()
        
        # Verify the pool and tracking set are empty
        self.assertEqual(len(self.db._connection_pool), 0)
        self.assertEqual(len(self.db._all_connections), 0)

    async def test_release_connection_close_exception(self):
        """Test double exception handling in the _release_connection method"""
        # Create a connection that will raise an exception when closed AND when appended
        bad_conn = AsyncMock()
        bad_conn.__bool__ = lambda x: True  # Make it truthy
        
        # Make both operations raise exceptions to test the nested exception handling
        # First exception when trying to add to pool
        mock_pool = MagicMock()
        mock_pool.append.side_effect = Exception("Test exception on append")
        
        # Second exception when trying to close the connection
        bad_conn.close = AsyncMock(side_effect=Exception("Test exception on close"))
        
        # Save the original pool and replace with our mock
        original_pool = self.db._connection_pool
        self.db._connection_pool = mock_pool
        
        try:
            # This should not raise an exception to the caller despite both operations failing
            await self.db._release_connection(bad_conn)
            
            # Verify append was attempted
            mock_pool.append.assert_called_once()
            
            # Verify close was attempted
            bad_conn.close.assert_called_once()
        finally:
            # Restore the original pool
            self.db._connection_pool = original_pool

    async def create_version_1_schema(self):
        """Helper method to create the version 1 schema"""
        async with aiosqlite.connect(self.test_db_path) as conn:
            await conn.executescript("""
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER NOT NULL UNIQUE,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (discord_id > 0)
                );

                CREATE INDEX IF NOT EXISTS idx_users_discord_id ON users(discord_id);

                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                INSERT INTO schema_version (version) VALUES (1);

                INSERT INTO users (discord_id, username, created_at, last_active)
                VALUES (12345, 'TestUser', '2025-03-01 12:00:00', '2025-03-01 12:00:00');
            """)
            await conn.commit()

    async def test_migration_1_to_2(self):
        # Create the version 1 schema
        await self.create_version_1_schema()

        # Run the database initialization (This should include the migration)
        success = await self.db.initialize()
        self.assertTrue(success)

        # Verify the schema version is updated to 2
        async with aiosqlite.connect(self.test_db_path) as conn:
            cursor = await conn.execute("SELECT MAX(version) as version FROM schema_version")
            row = await cursor.fetchone()
            self.assertEqual(row[0], 2)

            # Verify the new schema
            cursor = await conn.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in await cursor.fetchall()]
            self.assertIn("discord_user_id", columns)
            self.assertIn("discord_guild_id", columns)

            # Verify the migrated data
            cursor = await conn.execute("SELECT * FROM users WHERE discord_user_id = 12345")
            user = await cursor.fetchone()
            self.assertIsNotNone(user)
            self.assertEqual(user[1], 12345)
            self.assertEqual(user[2], 0)  # Default value
            self.assertEqual(user[3], "TestUser")

    async def test_no_migration_for_version_2(self):
        # Create a version 2 database
        await self.db.initialize()

        # Re-initialize the database
        success = await self.db.initialize()
        self.assertTrue(success)

        # Verify no additional migrations were applied
        async with aiosqlite.connect(self.test_db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM schema_version WHERE version = 2")
            row = await cursor.fetchone()
            self.assertEqual(row[0], 1)
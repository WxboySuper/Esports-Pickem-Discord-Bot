import os
import aiosqlite
from typing import List, Dict, Any, Optional, Union
from src.utils.logging_config import configure_logging

log = configure_logging()

# TODO: Investigate connection pooling for better performance


class Database:
    """
    Database handler for the Esports Pick'em bot

    This class handles all low-level database operations and provides
    a consistent interface for model classes to use.
    """

    def __init__(self, db_path: str = "data/pickem.db"):
        """
        Initialize the database handler

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # Ensure the database file exists
        if not os.path.exists(db_path):
            open(db_path, 'w').close()
            log.info(f"Created empty database file: {db_path}")
        log.info(f"Database path set to: {db_path}")

        self.schema_path = "src/database/schema/schema.sql"

    async def initialize(self) -> bool:
        """
        Initialize the database schema

        Returns:
            True if successful, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Enable foreign keys
                await db.execute("PRAGMA foreign_keys = ON")

                if os.path.exists(self.schema_path):
                    with open(self.schema_path, "r") as f:
                        schema_script = f.read()
                    await db.executescript(schema_script)
                else:
                    log.error(f"Schema file not found: {self.schema_path}")
                    return False

                await db.commit()
                log.info("Database initialized successfully")
                return True
        except Exception as e:
            log.error(f"Failed to initialize database: {str(e)}")
            return False

    async def _get_connection(self) -> aiosqlite.Connection:
        """
        Get a database connection with row factory enabled

        Returns:
            SQLite database connection
        """
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        return conn

    async def execute(self, query: str, params: Union[tuple, list] = ()) -> Optional[int]:
        """
        Execute a database query

        Args:
            query (str): SQL query to execute
            params (tuple, optional): Query parameters. Defaults to ().

        Returns:
            Optional[int]: Last row ID or None if error
        """
        try:
            async with await self._get_connection() as db:
                cursor = await db.execute(query, params)
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            log.error(f"Database execute error: {str(e)}\nQuery: {query}\nParams: {params}")
            return None

    async def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """
        Execute many queries at once

        Args:
            query (str): SQL query with placeholders
            params_list (List[tuple]): List of parameter tuples

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            async with await self._get_connection() as db:
                await db.executemany(query, params_list)
                await db.commit()
                return True
        except Exception as e:
            log.error(f"Database executemany error: {str(e)}\nQuery: {query}\nParams: {params_list}")
            return False

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row from the database

        Args:
            query (str): SQL query to execute
            params (tuple, optional): Query parameters. Defaults to ().

        Returns:
            Optional[Dict[str, Any]]: Row as dictionary or None if not found or error
        """
        try:
            async with await self._get_connection() as db:
                cursor = await db.execute(query, params)
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            log.error(f"Database fetch_one error: {str(e)}\nQuery: {query}\nParams: {params}")
            return None

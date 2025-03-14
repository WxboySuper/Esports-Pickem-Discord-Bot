import os
import aiosqlite
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Tuple
from src.utils.logging_config import configure_logging
import re

log = configure_logging()

# TODO: Add Docstrings

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
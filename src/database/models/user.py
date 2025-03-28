from typing import Optional, List, Dict, Any
from src.database.database import Database
from src.utils.logging_config import configure_logging

log = configure_logging()

class User:
    """
    Interface for user-related database operations.

    This model provides methods to create, retrieve, update, and delete
    user records in the database.
    """
    def __init__(self, db_id: Optional[int] = None, discord_user_id: int = 0, discord_guild_id: int = 0,
                 username: Optional[str] = None, created_at: Optional[str] = None, last_active: Optional[str] = None):
        self.db_id = db_id
        self.discord_user_id = discord_user_id
        self.discord_guild_id = discord_guild_id
        self.username = username
        self.created_at = created_at
        self.last_active = last_active

    @staticmethod
    async def create(db: Database, discord_user_id: int, discord_guild_id: int, username: str) -> Optional['User']:
        """Create a new user in the database"""
        log.info(f"Creating user {username} with ID {discord_user_id} in guild {discord_guild_id}")
        query = """
            INSERT INTO users (discord_user_id, discord_guild_id, username)
            VALUES (?, ?, ?)
        """
        user_id = await db.execute(query, (discord_user_id, discord_guild_id, username))
        if user_id:
            log.info(f"User {username} successfully created with ID {user_id}")
            return User(db_id=user_id, discord_user_id=discord_user_id, discord_guild_id=discord_guild_id, username=username)
        log.error(f"Failed to create user {username} with ID {discord_user_id}")
        return None

from typing import Optional, List
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
        """Create a new user in the database.

        Args:
            db: Database instance to use for the query.
            discord_user_id: The Discord user ID to associate with this user.
            discord_guild_id: The Discord guild ID to associate with this user.
            username: The username for this user.

        Returns:
            A new User instance if creation was successful, None otherwise.
        """
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

    @staticmethod
    async def get_by_id(db: Database, user_id: int) -> Optional['User']:
        """
        Retrieve a user by their ID.

        Args:
            db: Database instance to use for the query.
            user_id: The ID of the user to retrieve.

        Returns:
            A User instance if found, None otherwise.
        """
        log.info(f"Attempting to retrieve user with ID {user_id}")
        query = "SELECT * FROM users WHERE id = ?"
        try:
            row = await db.fetch_one(query, (user_id,))
            if row:
                log.info(f"User with ID {user_id} retrieved successfully: {row}")
                return User(**row)
            log.warning(f"No user found with ID {user_id}")
            return None
        except Exception as e:
            log.error(f"Error retrieving user with ID {user_id}: {str(e)}")
            return None

    @staticmethod
    async def get_by_discord_user_id(db: Database, discord_user_id: int) -> Optional['User']:
        """
        Retrieve a user by their Discord user ID.

        Args:
            db: Database instance to use for the query.
            discord_user_id: The Discord user ID of the user to retrieve.

        Returns:
            A User instance if found, None otherwise.
        """
        log.info(f"Attempting to retrieve user with Discord user ID {discord_user_id}")
        query = "SELECT * FROM users WHERE discord_user_id = ?"
        try:
            row = await db.fetch_one(query, (discord_user_id,))
            if row:
                log.info(f"User with Discord user ID {discord_user_id} retrieved successfully: {row}")
                return User(**row)
            log.warning(f"No user found with Discord user ID {discord_user_id}")
            return None
        except Exception as e:
            log.error(f"Error retrieving user with Discord user ID {discord_user_id}: {str(e)}")
            return None

    @staticmethod
    async def get_all(db: Database) -> List['User']:
        """
        Retrieve all users from the database.

        Args:
            db: Database instance to use for the query.

        Returns:
            A list of User instances.
        """
        log.info("Attempting to retrieve all users from the database")
        query = "SELECT * FROM users"
        try:
            rows = await db.fetch_all(query)
            if rows:
                log.info(f"Successfully retrieved {len(rows)} users from the database")
                return [User(**row) for row in rows]
            log.warning("No users found in the database")
            return []
        except Exception as e:
            log.error(f"Error retrieving all users from the database: {str(e)}")
            return []

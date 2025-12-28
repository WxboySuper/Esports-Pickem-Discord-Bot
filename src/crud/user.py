import logging
from typing import Optional
from sqlmodel import Session, select
from src.models import User
from .base import _save_and_refresh, _delete_and_commit

logger = logging.getLogger(__name__)


def create_user(
    session: Session,
    discord_id: str,
    username: Optional[str] = None,
) -> User:
    """
    Create a new User record with the given Discord ID and optional username.

    Parameters:
        discord_id (str): Discord identifier for the user.
        username (Optional[str]): Display name to associate with
            the user; if omitted, the username will be unset.

    Returns:
        user (User): The persisted User instance with its
            database-assigned `id` populated.
    """
    logger.info("Creating user: %s (%s)", username, discord_id)
    user = User(discord_id=discord_id, username=username)
    _save_and_refresh(session, user)
    logger.info("Created user with ID: %s", user.id)
    return user


def get_user_by_discord_id(
    session: Session,
    discord_id: str,
) -> Optional[User]:
    logger.debug("Fetching user by discord_id: %s", discord_id)
    statement = select(User).where(User.discord_id == discord_id)
    return session.exec(statement).first()


def update_user(
    session: Session, user_id: int, username: Optional[str] = None
) -> Optional[User]:
    """
    Update a user's username when a new value is provided.

    Fetches the User by id, sets the username if `username` is not
    None, persists the change, and returns the updated User.

    Parameters:
        user_id (int): Primary key of the User to update.
        username (Optional[str]): New username to apply; if None,
            the user's username is left unchanged.

    Returns:
        User | None: The updated User instance, or `None` if no user
            with the given id exists.
    """
    logger.info("Updating user ID: %s", user_id)
    user = session.get(User, user_id)
    if not user:
        logger.warning("User with ID %s not found for update.", user_id)
        return None
    if username is not None:
        user.username = username
    _save_and_refresh(session, user)
    logger.info("Updated user ID: %s", user_id)
    return user


def delete_user(session: Session, user_id: int) -> bool:
    """
    Delete a user record by its primary key and persist the change.

    Deletes the user with the given ID from the database and commits
    the transaction.

    Returns:
        `true` if the user was found and deleted, `false` otherwise.
    """
    logger.info("Deleting user ID: %s", user_id)
    user = session.get(User, user_id)
    if not user:
        logger.warning("User with ID %s not found for deletion.", user_id)
        return False
    _delete_and_commit(session, user)
    logger.info("Deleted user ID: %s", user_id)
    return True

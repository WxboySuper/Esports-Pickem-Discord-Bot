import logging
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass
from sqlalchemy import update
from sqlalchemy import update
from sqlmodel import Session, select
from src.models import Pick
from .base import _save_and_refresh, _delete_and_commit

logger = logging.getLogger(__name__)


@dataclass
class PickCreateParams:
    user_id: int
    contest_id: int
    match_id: int
    chosen_team: str
    timestamp: Optional[datetime] = None


# Allow this function to have multiple explicit args for clarity
# despite lint rules
# pylint: disable=too-many-arguments
def create_pick(session: Session, params: PickCreateParams) -> Pick:
    """
    Create and persist a Pick for a user in a contest match.

    Parameters:
        params (PickCreateParams): Parameter object containing
            `user_id`, `contest_id`, `match_id`, `chosen_team`, and optional
            `timestamp`.

    Returns:
        Pick: The persisted Pick instance with database-populated
            fields (for example, `id`) refreshed.
    """
    logger.info(
        "Creating pick for user %s, match %s, team %s",
        params.user_id,
        params.match_id,
        params.chosen_team,
    )
    pick_args = dict(
        user_id=params.user_id,
        contest_id=params.contest_id,
        match_id=params.match_id,
        chosen_team=params.chosen_team,
    )
    if params.timestamp is not None:
        pick_args["timestamp"] = params.timestamp
    pick = Pick(**pick_args)
    _save_and_refresh(session, pick)
    logger.info("Created pick with ID: %s", pick.id)
    return pick


def get_pick_by_id(session: Session, pick_id: int) -> Optional[Pick]:
    logger.debug("Fetching pick by ID: %s", pick_id)
    return session.get(Pick, pick_id)


def list_picks_for_user(session: Session, user_id: int) -> List[Pick]:
    logger.debug("Listing picks for user ID: %s", user_id)
    statement = select(Pick).where(Pick.user_id == user_id)
    return list(session.exec(statement))


def list_picks_for_match(session: Session, match_id: int) -> List[Pick]:
    logger.debug("Listing picks for match ID: %s", match_id)
    statement = select(Pick).where(Pick.match_id == match_id)
    return list(session.exec(statement))


def update_pick(
    session: Session, pick_id: int, chosen_team: Optional[str] = None
) -> Optional[Pick]:
    """
    Update an existing Pick's chosen team.

    Parameters:
        session (Session): Database session used for the update.
        pick_id (int): Primary key of the Pick to update.
        chosen_team (Optional[str]): New team name to set; if None the
            field is left unchanged.

    Returns:
        Optional[Pick]: The updated Pick if found, otherwise None.
    """
    logger.info("Updating pick ID: %s", pick_id)
    pick = session.get(Pick, pick_id)
    if not pick:
        logger.warning("Pick with ID %s not found for update.", pick_id)
        return None
    if chosen_team is not None:
        pick.chosen_team = chosen_team
    _save_and_refresh(session, pick)
    logger.info("Updated pick ID: %s", pick_id)
    return pick


def delete_pick(session: Session, pick_id: int) -> bool:
    """
    Delete a Pick record identified by its primary key.

    Attempts to remove the Pick with the given id from the database and
    commit the change.

    Parameters:
        pick_id (int): Primary key of the Pick to delete.

    Returns:
        bool: `True` if the pick was deleted, `False` if no pick with
            the given id existed.
    """
    logger.info("Deleting pick ID: %s", pick_id)
    pick = session.get(Pick, pick_id)
    if not pick:
        logger.warning("Pick with ID %s not found for deletion.", pick_id)
        return False
    _delete_and_commit(session, pick)
    logger.info("Deleted pick ID: %s", pick_id)
    return True


def score_picks_for_match(
    session: Session, match_id: int, winner: str, score: int = 10
) -> int:
    """
    Scores all picks for a given match based on the winning team.

    This function performs a bulk update and does not commit the session.

    Parameters:
        session (Session): The database session.
        match_id (int): The ID of the match to score picks for.
        winner (str): The winning team's name.
        score (int): The score to award for a correct pick.

    Returns:
        int: The number of picks that were updated.
    """
    # Score correct picks
    correct_stmt = (
        update(Pick)
        .where(Pick.match_id == match_id)
        .where(Pick.chosen_team == winner)
        .values(status="correct", score=score)
    )
    correct_result = session.exec(correct_stmt)
    correct_rows = correct_result.rowcount

    # Score incorrect picks
    incorrect_stmt = (
        update(Pick)
        .where(Pick.match_id == match_id)
        .where(Pick.chosen_team != winner)
        .values(status="incorrect", score=0)
    )
    incorrect_result = session.exec(incorrect_stmt)
    incorrect_rows = incorrect_result.rowcount

    total_updated = correct_rows + incorrect_rows
    logger.info(
        "Scored %d picks for match %d (winner: %s)",
        total_updated,
        match_id,
        winner,
    )
    return total_updated


def score_picks_for_match(
    session: Session, match_id: int, winner: str, score: int = 10
) -> int:
    """
    Scores all picks for a given match based on the winning team.

    This function performs a bulk update and does not commit the session.

    Parameters:
        session (Session): The database session.
        match_id (int): The ID of the match to score picks for.
        winner (str): The winning team's name.
        score (int): The score to award for a correct pick.

    Returns:
        int: The number of picks that were updated.
    """
    # Score correct picks
    correct_stmt = (
        update(Pick)
        .where(Pick.match_id == match_id)
        .where(Pick.chosen_team == winner)
        .values(status="correct", score=score)
    )
    correct_result = session.exec(correct_stmt)
    correct_rows = correct_result.rowcount

    # Score incorrect picks
    incorrect_stmt = (
        update(Pick)
        .where(Pick.match_id == match_id)
        .where(Pick.chosen_team != winner)
        .values(status="incorrect", score=0)
    )
    incorrect_result = session.exec(incorrect_stmt)
    incorrect_rows = incorrect_result.rowcount

    total_updated = correct_rows + incorrect_rows
    logger.info(
        "Scored %d picks for match %d (winner: %s)",
        total_updated,
        match_id,
        winner,
    )
    return total_updated

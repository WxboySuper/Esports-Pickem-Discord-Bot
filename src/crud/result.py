import logging
from typing import Optional
from sqlmodel import Session, select
from src.models import Result
from .base import _save_and_refresh, _delete_and_commit

logger = logging.getLogger(__name__)

def create_result(
    session: Session,
    match_id: int,
    winner: str,
    score: Optional[str] = None,
) -> Result:
    """
    Create a Result record linking a match to its winner and optional score.

    Parameters:
        match_id (int): Primary key of the match the result belongs to.
        winner (str): Identifier or name of the winning team.
        score (Optional[str]): Optional score string (for example "2-1").

    Returns:
        Result: The newly created and refreshed Result instance.
    """
    logger.info(f"Creating result for match ID: {match_id}")
    result = Result(match_id=match_id, winner=winner, score=score)
    _save_and_refresh(session, result)
    logger.info(f"Created result with ID: {result.id}")
    return result


def get_result_by_id(session: Session, result_id: int) -> Optional[Result]:
    logger.debug(f"Fetching result by ID: {result_id}")
    return session.get(Result, result_id)


def get_result_for_match(session: Session, match_id: int) -> Optional[Result]:
    logger.debug(f"Fetching result for match ID: {match_id}")
    stmt = select(Result).where(Result.match_id == match_id)
    return session.exec(stmt).first()


def update_result(
    session: Session,
    result_id: int,
    winner: Optional[str] = None,
    score: Optional[str] = None,
) -> Optional[Result]:
    """
    Update fields of an existing Result record.

    Only parameters provided (non-None) are applied to the stored Result.
    If the result with the given id does not exist, nothing is changed.

    Parameters:
        result_id (int): Primary key of the Result to update.
        winner (Optional[str]): New winner value to set, if provided.
        score (Optional[str]): New score value to set, if provided.

    Returns:
        Optional[Result]: The updated Result object when found and
            saved, or `None` if no matching Result exists.
    """
    logger.info(f"Updating result ID: {result_id}")
    result = session.get(Result, result_id)
    if not result:
        logger.warning(f"Result with ID {result_id} not found for update.")
        return None
    if winner is not None:
        result.winner = winner
    if score is not None:
        result.score = score
    _save_and_refresh(session, result)
    logger.info(f"Updated result ID: {result_id}")
    return result


def delete_result(session: Session, result_id: int) -> bool:
    """
    Delete the Result with the given primary key.

    Returns:
        True if a Result with the given `result_id` was found and
        deleted, False otherwise.
    """
    logger.info(f"Deleting result ID: {result_id}")
    result = session.get(Result, result_id)
    if not result:
        logger.warning(f"Result with ID {result_id} not found for deletion.")
        return False
    _delete_and_commit(session, result)
    logger.info(f"Deleted result ID: {result_id}")
    return True

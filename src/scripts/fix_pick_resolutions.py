import logging
import sys
from sqlmodel import select
from sqlalchemy.orm import selectinload
from src.db import get_session
from src.models import Match, Pick, Result

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_pick_resolutions")


def update_pick_state(pick: Pick, winner: str) -> bool:
    """
    Update a single pick's state based on the winner.
    Returns True if the pick was modified, False otherwise.
    """
    is_dirty = False
    is_correct = pick.chosen_team == winner
    expected_status = "correct" if is_correct else "incorrect"
    expected_score = 10 if is_correct else 0

    if pick.is_correct != is_correct:
        pick.is_correct = is_correct
        is_dirty = True

    if pick.status != expected_status:
        pick.status = expected_status
        is_dirty = True

    if pick.score != expected_score:
        pick.score = expected_score
        is_dirty = True

    return is_dirty


def process_match(session, match: Match) -> int:
    """
    Process picks for a single match.
    Returns the number of picks updated.
    """
    if not match.result or not match.picks:
        return 0

    winner = match.result.winner
    updated_count = 0

    for pick in match.picks:
        if update_pick_state(pick, winner):
            session.add(pick)
            updated_count += 1

    if updated_count > 0:
        logger.info("Match %s: Updated %d picks.", match.id, updated_count)

    return updated_count


def fix_picks():
    """
    Iterate over all matches with results and ensure all related picks
    have consistent `is_correct`, `status`, and `score` values.
    """
    logger.info("Starting pick resolution fix...")

    with get_session() as session:
        matches = session.exec(
            select(Match)
            .join(Result)
            .options(selectinload(Match.result), selectinload(Match.picks))
        ).all()

        logger.info("Found %d matches with results.", len(matches))

        total_picks_updated = 0
        matches_processed = 0

        for match in matches:
            updated = process_match(session, match)
            if updated > 0:
                total_picks_updated += updated
            matches_processed += 1

        if total_picks_updated > 0:
            session.commit()
            logger.info(
                "Successfully committed updates for %d picks across %d "
                "matches.",
                total_picks_updated,
                matches_processed,
            )
        else:
            logger.info("No picks needed updates.")


if __name__ == "__main__":
    try:
        fix_picks()
    except Exception:
        logger.exception("An error occurred during the fix process.")
        sys.exit(1)

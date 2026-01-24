import logging
import sys
from sqlmodel import select
from sqlalchemy.orm import selectinload
from src.db import get_session
from src.models import Match, Pick, Result

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_pick_resolutions")

def fix_picks():
    """
    Iterate over all matches with results and ensure all related picks
    have consistent `is_correct`, `status`, and `score` values.
    """
    logger.info("Starting pick resolution fix...")

    with get_session() as session:
        # Fetch all matches that have a result
        # Eagerly load the result and picks to avoid N+1 queries
        matches = session.exec(
            select(Match)
            .join(Result)
            .options(selectinload(Match.result), selectinload(Match.picks))
        ).all()

        logger.info(f"Found {len(matches)} matches with results.")

        total_picks_updated = 0
        matches_processed = 0

        for match in matches:
            if not match.result:
                continue

            winner = match.result.winner
            picks = match.picks

            if not picks:
                continue

            match_picks_updated = 0
            for pick in picks:
                is_dirty = False

                # Determine correct state based on winner
                is_correct = (pick.chosen_team == winner)
                expected_status = "correct" if is_correct else "incorrect"
                expected_score = 10 if is_correct else 0

                # Check if updates are needed
                if pick.is_correct != is_correct:
                    pick.is_correct = is_correct
                    is_dirty = True

                if pick.status != expected_status:
                    pick.status = expected_status
                    is_dirty = True

                if pick.score != expected_score:
                    pick.score = expected_score
                    is_dirty = True

                if is_dirty:
                    session.add(pick)
                    match_picks_updated += 1

            if match_picks_updated > 0:
                logger.info(f"Match {match.id}: Updated {match_picks_updated} picks.")
                total_picks_updated += match_picks_updated

            matches_processed += 1

        if total_picks_updated > 0:
            session.commit()
            logger.info(f"Successfully committed updates for {total_picks_updated} picks across {matches_processed} matches.")
        else:
            logger.info("No picks needed updates.")

if __name__ == "__main__":
    try:
        fix_picks()
    except Exception as e:
        logger.exception("An error occurred during the fix process.")
        sys.exit(1)

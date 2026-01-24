import logging
import asyncio
from sqlmodel import select, or_
from sqlalchemy.orm import selectinload
from src.db import get_async_session
from src.models import Pick, Match, Result

logger = logging.getLogger(__name__)


def _set_pick_correct(pick: Pick) -> bool:
    """Sets pick as correct if not already. Returns True if changed."""
    # Check if already correct state
    is_state_correct = (
        pick.is_correct is True
        and pick.status == "correct"
        and pick.score == 10
    )

    if is_state_correct:
        return False

    pick.is_correct = True
    pick.status = "correct"
    pick.score = 10
    return True


def _set_pick_incorrect(pick: Pick) -> bool:
    """Sets pick as incorrect if not already. Returns True if changed."""
    # Check if already incorrect state
    is_state_incorrect = (
        pick.is_correct is False
        and pick.status == "incorrect"
        and pick.score == 0
    )

    if is_state_incorrect:
        return False

    pick.is_correct = False
    pick.status = "incorrect"
    pick.score = 0
    return True


def _update_pick_if_needed(pick: Pick, winner: str) -> bool:
    """
    Evaluates if a pick needs updating based on the winner.
    Updates the pick in place and returns True if changed.
    """
    if pick.chosen_team == winner:
        return _set_pick_correct(pick)
    return _set_pick_incorrect(pick)


async def fix_pick_statuses():
    """
    Iterates through picks where the match has a result but the pick
    status is incorrect, pending, or has mismatched scores, and fixes them.
    """
    logger.info("Starting pick status repair job...")

    async with get_async_session() as session:
        # Optimized query:
        # We want picks where:
        # 1. The associated match has a result.
        # 2. AND (pick.status is 'pending' OR pick.status is 'incorrect'
        #    but was correct OR score mismatch etc.)
        stmt = (
            select(Pick)
            .join(Match)
            .join(Result)
            .options(selectinload(Pick.match).selectinload(Match.result))
            .where(
                or_(
                    Pick.status == "pending",
                    Pick.status.is_(None),
                    # Check for inconsistencies
                    (Pick.status == "correct") & (Pick.score != 10),
                    (Pick.status == "incorrect") & (Pick.score != 0),
                )
            )
        )

        result = await session.exec(stmt)
        picks = result.all()

        fixed_count = 0

        for pick in picks:
            match = pick.match
            match_result = match.result

            if not match_result:
                continue

            if _update_pick_if_needed(pick, match_result.winner):
                session.add(pick)
                fixed_count += 1

        if fixed_count > 0:
            await session.commit()
            logger.info(
                "Fixed %d picks with incorrect status/score.", fixed_count
            )
        else:
            logger.info("No picks needed fixing.")


if __name__ == "__main__":
    # Setup logging for standalone run
    logging.basicConfig(level=logging.INFO)
    asyncio.run(fix_pick_statuses())

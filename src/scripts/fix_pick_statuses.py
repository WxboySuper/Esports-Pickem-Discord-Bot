import logging
import asyncio
from sqlmodel import select, or_
from sqlalchemy.orm import selectinload
from src.db import get_async_session
from src.models import Pick, Match, Result

logger = logging.getLogger(__name__)


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
                    Pick.status.is_(None),  # Fix E711
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

            winner = match_result.winner
            should_be_correct = pick.chosen_team == winner

            needs_update = False

            if should_be_correct:
                if (
                    not pick.is_correct
                    or pick.status != "correct"
                    or pick.score != 10
                ):
                    pick.is_correct = True
                    pick.status = "correct"
                    pick.score = 10
                    needs_update = True
            else:
                if (
                    pick.is_correct
                    or pick.status != "incorrect"
                    or pick.score != 0
                ):
                    pick.is_correct = False
                    pick.status = "incorrect"
                    pick.score = 0
                    needs_update = True

            if needs_update:
                session.add(pick)
                fixed_count += 1

        if fixed_count > 0:
            await session.commit()
            logger.info(
                f"Fixed {fixed_count} picks with incorrect status/score."
            )
        else:
            logger.info("No picks needed fixing.")


if __name__ == "__main__":
    # Setup logging for standalone run
    logging.basicConfig(level=logging.INFO)
    asyncio.run(fix_pick_statuses())

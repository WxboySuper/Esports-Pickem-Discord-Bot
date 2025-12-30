"""
PandaScore-based live match polling for Esports Pickem Bot.

Polls the PandaScore API to detect match starts, score changes, and
final results. Replaces the Leaguepedia-based polling logic.
"""

import logging
import inspect

from src.db import get_async_session
from src.pandascore_client import pandascore_client
from src import crud
from src.pandascore_polling_core import (
    _process_running_match,
    _handle_finished_pandascore_id,
    _process_pandascore_match_data,
    _should_continue_polling,
    _fetch_match_from_pandascore,
    get_known_running_matches,
    remove_known_running_matches,
    _remove_job_if_exists as _core_remove,
)

logger = logging.getLogger(__name__)


# Note: running-match state is tracked in
# pandascore_polling_core._known_running_matches


async def poll_live_match_job(match_db_id: int) -> None:
    """
    Poll a single match via PandaScore API and handle result detection.

    Parameters:
        match_db_id: Database ID of the match to poll
    """
    job_id = f"poll_match_{match_db_id}"
    logger.info("Polling for match ID %s (Job: %s)", match_db_id, job_id)

    async with get_async_session() as session:
        match = await crud.get_match_with_result_by_id(session, match_db_id)

        if not await _should_continue_polling(match, job_id, session=session):
            return

        if not match.pandascore_id:
            logger.warning(
                "Match %s has no pandascore_id, cannot poll. Unscheduling.",
                match.id,
            )
            await _unschedule_job(job_id)
            return

        match_data = await _fetch_match_from_pandascore(match.pandascore_id)
        if not match_data:
            logger.info("No data returned for match %s. Will retry.", match.id)
            return

        committed = await _process_pandascore_match_data(
            session,
            match,
            match_data,
            job_id,
        )

        # Persist any changes made during processing (status updates,
        # last_announced_score, etc.). Processing helpers return a boolean
        # indicating whether they already committed a session. Only commit
        # here if no inner commit occurred.
        await _finalize_session_commit(session, committed, match.id)


async def poll_running_matches_job() -> None:
    """
    Poll all currently running matches from PandaScore.

    This job fetches the list of running matches and:
    1. Detects newly started matches
    2. Updates scores for ongoing matches
    3. Detects finished matches (disappeared from running list)
    """
    logger.debug("Running poll_running_matches_job...")

    running_matches = await _fetch_running_matches()
    running_ids = {m.get("id") for m in running_matches if m.get("id")}

    # Process running matches
    async with get_async_session() as session:
        await _process_running_matches(session, running_matches)

    # Process finished matches (were running but no longer are)
    # Use async accessors to safely read and modify the shared running set
    await _handle_finished_matches(running_ids)


async def _fetch_running_matches():
    """Fetch running matches, return empty list on error."""
    try:
        return await pandascore_client.fetch_running_matches()
    except Exception:
        logger.exception("Failed to fetch running matches")
        return []


async def _process_running_matches(session, running_matches):
    """Process running matches and commit if no inner commit occurred."""
    any_committed = False
    for match_data in running_matches:
        committed = await _process_running_match(session, match_data)
        any_committed = any_committed or bool(committed)

    if not any_committed:
        maybe = session.commit()
        if inspect.isawaitable(maybe):
            await maybe


async def _handle_finished_matches(running_ids):
    """Detect finished matches (were known running but no longer are).

    Removes finished IDs from the known set and dispatches handlers for
    each finished pandascore id.
    """
    known = await get_known_running_matches()
    finished_ids = known - running_ids
    if not finished_ids:
        return

    await remove_known_running_matches(finished_ids)
    for pandascore_id in finished_ids:
        await _handle_finished_pandascore_id(pandascore_id)


async def _unschedule_job(job_id: str) -> None:
    """Unschedule a job by delegating to the polling core helper.

    Kept as a small async wrapper so callers can await any future
    unscheduling implementation without inlining import logic.
    """

    # _core_remove is synchronous; keep wrapper async for future-proofing.
    _core_remove(job_id)


async def _finalize_session_commit(
    session, committed: bool, match_id: int
) -> None:
    """Commit the session if no inner commit occurred.

    This helper centralizes the awaitable vs non-awaitable handling so the
    primary job code stays small and focused.
    """
    try:
        if not committed:
            maybe = session.commit()
            # Await only if commit returned an awaitable (real AsyncSession)
            if inspect.isawaitable(maybe):
                await maybe
            try:
                setattr(session, "_committed", True)
            except Exception:
                pass
    except Exception:
        logger.exception(
            "Failed to commit session after processing match %s", match_id
        )
        raise

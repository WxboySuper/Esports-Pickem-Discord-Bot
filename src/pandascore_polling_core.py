"""
Core helper functions for PandaScore polling, extracted from
pandascore_polling.py to reduce file-level complexity.
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Set

from sqlmodel import select
from src.models import Match, Result
from src.pandascore_client import pandascore_client
from src import crud
from src import match_result_utils

logger = logging.getLogger(__name__)

# Shared running set protected by an asyncio lock
_known_running_matches: Set[int] = set()
_known_running_lock = asyncio.Lock()


async def get_known_running_matches() -> Set[int]:
    """Return a copy of the known running match IDs under the lock."""
    async with _known_running_lock:
        return set(_known_running_matches)


async def add_known_running_match(pandascore_id: int) -> None:
    """Add a pandascore id to the known-running set under the lock."""
    async with _known_running_lock:
        _known_running_matches.add(pandascore_id)


async def remove_known_running_matches(ids) -> None:
    """Remove a collection of pandascore ids from the known-running set."""
    async with _known_running_lock:
        for i in ids:
            _known_running_matches.discard(i)


def _remove_job_if_exists(job_id: str) -> None:
    from apscheduler.jobstores.base import JobLookupError

    try:
        from src.scheduler_instance import scheduler

        scheduler.remove_job(job_id)
    except JobLookupError:
        logger.debug("Job %s was already removed.", job_id)
    except Exception:
        logger.exception("Failed to remove job %s via scheduler", job_id)


async def _fetch_match_from_pandascore(pandascore_id: int) -> Optional[dict]:
    try:
        return await pandascore_client.fetch_match_by_id(pandascore_id)
    except Exception:
        logger.exception(
            "Failed to fetch match %s from PandaScore", pandascore_id
        )
        return None


async def _persist_result(match: Match, winner: str, current_score_str: str):
    """Persist a match result using the patched `get_async_session`.

    Returns a tuple `(result, committed)` where `committed` is True if the
    helper committed a session as part of persisting the result.
    """
    try:
        from src.db import get_async_session

        async with get_async_session() as session:
            result = await match_result_utils.save_result_and_update_picks(
                session, match, winner, current_score_str
            )
            await session.commit()
            try:
                setattr(session, "_committed", True)
            except Exception:
                pass
            return result, True
    except Exception:
        logger.exception("Failed to persist result for match %s", match.id)
        return None, False


async def _notify_result(match_id: int, result_id: int) -> None:
    try:
        from src.notifications import send_result_notification

        await send_result_notification(match_id, result_id)
    except Exception:
        logger.exception(
            "Failed to send result notification for match %s", match_id
        )


async def _notify_mid_series(match: Match, current_score_str: str) -> None:
    try:
        from src.notifications import send_mid_series_update

        await send_mid_series_update(match, current_score_str)
    except Exception:
        logger.exception(
            "Failed to send mid-series update for match %s", match.id
        )


async def _handle_winner(
    match: Match,
    winner: str,
    current_score_str: str,
    job_id: Optional[str] = None,
) -> bool:
    logger.info(
        "Series winner found for match %s: %s. Final Score: %s",
        match.id,
        winner,
        current_score_str,
    )

    result, committed = await _persist_result(match, winner, current_score_str)
    if result:
        logger.info("Saved result and updated picks for match %s.", match.id)
        await _notify_result(match.id, result.id)
    else:
        logger.error(
            "Failed to persist result for match %s; no notification sent",
            match.id,
        )

    if job_id is None:
        job_id = f"poll_match_{match.id}"
    logger.info("Unscheduling job %s for completed match.", job_id)
    _remove_job_if_exists(job_id)
    if match.pandascore_id:
        try:
            await remove_known_running_matches({match.pandascore_id})
        except Exception:
            logger.exception(
                "Failed to remove pandascore_id %s from running set",
                match.pandascore_id,
            )
    return bool(locals().get("committed", False))


async def _should_continue_polling(
    match: Optional[Match], job_id: str, session: Optional[Any] = None
) -> bool:
    if not match:
        logger.info("Match not found. Unscheduling '%s'.", job_id)
        _remove_job_if_exists(job_id)
        return False

    async def _result_exists(m: Match, sess: Optional[Any]) -> bool:
        # Check result existence without lazy load (MissingGreenlet-safe)
        if sess:
            stmt = select(Result).where(Result.match_id == m.id)
            res = await sess.exec(stmt)
            return bool(res.first())

        from src.db import get_async_session

        async with get_async_session() as new_session:
            stmt = select(Result).where(Result.match_id == m.id)
            res = await new_session.exec(stmt)
            return bool(res.first())

    def _compute_timed_out(m: Match) -> bool:
        now = datetime.now(timezone.utc)
        if getattr(m, "scheduled_time", None) is None:
            logger.warning(
                "Match %s has no scheduled_time; skipping timeout check.", m.id
            )
            return False
        try:
            return now > m.scheduled_time + timedelta(hours=12)
        except (TypeError, AttributeError) as e:
            logger.warning(
                "Could not compute timeout for match %s: %s",
                m.id,
                e,
            )
            return False

    if await _result_exists(match, session):
        logger.info(
            "Match %s result exists. Unscheduling '%s'.",
            match.id,
            job_id,
        )
        _remove_job_if_exists(job_id)
        return False

    if _compute_timed_out(match):
        logger.warning(
            "Job %s for match %s timed out; unscheduling.", job_id, match.id
        )
        _remove_job_if_exists(job_id)
        return False

    return True


def _extract_scores_from_pandascore(match_data: dict, match: Match) -> tuple:
    results = match_data.get("results", [])
    team1_score = 0
    team2_score = 0

    for result in results:
        team_id = result.get("team_id")
        score = result.get("score", 0)

        if team_id == match.team1_id:
            team1_score = score
        elif team_id == match.team2_id:
            team2_score = score

    return team1_score, team2_score


def _determine_winner_from_pandascore(
    match_data: dict, match: Match, team1_score: int, team2_score: int
) -> Optional[str]:
    winner_id = match_data.get("winner_id")
    if not winner_id:
        return None

    if winner_id == match.team1_id:
        return match.team1
    elif winner_id == match.team2_id:
        return match.team2

    if match_data.get("status") == "finished":
        if team1_score > team2_score:
            return match.team1
        elif team2_score > team1_score:
            return match.team2

    return None


async def _update_match_score(
    session, match: Match, current_score_str: str
) -> bool:
    logger.info(
        "New score for match %s: %s. Announcing update.",
        match.id,
        current_score_str,
    )
    match.last_announced_score = current_score_str
    session.add(match)
    await session.commit()
    try:
        setattr(session, "_committed", True)
    except Exception:
        pass
    await _notify_mid_series(match, current_score_str)
    return True


async def _process_pandascore_match_data(
    session, match: Match, match_data: dict, job_id: str
) -> bool:
    team1_score, team2_score = _extract_scores_from_pandascore(
        match_data, match
    )
    current_score_str = f"{team1_score}-{team2_score}"

    winner = _determine_winner_from_pandascore(
        match_data, match, team1_score, team2_score
    )

    if winner:
        committed = await _handle_winner(
            match, winner, current_score_str, job_id
        )
        return bool(committed)
    elif match.last_announced_score != current_score_str:
        committed = await _update_match_score(
            session, match, current_score_str
        )
        return bool(committed)
    else:
        logger.info(
            "Polling for match %s complete. No winner yet. Score: %s.",
            match.id,
            current_score_str,
        )
        return False


async def _persist_running_flag(session, match, pandascore_id: int) -> bool:
    """Ensure `match` is marked running and persist that change.

    Returns True when the running state was persisted, False on error or
    when no change was needed.
    """
    known = await get_known_running_matches()
    if pandascore_id in known:
        return False

    logger.info(
        "Match %s (%s vs %s) detected as running",
        match.id,
        match.team1,
        match.team2,
    )
    try:
        await add_known_running_match(pandascore_id)
    except Exception:
        logger.exception(
            "Failed to add pandascore_id %s to running set",
            pandascore_id,
        )
    match.status = "running"
    session.add(match)

    try:
        await session.commit()
        try:
            setattr(session, "_committed", True)
        except Exception:
            pass
        return True
    except Exception:
        logger.exception(
            "Failed to persist running status for match %s", match.id
        )
        try:
            await session.rollback()
        except Exception:
            logger.exception(
                "Failed to rollback after commit error for match %s",
                match.id,
            )
        return False


async def _process_in_proc_session(
    pandascore_id: int, match_data: dict
) -> bool:
    """Process match data in a fresh session. Returns True on success,
    False on error."""
    try:
        from src.db import get_async_session

        async with get_async_session() as proc_session:
            proc_match = await crud.get_match_by_pandascore_id(
                proc_session, pandascore_id
            )
            if not proc_match:
                logger.debug(
                    "Running match %s not found; skipping processing",
                    pandascore_id,
                )
                return False

            try:
                committed = await _process_pandascore_match_data(
                    proc_session,
                    proc_match,
                    match_data,
                    f"poll_match_{proc_match.id}",
                )
                if not committed:
                    await proc_session.commit()
                return True
            except Exception:
                logger.exception(
                    "Error processing running match %s (processing session)",
                    pandascore_id,
                )
                try:
                    await proc_session.rollback()
                except Exception:
                    logger.exception(
                        "Failed to rollback processing session for match %s",
                        pandascore_id,
                    )
                return False
    except Exception:
        logger.exception(
            "Unexpected error setting up processing session for match %s",
            pandascore_id,
        )
        return False


async def _process_running_match(session, match_data: dict) -> bool:
    pandascore_id = match_data.get("id")
    if not pandascore_id:
        return False

    match = await crud.get_match_by_pandascore_id(session, pandascore_id)
    if not match:
        logger.debug(
            "Running match %s not in database, skipping", pandascore_id
        )
        return False

    persisted = await _persist_running_flag(session, match, pandascore_id)
    if persisted:
        # We persisted running state in a separate transaction; process in
        # a new session so failures don't undo that change.
        return await _process_in_proc_session(pandascore_id, match_data)

    # No persisted running state; process using the provided session and
    # return whether processing committed that session.
    try:
        committed = await _process_pandascore_match_data(
            session, match, match_data, f"poll_match_{match.id}"
        )
        return bool(committed)
    except Exception:
        logger.exception("Error processing running match %s", pandascore_id)
        try:
            await session.rollback()
        except Exception:
            logger.exception(
                "Failed to rollback after processing error for match %s",
                pandascore_id,
            )
        return False


async def _handle_finished_pandascore_id(pandascore_id: int) -> None:
    try:
        match_data = await pandascore_client.fetch_match_by_id(pandascore_id)
        if not match_data or match_data.get("status") != "finished":
            return

        try:
            from src.db import get_async_session

            async with get_async_session() as session:
                match = await crud.get_match_by_pandascore_id(
                    session, pandascore_id
                )
                if not match:
                    return

                # Check if result exists without triggering lazy load
                stmt = select(Result).where(Result.match_id == match.id)
                res = await session.exec(stmt)
                if not res.first():
                    committed = await _process_pandascore_match_data(
                        session, match, match_data, f"poll_match_{match.id}"
                    )
                    if not committed:
                        await session.commit()
        except Exception:
            logger.exception(
                "Error processing finished match %s", pandascore_id
            )
    except Exception:
        logger.exception("Error fetching finished match %s", pandascore_id)

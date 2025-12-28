import logging
from datetime import datetime, timedelta, timezone
from src.db import get_async_session
from src.models import Match
from src.leaguepedia_client import leaguepedia_client
from src import crud
from src.notifications import send_result_notification, send_mid_series_update
from src.scheduler_instance import scheduler
from src import match_result_utils

logger = logging.getLogger(__name__)


def _remove_job_if_exists(job_id: str):
    """
    Helper function to safely remove a job from the scheduler.
    Logs a debug message if the job doesn't exist.
    """
    from apscheduler.jobstores.base import JobLookupError

    try:
        scheduler.remove_job(job_id)
    except JobLookupError:
        logger.debug("Job %s was already removed.", job_id)


async def _fetch_scoreboard_for_match(match: Match):
    """
    Fetches scoreboard data for the match's contest from
    Leaguepedia.

    Parameters:
        match (Match): Match whose contest must include a valid
            `leaguepedia_id`.

    Returns:
        The scoreboard data object returned by the Leaguepedia
            client for the contest.
    """
    logger.debug("Fetching scoreboard data for match %s", match.id)
    return await leaguepedia_client.get_scoreboard_data(
        match.contest.leaguepedia_id
    )


async def _handle_winner(
    match: Match,
    winner: str,
    current_score_str: str,
    job_id: str | None = None,
):
    """
    Handle a detected series winner by persisting the result,
    updating picks, notifying guilds, and unscheduling the poll job
    for the match.

    This function opens and manages its own database session. If
    `job_id` is not provided, the poll job id `poll_match_{match.id}`
    will be used to remove the scheduled polling job.
    """
    logger.info(
        "Series winner found for match %s: %s. Final Score: %s",
        match.id,
        winner,
        current_score_str,
    )

    # Use an internal session to persist the result and update picks.
    async with get_async_session() as session:
        result = await match_result_utils.save_result_and_update_picks(
            session, match, winner, current_score_str
        )
        await session.commit()
    logger.info("Saved result and updated picks for match %s.", match.id)

    # Notify using IDs so the notification handler can load fresh
    # objects within its own session and avoid detached-instance issues.
    await send_result_notification(match.id, result.id)

    if job_id is None:
        job_id = f"poll_match_{match.id}"
    logger.info("Unscheduling job %s for completed match.", job_id)
    _remove_job_if_exists(job_id)


async def _should_continue_polling(match: Match | None, job_id: str) -> bool:
    """
    Decides whether polling should continue for a match and
    unschedules the poll job when it should stop.

    Stops and removes the job when the match is missing, a result
    already exists, or the match is more than 12 hours past its
    scheduled time. The job identified by `job_id` will be
    unscheduled in those cases.

    Returns:
        `True` if polling should continue, `False` otherwise.
    """
    if not match or match.result:
        logger.info(
            "Match %s not found or result exists. Unscheduling '%s'.",
            getattr(match, "id", "<unknown>"),
            job_id,
        )
        _remove_job_if_exists(job_id)
        return False

    now = datetime.now(timezone.utc)
    try:
        timed_out = now > match.scheduled_time + timedelta(hours=12)
    except Exception:
        timed_out = False

    if timed_out:
        logger.warning(
            "Job '%s' for match %s timed out after 12 hours. Unscheduling.",
            job_id,
            match.id,
        )
        _remove_job_if_exists(job_id)
        return False

    return True


async def _update_match_score(session, match: Match, current_score_str: str):
    """
    Updates the match score in the database and sends a mid-series
    update notification.
    """
    logger.info(
        "New score for match %s: %s. Announcing update.",
        match.id,
        current_score_str,
    )
    match.last_announced_score = current_score_str
    session.add(match)
    await session.commit()
    await send_mid_series_update(match, current_score_str)


async def _process_match_results(
    session, match: Match, scoreboard_data: dict, job_id: str
):
    """
    Processes scoreboard data to determine the current score and
    winner, then handles updates or final results.
    """
    relevant_games = match_result_utils.filter_relevant_games_from_scoreboard(
        scoreboard_data, match
    )
    if not relevant_games:
        logger.info(
            "No relevant games found in scoreboard data for match %s.",
            match.id,
        )
        return

    team1_score, team2_score = match_result_utils.calculate_team_scores(
        relevant_games, match
    )
    winner = match_result_utils.determine_winner(
        team1_score, team2_score, match
    )
    current_score_str = f"{team1_score}-{team2_score}"

    if winner:
        await _handle_winner(match, winner, current_score_str, job_id)
    elif match.last_announced_score != current_score_str:
        await _update_match_score(session, match, current_score_str)
    else:
        logger.info(
            "Polling for match %s complete. No winner yet. Score: %s.",
            match.id,
            current_score_str,
        )


async def poll_live_match_job(match_db_id: int):
    """
    Polls the live scoreboard for a match, updates match state in
    the database, and broadcasts score updates or the final result.

    Given a match database ID, attempts to retrieve current
    scoreboard data for that match, determines the live series score
    and winner (if any), persists score and result changes, announces
    mid-series updates or final results to guilds, and unschedules
    polling when the match is finished or should stop (e.g., timed
    out or missing). The function performs no return value.

    Parameters:
        match_db_id (int): The database ID of the match to poll.
    """
    job_id = f"poll_match_{match_db_id}"
    logger.info("Polling for match ID %s (Job: %s)", match_db_id, job_id)

    async with get_async_session() as session:
        match = await crud.get_match_with_result_by_id(session, match_db_id)

        if not await _should_continue_polling(match, job_id):
            return

        scoreboard_data = await _fetch_scoreboard_for_match(match)
        if not scoreboard_data:
            logger.info(
                "No scoreboard data found for match %s. Will retry.", match.id
            )
            return

        await _process_match_results(session, match, scoreboard_data, job_id)

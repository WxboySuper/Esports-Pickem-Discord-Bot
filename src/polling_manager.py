import logging
from datetime import datetime, timedelta, timezone
from sqlmodel import select
from src.db import get_async_session
from src.models import Match, Result
from src.scheduler_instance import scheduler
from src.polling import poll_live_match_job

logger = logging.getLogger(__name__)


async def _get_matches_starting_soon(session):
    """
    Get the current UTC time and the Match records scheduled to start
    within the next 5 minutes that have no result.

    Parameters:
        session: A SQLModel/SQLAlchemy session used to query Match records.

    Returns:
        tuple: (now, matches) where `now` is the current UTC datetime and
            `matches` is a list of Match objects with `scheduled_time` >=
            `now`, < 5 minutes after `now`, and `result` is None.
    """
    now = datetime.now(timezone.utc)
    five_minutes_from_now = now + timedelta(minutes=5)
    stmt = (
        select(Match)
        .outerjoin(Result)
        .where(
            Match.scheduled_time >= now,
            Match.scheduled_time < five_minutes_from_now,
            Result.id.is_(None),
        )
    )
    matches = (await session.exec(stmt)).all()
    return now, matches


def _safe_get_jobs():
    """
    Fetch the current scheduled jobs from the scheduler.

    Returns:
        list: A list of scheduled job objects from the scheduler.
            Returns an empty list if the scheduler does not expose a
            `get_jobs` method or if job retrieval fails.
    """
    try:
        return scheduler.get_jobs()
    except AttributeError:
        logger.debug(
            "schedule_live_polling: scheduler.get_jobs() not available"
        )
        return []
    except Exception as e:
        logger.warning(
            "schedule_live_polling: failed to enumerate scheduler jobs: %s", e
        )
        return []


def _count_poll_jobs(jobs):
    """
    Count how many scheduler jobs are poll jobs for matches.

    Parameters:
        jobs (Iterable): An iterable of job-like objects; each object
            is expected to have an `id` attribute.

    Returns:
        int: Number of jobs whose `id` starts with "poll_match_".
            Returns 0 if an unexpected job object is encountered.
    """
    try:
        return sum(
            1 for j in jobs if getattr(j, "id", "").startswith("poll_match_")
        )
    except Exception:
        logger.debug(
            "schedule_live_polling: unexpected job object counting poll jobs"
        )
        return 0


def _schedule_poll_for_match(match):
    """
    Schedule a recurring poll job to monitor a live match if one is
    not already scheduled.

    Schedules a job named "poll_match_<match.id>" that calls
    poll_live_match_job(match.id) every 5 minutes with a 60-second
    misfire grace period. If a job with the same id already exists,
    no changes are made.

    Parameters:
        match: Match-like object with at least `id`, `team1`, and
            `team2` attributes used to name and log the job.
    """
    job_id = f"poll_match_{match.id}"
    if scheduler.get_job(job_id):
        logger.debug(
            "Job '%s' for match %s already exists. Skipping.", job_id, match.id
        )
        return

    logger.info(
        "Match %s (%s vs %s) is starting soon. Scheduling job '%s'.",
        match.id,
        match.team1,
        match.team2,
        job_id,
    )
    scheduler.add_job(
        poll_live_match_job,
        "interval",
        minutes=5,
        id=job_id,
        args=[match.id],
        misfire_grace_time=60,
        replace_existing=True,
    )


async def schedule_live_polling():
    """
    Schedule recurring live-polling jobs for matches starting within the
    next 5 minutes.

    Scans the database for matches with no result that are scheduled to
    begin within the upcoming 5-minute window, logs candidate and
    currently scheduled poll job counts, and schedules a recurring poll
    job for each candidate match. Does not return a value.
    """
    logger.debug("Running schedule_live_polling job...")

    async with get_async_session() as session:
        _, matches_starting_soon = await _get_matches_starting_soon(session)

        if matches_starting_soon:
            times = [
                getattr(m, "scheduled_time", None)
                for m in matches_starting_soon
            ]
            times = [t for t in times if t is not None]
            earliest = min(times) if times else None
            logger.info(
                "schedule_live_polling: found %d candidate(s); "
                "earliest scheduled_time=%s",
                len(matches_starting_soon),
                earliest,
            )
        else:
            logger.info(
                "schedule_live_polling: found 0 candidates in "
                "the 5-minute window."
            )

        jobs = _safe_get_jobs()
        poll_jobs_count = _count_poll_jobs(jobs)
        logger.info(
            "schedule_live_polling: %d poll_match jobs in scheduler",
            poll_jobs_count,
        )

        if not matches_starting_soon:
            return

        for match in matches_starting_soon:
            _schedule_poll_for_match(match)

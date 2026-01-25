import logging
import asyncio
from datetime import datetime, timedelta, timezone
from src.config import REMINDER_MINUTES
from src.models import Match
from src.scheduler_instance import scheduler
from src.notification_batcher import batcher

logger = logging.getLogger(__name__)


async def schedule_reminders(match: Match):
    """
    Schedules 30-minute and 5-minute reminders for a given match.
    Cancels any existing reminders for the match before scheduling new ones.
    """
    logger.info("Scheduling reminders for match %s", match.id)
    now = datetime.now(timezone.utc)

    # Use module-level helpers defined below
    minutes_list = _normalize_minutes(REMINDER_MINUTES)
    for minutes_int in minutes_list:
        reminder_time = match.scheduled_time - timedelta(minutes=minutes_int)
        if now < reminder_time:
            _schedule(minutes_int, reminder_time, match)
            continue

        if _should_send_immediately(minutes_int, minutes_list, now, match):
            _schedule(minutes_int, now, match)

    # Yield to event loop to prevent heartbeat blocking during bulk scheduling
    await asyncio.sleep(0)


def _normalize_minutes(raw):
    # Delegate parsing and validation to small helpers to keep complexity low
    safe_default = [5, 30, 1440]
    minutes = _parse_minutes_from_raw(raw)
    validated, err = _validate_minutes(minutes)
    if validated is None:
        logger.error(
            "Invalid REMINDER_MINUTES config (%r); using safe default %r",
            raw,
            safe_default,
            exc_info=err,
        )
        return safe_default
    return validated


def _parse_minutes_from_raw(raw) -> list:
    """Parse the raw config into a list of values suitable for int conversion.

    Returns an empty list for None or un-iterable inputs.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    try:
        # Try to consume an iterable (e.g., list of ints or strings)
        return list(raw)
    except TypeError:
        return []


def _validate_minutes(
    minutes_list: list,
) -> tuple[list[int] | None, Exception | None]:
    """Convert items to ints, ensure positive, deduplicate, and sort.

    Returns `(list, None)` on success or `(None, Exception)` on failure so the
    caller can log the original exception context without raising here.
    """
    if not minutes_list:
        return None, ValueError(
            "no reminder minutes configured",
        )
    converted: list[int] = []
    for item in minutes_list:
        try:
            m = int(item)
        except Exception as exc:
            return None, exc
        if m <= 0:
            return None, ValueError(
                "reminder minutes must be positive non-zero integers",
            )
        converted.append(m)
    return sorted(set(converted)), None


def _should_send_immediately(
    minutes_int: int, minutes_list: list[int], now_dt: datetime, match: Match
) -> bool:
    """Return True if this reminder should be sent immediately.

    If a smaller (closer) reminder is configured, only send this larger
    reminder immediately if the closer reminder is still in the future.
    If there is no smaller reminder, fall back to sending if the match
    hasn't started.
    """
    smaller = max(
        (m for m in minutes_list if m < minutes_int),
        default=None,
    )
    if smaller is None:
        return now_dt < match.scheduled_time
    smaller_time = match.scheduled_time - timedelta(minutes=smaller)
    return now_dt < smaller_time


def _schedule(job_minutes: int, run_dt: datetime, match: Match) -> None:
    """Schedule a single reminder job with a stable id and replace_existing.

    This uses the module-level `scheduler` which tests may patch via
    `patch("src.reminders.scheduler", mock_scheduler)`.
    """
    job_id = f"reminder_{job_minutes}_{match.id}"
    logger.info(
        "Scheduling %s-minute reminder for match %s (run=%s)",
        job_minutes,
        match.id,
        run_dt,
    )
    scheduler.add_job(
        send_reminder,
        "date",
        id=job_id,
        run_date=run_dt,
        args=[match.id, job_minutes],
        replace_existing=True,
    )


async def send_reminder(match_id: int, minutes: int):
    """
    Sends a reminder embed about a scheduled match to all guilds.
    Delegates to NotificationBatcher to allow grouping.

    Parameters:
        match_id (int): Database ID of the match to remind about.
        minutes (int): Number of minutes before the match.
    """
    logger.info("Queuing %s-minute reminder for match %s", minutes, match_id)
    await batcher.add_reminder(match_id, minutes)

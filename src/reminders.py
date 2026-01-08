import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from src.config import REMINDER_MINUTES
import discord
from src.db import get_async_session
from src.models import Match
from src.bot_instance import get_bot_instance
from src.scheduler_instance import scheduler
from src.match_result_utils import fetch_teams
from src.notifications import broadcast_embed_to_guilds

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
    safe_default = [5, 30]
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


def _validate_minutes(minutes_list: list) -> tuple[list[int] | None, Exception | None]:
    """Convert items to ints, ensure positive, deduplicate, and sort.

    Returns `(list, None)` on success or `(None, Exception)` on failure so the
    caller can log the original exception context without raising here.
    """
    if not minutes_list:
        return None, ValueError("no reminder minutes configured")
    converted: list[int] = []
    for item in minutes_list:
        try:
            m = int(item)
        except Exception as exc:
            return None, exc
        if m <= 0:
            return None, ValueError("reminder minutes must be positive non-zero integers")
        converted.append(m)
    return sorted(set(converted)), None


def _should_send_immediately(minutes_int: int, minutes_list: list[int], now_dt: datetime, match: Match) -> bool:
    """Return True if this reminder should be sent immediately.

    If a smaller (closer) reminder is configured, only send this larger
    reminder immediately if the closer reminder is still in the future.
    If there is no smaller reminder, fall back to sending if the match
    hasn't started.
    """
    smaller = max((m for m in minutes_list if m < minutes_int), default=None)
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
    logger.info("Scheduling %s-minute reminder for match %s (run=%s)", job_minutes, match.id, run_dt)
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

    Parameters:
        match_id (int): Database ID of the match to remind about.
        minutes (int): Number of minutes before the match (e.g., 5 or
            30) used in the embed text.
    """
    logger.info(
        "Broadcasting %s-minute reminder for match %s to all guilds.",
        minutes,
        match_id,
    )
    bot = get_bot_instance()
    if not bot:
        logger.error(
            "Bot instance not available for %s-minute reminder: match %s",
            minutes,
            match_id,
        )
        return

    async with get_async_session() as session:
        match = await session.get(Match, match_id)
        if not match:
            logger.error("Match %s not found for reminder.", match_id)
            return

        logger.debug("Fetching team data for match %s", match_id)
        team1, team2 = await fetch_teams(session, match)

        embed = _create_reminder_embed(match, team1, team2, minutes)
        await broadcast_embed_to_guilds(
            bot, embed, f"{minutes}-minute reminder for match {match_id}"
        )


def _create_reminder_embed(
    match: Match, team1: Any, team2: Any, minutes: int
) -> discord.Embed:
    """
    Builds a Discord embed reminding users of an upcoming match.

    Parameters:
        match (Match): Match instance whose teams and scheduled_time
            are shown in the embed.
        team1 (Team | None): Optional team object for team1; used to
            select a thumbnail if it provides an image_url.
        team2 (Team | None): Optional team object for team2; used to
            select a thumbnail if team1 has no image.
        minutes (int): Minutes before the match (commonly 5 or 30)
            that determines the embed's title, description, and color.

    Returns:
        discord.Embed: A ready-to-send embed containing the match
            reminder, scheduled time field, and optional thumbnail.
    """
    scheduled_ts = int(match.scheduled_time.timestamp())

    if minutes == 5:
        title = "🔴 Match Starting Soon!"
        description = (
            f"**{match.team1}** vs **{match.team2}** is starting "
            f"<t:{scheduled_ts}:R>! Last chance to lock in picks."
        )
        color = discord.Color.red()
    else:
        title = "⚔️ Upcoming Match Reminder"
        description = (
            f"Get your picks in! **{match.team1}** vs "
            f"**{match.team2}** starts <t:{scheduled_ts}:R>."
        )
        color = discord.Color.blue()

    embed = discord.Embed(title=title, description=description, color=color)

    thumbnail_url = None
    if team1 and getattr(team1, "image_url", None):
        thumbnail_url = team1.image_url
    elif team2 and getattr(team2, "image_url", None):
        thumbnail_url = team2.image_url
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    embed.add_field(
        name="Scheduled Time", value=f"<t:{scheduled_ts}:F>", inline=False
    )
    embed.set_footer(text="Use the /picks command to make your predictions!")
    return embed

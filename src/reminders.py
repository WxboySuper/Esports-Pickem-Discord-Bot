import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import discord
from apscheduler.jobstores.base import JobLookupError
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
    job_id_30 = f"reminder_30_{match.id}"
    job_id_5 = f"reminder_5_{match.id}"

    # Cancel existing jobs to prevent duplicates
    try:
        scheduler.remove_job(job_id_30)
    except JobLookupError:
        pass  # Job doesn't exist, no need to remove
    try:
        scheduler.remove_job(job_id_5)
    except JobLookupError:
        pass
    reminder_time_30 = match.scheduled_time - timedelta(minutes=30)
    reminder_time_5 = match.scheduled_time - timedelta(minutes=5)

    # Schedule 5-minute reminder if it's not already past
    if now < reminder_time_5:
        logger.info("Scheduling 5-minute reminder for match %s", match.id)
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_5,
            run_date=reminder_time_5,
            args=[match.id, 5],
        )
    # If 5-min reminder is late, but match hasn't started, send immediately
    elif now < match.scheduled_time:
        logger.info(
            "5-minute reminder for match %s is late, sending now.", match.id
        )
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_5,
            run_date=now,
            args=[match.id, 5],
        )

    # Schedule 30-minute reminder
    if now < reminder_time_30:
        logger.info("Scheduling 30-minute reminder for match %s", match.id)
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_30,
            run_date=reminder_time_30,
            args=[match.id, 30],
        )
    # If 30-min is late, but 5-min is still in the future, send 30-min now
    elif now < reminder_time_5:
        logger.info(
            "30-minute reminder for match %s is late, sending now.", match.id
        )
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_30,
            run_date=now,
            args=[match.id, 30],
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

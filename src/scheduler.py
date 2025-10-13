import logging
import aiohttp
import discord
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import JobLookupError
from sqlmodel import select
from src.db import get_async_session
from src.models import Match, Result, Pick, Team
from src.leaguepedia_client import LeaguepediaClient
from src.announcements import send_announcement
from src.config import ANNOUNCEMENT_GUILD_ID
from src.db import DATABASE_URL
from src.bot_instance import get_bot_instance
from src.commands.sync_leaguepedia import perform_leaguepedia_sync

logger = logging.getLogger(__name__)

jobstores = {"default": SQLAlchemyJobStore(url=DATABASE_URL)}
scheduler = AsyncIOScheduler(jobstores=jobstores)


async def schedule_match_reminders(match: Match):
    """
    Schedules 30-minute and 5-minute reminders for a given match.
    Cancels any existing reminders for the match before scheduling new ones.
    """
    logger.info(f"Scheduling reminders for match {match.id}")
    now = datetime.now(timezone.utc)
    guild_id = ANNOUNCEMENT_GUILD_ID
    logger.info(f"Using guild_id: {guild_id}")
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

    # Calculate reminder times
    reminder_time_30 = match.scheduled_time - timedelta(minutes=30)
    reminder_time_5 = match.scheduled_time - timedelta(minutes=5)

    # Schedule 5-minute reminder if it's not already past
    if now < reminder_time_5:
        logger.info(f"Scheduling 5-minute reminder for match {match.id}")
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_5,
            run_date=reminder_time_5,
            args=[guild_id, match.id, 5],
        )
    # If 5-min reminder is late, but match hasn't started, send immediately
    elif now < match.scheduled_time:
        logger.info(
            f"5-minute reminder time for match {match.id} is in the past. "
            "Scheduling to run immediately."
        )
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_5,
            run_date=now,
            args=[guild_id, match.id, 5],
        )

    # Schedule 30-minute reminder ONLY IF the 5-minute one was not sent immediately
    if now < reminder_time_30:
        logger.info(f"Scheduling 30-minute reminder for match {match.id}")
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_30,
            run_date=reminder_time_30,
            args=[guild_id, match.id, 30],
        )
    # If 30-min is late, but 5-min is still in the future, send 30-min now
    elif now < reminder_time_5:
        logger.info(
            f"30-minute reminder time for match {match.id} is in the past. "
            "Scheduling to run immediately."
        )
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_30,
            run_date=now,
            args=[guild_id, match.id, 30],
        )


async def poll_live_match_job(match_db_id: int, guild_id: int):
    """
    Polls a specific match for live updates/results. If a winner is found,
    it saves the result, sends a notification, and removes itself from the
    scheduler.
    """
    job_id = f"poll_match_{match_db_id}"
    logger.info(f"Running job '{job_id}': Polling for match ID {match_db_id}")

    async with get_async_session() as session:
        match = await session.get(Match, match_db_id)
        if not match or match.result:
            logger.info(
                f"Match {match_db_id} not found or result already exists. "
                f"Unscheduling job '{job_id}'."
            )
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                logger.warning(
                    f"Could not find job '{job_id}' to remove. "
                    "It might have been removed already."
                )
            return

        async with aiohttp.ClientSession() as http_session:
            client = LeaguepediaClient(http_session)
            result_data = await client.get_match_by_id(match.leaguepedia_id)
            winner = result_data.get("Winner")

            if winner:
                logger.info(
                    f"Result found for match {match.id}: Winner is {winner}. "
                    f"Unscheduling job '{job_id}'."
                )
                result = Result(
                    match_id=match.id,
                    winner=winner,
                    score=(
                        f"{result_data.get('Team1Score')} - "
                        f"{result_data.get('Team2Score')}"
                    ),
                )
                session.add(result)
                await session.commit()
                await send_result_notification(guild_id, match, result)

                try:
                    scheduler.remove_job(job_id)
                except JobLookupError:
                    logger.warning(
                        f"Could not find job '{job_id}' to remove. "
                        "It might have been removed already."
                    )


async def send_reminder(guild_id: int, match_id: int, minutes: int):
    """Sends a rich, informative embed as a match reminder."""
    bot = get_bot_instance()
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error(f"Guild {guild_id} not found.")
        return

    async with get_async_session() as session:
        match = await session.get(Match, match_id)
        if not match:
            logger.error(f"Match {match_id} not found for reminder.")
            return

        # Fetch team data to get image URLs
        team1_stmt = select(Team).where(Team.name == match.team1)
        team2_stmt = select(Team).where(Team.name == match.team2)
        team1 = (await session.exec(team1_stmt)).first()
        team2 = (await session.exec(team2_stmt)).first()

        scheduled_ts = int(match.scheduled_time.timestamp())

        if minutes == 5:
            title = "🔴 Match Starting Soon!"
            description = (
                f"**{match.team1}** vs **{match.team2}** is starting "
                f"<t:{scheduled_ts}:R>! Last chance to lock in picks."
            )
            color = discord.Color.red()
        else:  # 30-minute reminder
            title = "⚔️ Upcoming Match Reminder"
            description = (
                f"Get your picks in! **{match.team1}** vs "
                f"**{match.team2}** starts <t:{scheduled_ts}:R>."
            )
            color = discord.Color.blue()

        embed = discord.Embed(
            title=title, description=description, color=color
        )

        thumbnail_url = None
        if team1 and team1.image_url:
            thumbnail_url = team1.image_url
        elif team2 and team2.image_url:
            thumbnail_url = team2.image_url
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        embed.add_field(
            name="Scheduled Time",
            value=f"<t:{scheduled_ts}:F>",
            inline=False,
        )
        embed.set_footer(
            text="Use the /picks command to make your predictions!"
        )

        await send_announcement(guild, embed)


async def send_result_notification(
    guild_id: int, match: Match, result: Result
):
    bot = get_bot_instance()
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error(f"Guild {guild_id} not found.")
        return
    async with get_async_session() as session:
        statement = select(Pick).where(Pick.match_id == match.id)
        db_result = await session.exec(statement)
        picks = db_result.all()
        total_picks = len(picks)
        correct_picks = len(
            [p for p in picks if p.chosen_team == result.winner]
        )
        correct_percentage = (
            (correct_picks / total_picks) * 100 if total_picks > 0 else 0
        )
        opponent = match.team2 if result.winner == match.team1 else match.team1
        embed = discord.Embed(
            title="Match Result",
            description=f"{result.winner} won against {opponent}!",
            color=discord.Color.green(),
        )
        winner_picks_str = (
            f"{correct_percentage:.2f}% of users "
            "correctly picked the winner."
        )
        embed.add_field(
            name="Picks",
            value=winner_picks_str,
        )
        await send_announcement(guild, embed)


async def schedule_live_polling(guild_id: int):
    """
    Checks for matches starting soon and schedules a dedicated polling job
    for each one.
    """
    async with get_async_session() as session:
        now = datetime.now(timezone.utc)
        one_minute_from_now = now + timedelta(minutes=1)

        statement = select(Match).where(
            Match.scheduled_time >= now,
            Match.scheduled_time < one_minute_from_now,
            Match.result == None,  # noqa: E711
        )
        result = await session.exec(statement)
        matches_starting_soon = result.all()

        for match in matches_starting_soon:
            job_id = f"poll_match_{match.id}"
            if not scheduler.get_job(job_id):
                logger.info(
                    f"Match {match.id} is starting soon. "
                    f"Scheduling job '{job_id}' to poll for results."
                )
                scheduler.add_job(
                    poll_live_match_job,
                    "interval",
                    minutes=5,
                    id=job_id,
                    args=[match.id, guild_id],
                )


def start_scheduler():
    if not scheduler.running:
        # Schedule the main Leaguepedia sync
        scheduler.add_job(
            perform_leaguepedia_sync,
            "interval",
            hours=6,
            id="sync_all_tournaments_job",
        )

        # Schedule the orchestrator job to run every minute
        scheduler.add_job(
            schedule_live_polling,
            "interval",
            minutes=1,
            args=[ANNOUNCEMENT_GUILD_ID],
        )

        scheduler.start()
        logger.info("Scheduler started.")

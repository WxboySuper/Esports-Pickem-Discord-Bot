import logging
import discord
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import JobLookupError
from sqlmodel import select
from src.db import get_async_session
from src.models import Match, Result, Pick, Team
from src.leaguepedia_client import leaguepedia_client
from src import crud
from src.announcements import send_announcement
from src.config import ANNOUNCEMENT_GUILD_ID
from src.db import DATABASE_URL
from src.bot_instance import get_bot_instance

logger = logging.getLogger(__name__)

jobstores = {"default": SQLAlchemyJobStore(url=DATABASE_URL)}
scheduler = AsyncIOScheduler(jobstores=jobstores)


async def schedule_reminders(match: Match):
    """
    Schedules 30-minute and 5-minute reminders for a given match.
    Cancels any existing reminders for the match before scheduling new ones.
    """
    logger.info("Scheduling reminders for match %s", match.id)
    now = datetime.now(timezone.utc)
    guild_id = ANNOUNCEMENT_GUILD_ID
    logger.info("Using guild_id: %s", guild_id)
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
        logger.info("Scheduling 5-minute reminder for match %s", match.id)
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
            "5-minute reminder for match %s is late, sending now.", match.id
        )
        scheduler.add_job(
            send_reminder,
            "date",
            id=job_id_5,
            run_date=now,
            args=[guild_id, match.id, 5],
        )

    # Schedule 30-minute reminder
    if now < reminder_time_30:
        logger.info("Scheduling 30-minute reminder for match %s", match.id)
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
            "30-minute reminder for match %s is late, sending now.", match.id
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
    Polls a specific match for live updates/results using scoreboard data.
    If a winner is found, it saves the result, sends a notification, and
    removes itself from the scheduler. Includes a timeout.
    """
    job_id = f"poll_match_{match_db_id}"
    logger.info("Polling for match ID %s (Job: %s)", match_db_id, job_id)

    async with get_async_session() as session:
        match = await crud.get_match_with_result_by_id(session, match_db_id)

        if not match or match.result:
            logger.info(
                "Match %s not found or result exists. Unscheduling '%s'.",
                match_db_id,
                job_id,
            )
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                pass
            return

        now = datetime.now(timezone.utc)
        if now > match.scheduled_time + timedelta(hours=12):
            logger.warning(
                "Job '%s' for match %s timed out. Unscheduling.",
                job_id,
                match.id,
            )
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                pass
            return

        scoreboard_data = await leaguepedia_client.get_scoreboard_data(
            match.contest.leaguepedia_id
        )

        if not scoreboard_data:
            logger.info("No scoreboard data for match %s.", match.id)
            return

        team1_score = 0
        team2_score = 0
        for game in scoreboard_data:
            if game.get("Winner") == "1":
                team1_score += 1
            elif game.get("Winner") == "2":
                team2_score += 1

        # Check if the series is over
        games_to_win = (match.best_of // 2) + 1
        winner = None
        if team1_score >= games_to_win:
            winner = match.team1
        elif team2_score >= games_to_win:
            winner = match.team2

        current_score_str = f"{team1_score}-{team2_score}"
        if winner:
            logger.info(
                "Series winner found for match %s: %s. Final Score: %s",
                match.id,
                winner,
                current_score_str,
            )
            result = Result(
                match_id=match.id,
                winner=winner,
                score=current_score_str,
            )
            session.add(result)
            await session.commit()
            await send_result_notification(guild_id, match, result)

            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                pass
        elif match.last_announced_score != current_score_str:
            logger.info(
                "New score for match %s: %s. Announcing update.",
                match.id,
                current_score_str,
            )
            match.last_announced_score = current_score_str
            session.add(match)
            await session.commit()
            await send_mid_series_update(
                guild_id, match, current_score_str
            )


async def send_reminder(guild_id: int, match_id: int, minutes: int):
    """Sends a rich, informative embed as a match reminder."""
    bot = get_bot_instance()
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error("Guild %s not found for reminder.", guild_id)
        return

    async with get_async_session() as session:
        match = await session.get(Match, match_id)
        if not match:
            logger.error("Match %s not found for reminder.", match_id)
            return

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
            name="Scheduled Time", value=f"<t:{scheduled_ts}:F>", inline=False
        )
        embed.set_footer(
            text="Use the /picks command to make your predictions!"
        )

        await send_announcement(guild, embed)


async def send_result_notification(
    guild_id: int, match: Match, result: Result
):
    """Sends a rich, detailed embed with match results."""
    bot = get_bot_instance()
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error("Guild %s not found for result notification.", guild_id)
        return

    async with get_async_session() as session:
        team1_stmt = select(Team).where(Team.name == match.team1)
        team2_stmt = select(Team).where(Team.name == match.team2)
        team1 = (await session.exec(team1_stmt)).first()
        team2 = (await session.exec(team2_stmt)).first()

        winner_team_obj = team1 if result.winner == match.team1 else team2

        statement = select(Pick).where(Pick.match_id == match.id)
        picks = (await session.exec(statement)).all()
        total_picks = len(picks)
        correct_picks = len(
            [p for p in picks if p.chosen_team == result.winner]
        )
        correct_percentage = (
            (correct_picks / total_picks) * 100 if total_picks > 0 else 0
        )

        opponent = match.team2 if result.winner == match.team1 else match.team1
        title = f"🏆 Match Results: {match.team1} vs {match.team2}"
        description = (
            f"**{result.winner}** emerges victorious over **{opponent}** "
            f"with a final score of **{result.score}**."
        )
        embed = discord.Embed(
            title=title, description=description, color=discord.Color.gold()
        )

        if winner_team_obj and winner_team_obj.image_url:
            embed.set_thumbnail(url=winner_team_obj.image_url)

        if total_picks > 0:
            picks_value = (
                f"**{correct_picks}** of **{total_picks}** users "
                f"({correct_percentage:.2f}%) correctly picked the winner."
            )
        else:
            picks_value = "No picks were made for this match."

        embed.add_field(
            name="📊 Pick'em Stats", value=picks_value, inline=False
        )
        embed.set_footer(text=f"Leaguepedia Match ID: {match.leaguepedia_id}")
        embed.timestamp = datetime.now(timezone.utc)

        await send_announcement(guild, embed)


async def send_mid_series_update(
    guild_id: int, match: Match, score: str
):
    """Sends a Discord embed with a mid-series score update."""
    bot = get_bot_instance()
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error(
            "Guild %s not found for mid-series update.", guild_id
        )
        return

    title = f"Live Update: {match.team1} vs {match.team2}"
    description = (
        f"The score is now **{score}** in this best of {match.best_of} series."
    )
    embed = discord.Embed(
        title=title, description=description, color=discord.Color.orange()
    )
    embed.set_footer(text=f"Match ID: {match.id}")
    embed.timestamp = datetime.now(timezone.utc)

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
        matches_starting_soon = (await session.exec(statement)).all()

        for match in matches_starting_soon:
            job_id = f"poll_match_{match.id}"
            if not scheduler.get_job(job_id):
                logger.info(
                    "Match %s is starting soon. Scheduling job '%s'.",
                    match.id,
                    job_id,
                )
                scheduler.add_job(
                    poll_live_match_job,
                    "interval",
                    minutes=5,
                    id=job_id,
                    args=[match.id, guild_id],
                    misfire_grace_time=60,
                )


def start_scheduler():
    # Local import to avoid circular dependency
    from src.commands.sync_leaguepedia import perform_leaguepedia_sync

    if not scheduler.running:
        scheduler.add_job(
            perform_leaguepedia_sync,
            "interval",
            hours=6,
            id="sync_all_tournaments_job",
            replace_existing=True,
        )
        scheduler.add_job(
            schedule_live_polling,
            "interval",
            minutes=1,
            id="schedule_live_polling_job",
            args=[ANNOUNCEMENT_GUILD_ID],
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started.")

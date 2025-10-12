import logging
import discord
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlmodel import select
from sqlalchemy.orm import selectinload
from src.db import get_async_session
from src.models import Match, Result, Pick
from src.leaguepedia import get_match_results
from src.announcements import send_announcement
from src.config import ANNOUNCEMENT_GUILD_ID
from src.db import DATABASE_URL
from src.bot_instance import get_bot_instance

logger = logging.getLogger(__name__)

jobstores = {"default": SQLAlchemyJobStore(url=DATABASE_URL)}
scheduler = AsyncIOScheduler(jobstores=jobstores)


async def schedule_reminders(guild_id: int):
    async with get_async_session() as session:
        now = datetime.now(timezone.utc)

        # Schedule 30-minute reminders
        thirty_minutes_from_now = now + timedelta(minutes=30)
        thirty_five_minutes_from_now = now + timedelta(minutes=35)

        statement = select(Match).where(
            Match.scheduled_time > thirty_minutes_from_now,
            Match.scheduled_time <= thirty_five_minutes_from_now,
        )
        result = await session.exec(statement)
        matches_30_min = result.all()

        for match in matches_30_min:
            job_id = f"reminder_30_{match.id}"
            if not scheduler.get_job(job_id):
                run_date = match.scheduled_time - timedelta(minutes=30)
                scheduler.add_job(
                    send_reminder,
                    "date",
                    id=job_id,
                    run_date=run_date,
                    args=[guild_id, match.id, 30],
                )

        # Schedule 5-minute reminders
        five_minutes_from_now = now + timedelta(minutes=5)
        ten_minutes_from_now = now + timedelta(minutes=10)

        statement = select(Match).where(
            Match.scheduled_time > five_minutes_from_now,
            Match.scheduled_time <= ten_minutes_from_now,
        )
        result = await session.exec(statement)
        matches_5_min = result.all()

        for match in matches_5_min:
            job_id = f"reminder_5_{match.id}"
            if not scheduler.get_job(job_id):
                run_date = match.scheduled_time - timedelta(minutes=5)
                scheduler.add_job(
                    send_reminder,
                    "date",
                    id=job_id,
                    run_date=run_date,
                    args=[guild_id, match.id, 5],
                )


async def poll_for_results(guild_id: int):
    bot = get_bot_instance()
    async with get_async_session() as session:
        statement = select(Match).options(
            selectinload(Match.result), selectinload(Match.contest)
        )
        result = await session.exec(statement)
        matches = result.all()
        for match in matches:
            if not match.result:
                results = await get_match_results(
                    bot.session, match.contest.name, match.team1, match.team2
                )
                if results and results[0].get("winner"):
                    result = Result(
                        match_id=match.id, winner=results[0].get("winner")
                    )
                    session.add(result)
                    await session.commit()
                    await send_result_notification(guild_id, match, result)


async def send_reminder(guild_id: int, match_id: int, minutes: int):
    bot = get_bot_instance()
    guild = bot.get_guild(guild_id)
    if not guild:
        logger.error(f"Guild {guild_id} not found.")
        return
    async with get_async_session() as session:
        match = await session.get(Match, match_id)
        embed = discord.Embed(
            title="Match Reminder",
            description=(
                f"{match.team1} vs {match.team2} is starting in {minutes} "
                "minutes!"
            ),
            color=discord.Color.blue(),
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


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            schedule_reminders,
            "interval",
            minutes=15,
            args=[ANNOUNCEMENT_GUILD_ID],
        )
        scheduler.add_job(
            poll_for_results,
            "interval",
            minutes=5,
            args=[ANNOUNCEMENT_GUILD_ID],
        )
        scheduler.start()
        logger.info("Scheduler started.")

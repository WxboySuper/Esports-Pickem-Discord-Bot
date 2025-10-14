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


async def poll_live_match_job(match_db_id: int):
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
                logger.debug("Job %s was already removed.", job_id)
            return

        now = datetime.now(timezone.utc)
        if now > match.scheduled_time + timedelta(hours=12):
            logger.warning(
                "Job '%s' for match %s timed out after 12 hours. "
                "Unscheduling.",
                job_id,
                match.id,
            )
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                logger.debug("Job %s was already removed.", job_id)
            return

        logger.debug(f"Fetching scoreboard data for match {match.id}")
        scoreboard_data = await leaguepedia_client.get_scoreboard_data(
            match.contest.leaguepedia_id
        )

        if not scoreboard_data:
            logger.info(
                "No scoreboard data found for match %s. Will retry.",
                match.id,
            )
            return

        # Filter for games relevant to this specific match
        match_teams = {match.team1, match.team2}
        relevant_games = [
            g
            for g in scoreboard_data
            if {g.get("Team1"), g.get("Team2")} == match_teams
        ]

        if not relevant_games:
            logger.info(
                "No relevant games found in scoreboard data for match %s.",
                match.id,
            )
            return

        logger.debug(
            f"Found {len(relevant_games)} relevant games for match {match.id}."
        )

        team1_score = 0
        team2_score = 0
        for game in relevant_games:
            winner_id = game.get("Winner")
            if not winner_id:
                continue

            # Determine which team in the game corresponds to match.team1
            if game.get("Team1") == match.team1:
                if winner_id == "1":
                    team1_score += 1
                elif winner_id == "2":
                    team2_score += 1
            # Handle case where teams are swapped in the data
            elif game.get("Team1") == match.team2:
                if winner_id == "1":
                    team2_score += 1
                elif winner_id == "2":
                    team1_score += 1

        games_to_win = (match.best_of // 2) + 1
        winner = None
        if team1_score >= games_to_win:
            winner = match.team1
        elif team2_score >= games_to_win:
            winner = match.team2

        current_score_str = f"{team1_score}-{team2_score}"
        logger.debug(
            f"Match {match.id} score: {current_score_str}. "
            f"Games to win: {games_to_win}. "
            f"Last announced: {match.last_announced_score}"
        )

        if winner:
            logger.info(
                "Series winner found for match %s: %s. Final Score: %s",
                match.id,
                winner,
                current_score_str,
            )
            # All database updates for a match result are in one transaction
            result = Result(
                match_id=match.id,
                winner=winner,
                score=current_score_str,
            )
            session.add(result)

            # Update picks
            logger.info(f"Updating picks for match {match.id}")
            statement = select(Pick).where(Pick.match_id == match.id)
            result_proxy = await session.exec(statement)
            picks_to_update = result_proxy.all()
            updated_count = 0
            for pick in picks_to_update:
                pick.is_correct = pick.chosen_team == winner
                session.add(pick)
                updated_count += 1
            logger.info(
                f"Updated {updated_count} picks for match {match.id}."
            )

            await session.commit()
            logger.info(f"Saved result and updated picks for match {match.id}.")

            # Send notifications only after successful commit
            await send_result_notification(match, result)

            logger.info(f"Unscheduling job '{job_id}' for completed match.")
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                logger.debug("Job %s was already removed.", job_id)

        elif match.last_announced_score != current_score_str:
            logger.info(
                "New score for match %s: %s. Announcing update.",
                match.id,
                current_score_str,
            )
            match.last_announced_score = current_score_str
            session.add(match)
            await session.commit()
            await send_mid_series_update(match, current_score_str)
        else:
            logger.info(
                "Polling for match %s complete. No winner yet. "
                "Current score: %s.",
                match.id,
                current_score_str,
            )


async def send_reminder(match_id: int, minutes: int):
    """Sends a rich, informative embed as a match reminder to all guilds."""
    logger.info(
        f"Broadcasting {minutes}-minute reminder for match {match_id} to all guilds."
    )
    bot = get_bot_instance()

    async with get_async_session() as session:
        match = await session.get(Match, match_id)
        if not match:
            logger.error("Match %s not found for reminder.", match_id)
            return

        logger.debug(f"Fetching team data for match {match_id}")
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

        for guild in bot.guilds:
            try:
                await send_announcement(guild, embed)
                logger.info(
                    f"Sent {minutes}-minute reminder for match {match_id} to guild {guild.id}."
                )
            except Exception as e:
                logger.error(
                    f"Failed to send reminder for match {match_id} to guild {guild.id}: {e}"
                )


async def send_result_notification(match: Match, result: Result):
    """Sends a rich, detailed embed with match results to all guilds."""
    logger.info(
        f"Broadcasting result notification for match {match.id} to all guilds."
    )
    bot = get_bot_instance()

    async with get_async_session() as session:
        logger.debug(f"Fetching teams and picks for match {match.id}")
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

        for guild in bot.guilds:
            try:
                await send_announcement(guild, embed)
                logger.info(
                    f"Sent result notification for match {match.id} to guild {guild.id}."
                )
            except Exception as e:
                logger.error(
                    f"Failed to send result notification for match {match.id} to guild {guild.id}: {e}"
                )


async def send_mid_series_update(match: Match, score: str):
    """Sends a Discord embed with a mid-series score update to all guilds."""
    logger.info(
        f"Broadcasting mid-series update for match {match.id} (score: {score}) to all guilds."
    )
    bot = get_bot_instance()

    title = f"Live Update: {match.team1} vs {match.team2}"
    description = (
        f"The score is now **{score}** in this best of {match.best_of} series."
    )
    embed = discord.Embed(
        title=title, description=description, color=discord.Color.orange()
    )
    embed.set_footer(text=f"Match ID: {match.id}")
    embed.timestamp = datetime.now(timezone.utc)

    for guild in bot.guilds:
        try:
            await send_announcement(guild, embed)
            logger.info(
                f"Sent mid-series update for match {match.id} to guild {guild.id}."
            )
        except Exception as e:
            logger.error(
                f"Failed to send mid-series update for match {match.id} to guild {guild.id}: {e}"
            )


async def schedule_live_polling():
    """
    Checks for matches starting soon and schedules a dedicated polling job
    for each one.
    """
    logger.debug("Running schedule_live_polling job...")
    async with get_async_session() as session:
        now = datetime.now(timezone.utc)
        one_minute_from_now = now + timedelta(minutes=1)

        statement = select(Match).where(
            Match.scheduled_time >= now,
            Match.scheduled_time < one_minute_from_now,
            Match.result == None,  # noqa: E711
        )
        matches_starting_soon = (await session.exec(statement)).all()

        if not matches_starting_soon:
            logger.debug("No matches starting in the next minute.")
            return

        logger.info(
            f"Found {len(matches_starting_soon)} matches starting soon."
        )
        for match in matches_starting_soon:
            job_id = f"poll_match_{match.id}"
            if not scheduler.get_job(job_id):
                log_msg = (
                    "Match %s (%s vs %s) is starting soon. "
                    "Scheduling job '%s'."
                )
                logger.info(
                    log_msg, match.id, match.team1, match.team2, job_id
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
            else:
                logger.debug(
                    "Job '%s' for match %s already exists. Skipping.",
                    job_id,
                    match.id,
                )


def start_scheduler():
    # Local import to avoid circular dependency
    from src.commands.sync_leaguepedia import perform_leaguepedia_sync

    if not scheduler.running:
        logger.info("Scheduler not running. Starting jobs...")
        scheduler.add_job(
            perform_leaguepedia_sync,
            "interval",
            hours=6,
            id="sync_all_tournaments_job",
            replace_existing=True,
        )
        logger.info("Added 'sync_all_tournaments_job' to scheduler.")

        scheduler.add_job(
            schedule_live_polling,
            "interval",
            minutes=1,
            id="schedule_live_polling_job",
            replace_existing=True,
        )
        logger.info("Added 'schedule_live_polling_job' to scheduler.")

        scheduler.start()
        logger.info("Scheduler started.")
    else:
        logger.info("Scheduler is already running.")

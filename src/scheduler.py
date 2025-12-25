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
# Lazily create the AsyncIOScheduler to avoid creating background
# scheduler objects (and associated event loop hooks) at import time
# which can interfere with test runners and cause processes to not exit.
_scheduler = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(jobstores=jobstores)
    return _scheduler


# A lightweight proxy object that forwards attribute access to the
# lazily-created scheduler. This keeps `scheduler` available at module
# level so tests and code that patch `src.scheduler.scheduler` continue to
# work, while still avoiding creation of the real scheduler until needed.
class _SchedulerProxy:
    def __getattr__(self, item):
        return getattr(get_scheduler(), item)


# Public module-level symbol for compatibility
scheduler = _SchedulerProxy()


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


def _remove_job_if_exists(job_id: str):
    """
    Helper function to safely remove a job from the scheduler.
    Logs a debug message if the job doesn't exist.
    """
    try:
        scheduler.remove_job(job_id)
    except JobLookupError:
        logger.debug("Job %s was already removed.", job_id)


def _calculate_team_scores(relevant_games, match):
    """Calculate scores for both teams from the relevant games.

    This implementation is defensive and simpler: it normalizes team
    names, validates the winner value, and derives which normalized
    game-side corresponds to match.team1/team2 before incrementing
    scores.
    Returns a tuple of (team1_score, team2_score).
    """
    def _norm(s: str) -> str:
        return (s or "").strip().lower()

    m_t1 = _norm(match.team1)
    m_t2 = _norm(match.team2)

    def _scores_from_game(game: dict, m1: str, m2: str):
        # Return (delta_team1, delta_team2) for this game
        winner_raw = game.get("Winner")
        if winner_raw is None:
            return 0, 0
        try:
            winner_id = int(str(winner_raw).strip())
        except Exception:
            return 0, 0

        g1 = _norm(game.get("Team1"))
        g2 = _norm(game.get("Team2"))

        # If the game doesn't involve the two match teams, ignore it
        if {g1, g2} != {m1, m2}:
            return 0, 0

        # Determine which side (g1/g2) maps to match.team1
        # If winner_id is 1, the winner is g1; if 2, the winner is g2
        if winner_id == 1:
            return (1, 0) if g1 == m1 else (0, 1)
        if winner_id == 2:
            return (1, 0) if g2 == m1 else (0, 1)
        return 0, 0

    team1_score = 0
    team2_score = 0
    for game in relevant_games:
        d1, d2 = _scores_from_game(game, m_t1, m_t2)
        team1_score += d1
        team2_score += d2

    return team1_score, team2_score


def _determine_winner(team1_score, team2_score, match):
    """
    Determine if there's a winner based on the current scores.
    Returns the winner team name or None if no winner yet.
    """
    games_to_win = (match.best_of // 2) + 1
    if team1_score >= games_to_win:
        return match.team1
    elif team2_score >= games_to_win:
        return match.team2
    return None


async def _save_result_and_update_picks(session, match, winner, score_str):
    """
    Save the match result and update all picks for the match.
    Returns the created Result object.
    """
    result = Result(
        match_id=match.id,
        winner=winner,
        score=score_str,
    )
    session.add(result)

    # Update picks
    logger.info("Updating picks for match %s", match.id)
    statement = select(Pick).where(Pick.match_id == match.id)
    result_proxy = await session.exec(statement)
    picks_to_update = result_proxy.all()
    updated_count = 0
    for pick in picks_to_update:
        pick.is_correct = pick.chosen_team == winner
        session.add(pick)
        updated_count += 1
    logger.info("Updated %d picks for match %s.", updated_count, match.id)

    return result


async def _fetch_scoreboard_for_match(match: Match):
    logger.debug("Fetching scoreboard data for match %s", match.id)
    return await leaguepedia_client.get_scoreboard_data(
        match.contest.leaguepedia_id
    )


def _filter_relevant_games_from_scoreboard(scoreboard_data, match: Match):
    def _norm(s: str) -> str:
        return (s or "").strip().lower()

    match_teams = {_norm(match.team1), _norm(match.team2)}
    return [
        g
        for g in scoreboard_data
        if {_norm(g.get("Team1")), _norm(g.get("Team2"))} == match_teams
    ]


async def _handle_winner(
    match: Match,
    winner: str,
    current_score_str: str,
    job_id: str | None = None,
):
    """Handle a detected series winner: save result, update picks,
    notify guilds, and unschedule the poll job for the match.

    This function opens its own database session so callers do not need
    to pass one in (reduces argument count).
    """
    logger.info(
        "Series winner found for match %s: %s. Final Score: %s",
        match.id,
        winner,
        current_score_str,
    )

    # Use an internal session to persist the result and update picks.
    async with get_async_session() as session:
        result = await _save_result_and_update_picks(
            session, match, winner, current_score_str
        )
        await session.commit()
    logger.info("Saved result and updated picks for match %s.", match.id)

    await send_result_notification(match, result)

    if job_id is None:
        job_id = f"poll_match_{match.id}"
    logger.info("Unscheduling job %s for completed match.", job_id)
    _remove_job_if_exists(job_id)


async def _should_continue_polling(session, match: Match | None, job_id: str) -> bool:
    """Return True if polling should continue for this match.

    Encapsulates checks for match existence, existing result, and
    timeout to keep poll_live_match_job concise.
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


async def poll_live_match_job(match_db_id: int):
    """Polls a specific match for live updates/results using scoreboard data.
    Refactored to delegate checks and keep cyclomatic complexity low.
    """
    job_id = f"poll_match_{match_db_id}"
    logger.info("Polling for match ID %s (Job: %s)", match_db_id, job_id)

    async with get_async_session() as session:
        match = await crud.get_match_with_result_by_id(session, match_db_id)

        if not await _should_continue_polling(session, match, job_id):
            return

        scoreboard_data = await _fetch_scoreboard_for_match(match)
        if not scoreboard_data:
            logger.info("No scoreboard data found for match %s. Will retry.", match.id)
            return

        relevant_games = _filter_relevant_games_from_scoreboard(scoreboard_data, match)
        if not relevant_games:
            logger.info("No relevant games found in scoreboard data for match %s.", match.id)
            return

        logger.debug(
            "Found %d relevant games for match %s.", len(relevant_games), match.id
        )

        team1_score, team2_score = _calculate_team_scores(relevant_games, match)
        winner = _determine_winner(team1_score, team2_score, match)

        current_score_str = f"{team1_score}-{team2_score}"
        logger.debug(
            "Match %s score: %s. Last announced: %s",
            match.id,
            current_score_str,
            match.last_announced_score,
        )

        if winner:
            await _handle_winner(session, match, winner, current_score_str, job_id)
            return

        if match.last_announced_score == current_score_str:
            logger.info(
                "Polling for match %s complete. No winner yet. Current score: %s.",
                match.id,
                current_score_str,
            )
            return

        logger.info("New score for match %s: %s. Announcing update.", match.id, current_score_str)
        match.last_announced_score = current_score_str
        session.add(match)
        await session.commit()
        await send_mid_series_update(match, current_score_str)


async def send_reminder(match_id: int, minutes: int):
    """Sends a rich, informative embed as a match reminder to all guilds.

    The embed construction is delegated to a small helper to keep this
    function concise and reduce cyclomatic complexity.
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
        team1, team2 = await _fetch_teams(session, match)

        embed = _create_reminder_embed(match, team1, team2, minutes)
        await _broadcast_embed_to_guilds(bot, embed, f"{minutes}-minute reminder for match {match_id}")


def _create_reminder_embed(match: Match, team1: Team | None, team2: Team | None, minutes: int) -> discord.Embed:
    """Helper to build the reminder embed for a match.

    Extracted to keep send_reminder simpler and more testable.
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

    embed.add_field(name="Scheduled Time", value=f"<t:{scheduled_ts}:F>", inline=False)
    embed.set_footer(text="Use the /picks command to make your predictions!")
    return embed


async def send_result_notification(match: Match, result: Result):
    """Sends a rich, detailed embed with match results to all guilds."""
    logger.info(
        "Broadcasting result notification for match %s "
        "to all guilds.",
        match.id,
    )
    bot = get_bot_instance()

    async with get_async_session() as session:
        logger.debug("Fetching teams and picks for match %s", match.id)
        team1, team2 = await _fetch_teams(session, match)

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
            title=title,
            description=description,
            color=discord.Color.gold(),
        )

        if winner_team_obj and winner_team_obj.image_url:
            embed.set_thumbnail(url=winner_team_obj.image_url)

        if total_picks > 0:
            picks_value = (
                "**{cp}** of **{tp}** users "
                "({pc:.2f}%) correctly picked the winner."
            ).format(
                cp=correct_picks, tp=total_picks, pc=correct_percentage
            )
        else:
            picks_value = "No picks were made for this match."

        embed.add_field(
            name="📊 Pick'em Stats", value=picks_value, inline=False
        )
        embed.set_footer(
            text="Leaguepedia Match ID: %s" % match.leaguepedia_id
        )
        embed.timestamp = datetime.now(timezone.utc)

        await _broadcast_embed_to_guilds(bot, embed, f"result notification for match {match.id}")


async def send_mid_series_update(match: Match, score: str):
    """Sends a Discord embed with a mid-series score update to all guilds."""
    logger.info(
        "Broadcasting mid-series update for match %s "
        "(score: %s) to all guilds.",
        match.id,
        score,
    )
    bot = get_bot_instance()

    title = f"Live Update: {match.team1} vs {match.team2}"
    description = (
        f"The score is now **{score}** in this best of {match.best_of} series."
    )
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.orange(),
    )
    embed.set_footer(text="Match ID: %s" % match.id)
    embed.timestamp = datetime.now(timezone.utc)

    await _broadcast_embed_to_guilds(bot, embed, f"mid-series update for match {match.id} (score: {score})")


async def _fetch_teams(session, match: Match):
    """Return (team1_obj, team2_obj) for the given match using the session."""
    team1_stmt = select(Team).where(Team.name == match.team1)
    team2_stmt = select(Team).where(Team.name == match.team2)
    team1 = (await session.exec(team1_stmt)).first()
    team2 = (await session.exec(team2_stmt)).first()
    return team1, team2


async def _broadcast_embed_to_guilds(bot: discord.Client, embed: discord.Embed, context: str):
    """Send an embed to all guilds and centralize logging/exception handling.

    context is a short description used in logs.
    """
    for guild in bot.guilds:
        try:
            await send_announcement(guild, embed)
            logger.info("Sent %s to guild %s.", context, guild.id)
        except Exception as e:
            logger.error("Failed to send %s to guild %s: %s", context, guild.id, e)


async def _get_matches_starting_soon(session):
    now = datetime.now(timezone.utc)
    one_minute_from_now = now + timedelta(minutes=1)
    stmt = select(Match).where(
        Match.scheduled_time >= now,
        Match.scheduled_time < one_minute_from_now,
        Match.result == None,  # noqa: E711
    )
    matches = (await session.exec(stmt)).all()
    return now, matches


def _safe_get_jobs():
    try:
        return scheduler.get_jobs()
    except AttributeError:
        logger.debug("schedule_live_polling: scheduler.get_jobs() not available")
        return []
    except Exception as e:
        logger.warning("schedule_live_polling: failed to enumerate scheduler jobs: %s", e)
        return []


def _count_poll_jobs(jobs):
    try:
        return sum(1 for j in jobs if getattr(j, "id", "").startswith("poll_match_"))
    except Exception:
        logger.debug("schedule_live_polling: unexpected job object while counting poll jobs")
        return 0


def _schedule_poll_for_match(match):
    job_id = f"poll_match_{match.id}"
    if scheduler.get_job(job_id):
        logger.debug("Job '%s' for match %s already exists. Skipping.", job_id, match.id)
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
    Checks for matches starting soon and schedules a dedicated polling job
    for each one.
    """
    logger.debug("Running schedule_live_polling job...")

    async with get_async_session() as session:
        now, matches_starting_soon = await _get_matches_starting_soon(session)

        if matches_starting_soon:
            times = [getattr(m, "scheduled_time", None) for m in matches_starting_soon]
            times = [t for t in times if t is not None]
            earliest = min(times) if times else None
            logger.info(
                "schedule_live_polling: found %d candidate(s); earliest scheduled_time=%s",
                len(matches_starting_soon),
                earliest,
            )
        else:
            logger.info("schedule_live_polling: found 0 candidates in the 1-minute window.")

        jobs = _safe_get_jobs()
        poll_jobs_count = _count_poll_jobs(jobs)
        logger.info("schedule_live_polling: %d poll_match jobs in scheduler", poll_jobs_count)

        if not matches_starting_soon:
            return

        for match in matches_starting_soon:
            _schedule_poll_for_match(match)


def start_scheduler():
    # Local import to avoid circular dependency
    from src.commands.sync_leaguepedia import perform_leaguepedia_sync
    if not getattr(scheduler, "running", False):
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

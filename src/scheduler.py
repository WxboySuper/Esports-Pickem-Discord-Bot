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
    """
    Lazily instantiate and return the module-level AsyncIOScheduler.

    Returns:
        AsyncIOScheduler: The shared scheduler instance used by the
            module; created on first invocation and reused thereafter.
    """
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
        """
        Delegate attribute lookups to the underlying
        lazily-instantiated scheduler.

        Parameters:
            item (str): Name of the attribute being accessed on
                the proxy.

        Returns:
            Any: The attribute value retrieved from the underlying
                scheduler instance.
        """
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
    """
    Compute aggregate series scores for match.team1 and match.team2
    from scoreboard game entries.

    Normalizes team names and counts wins using each game's 'Winner'
    field (expected values 1 or 2). Games that do not involve both
    match teams or that contain an invalid/missing winner are ignored.

    Parameters:
        relevant_games (Iterable[dict]): Sequence of scoreboard
            entries; each entry should provide at least the keys
            'Team1', 'Team2', and 'Winner'.
        match (object): Match object with attributes `team1` and
            `team2` containing team names.

    Returns:
        tuple: (team1_score, team2_score) — integers representing
            the number of games won by match.team1 and match.team2,
            respectively.
    """

    def _norm(s: str) -> str:
        """
        Normalize a text string for case- and whitespace-insensitive
        comparisons.

        Parameters:
            s (str): Input string to normalize; None or falsy values
                are treated as empty.

        Returns:
            normalized (str): The input converted to lowercase with
                leading/trailing whitespace removed (empty string if
                input was falsy).
        """
        return (s or "").strip().lower()

    m_t1 = _norm(match.team1)
    m_t2 = _norm(match.team2)

    def _scores_from_game(game: dict, m1: str, m2: str):
        # Return (delta_team1, delta_team2) for this game
        """
        Compute the score delta contributed by a single scoreboard
        game for a match between two teams.

        Parameters:
            game (dict): A scoreboard entry containing at least
                "Team1", "Team2", and "Winner".
            m1 (str): Normalized identifier for match.team1.
            m2 (str): Normalized identifier for match.team2.

        Returns:
            tuple: (delta_team1, delta_team2) where exactly one value
                is 1 when the game is won by one of the match teams
                and 0 otherwise. Returns (0, 0) if the game does not
                involve the two match teams or the winner is
                missing/invalid.
        """
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
    Persist a match result and mark all picks for that match as
    correct or incorrect.

    Parameters:
        session: An asynchronous database session used to add the
            result and update picks.
        match: The Match model instance for which the result is being
            recorded.
        winner: The value stored as the winner on the Result;
            compared against each Pick.chosen_team to set is_correct.
        score_str: A human-readable score string to store on the
            Result.

    Returns:
        The created Result instance that was added to the session
            (not committed).
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


def _filter_relevant_games_from_scoreboard(scoreboard_data, match: Match):
    """
    Return the subset of scoreboard entries that involve exactly the
    two teams in the given match.

    Parameters:
        scoreboard_data (iterable[dict]): Iterable of scoreboard
            entries where each entry is expected to have "Team1" and
            "Team2" keys containing team names.
        match (Match): Match whose `team1` and `team2` names are used
            to identify relevant entries.

    Returns:
        list[dict]: List of scoreboard entries from `scoreboard_data`
            whose Team1/Team2 pair matches the match teams (order-
            insensitive).
    """

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

        relevant_games = _filter_relevant_games_from_scoreboard(
            scoreboard_data, match
        )
        if not relevant_games:
            logger.info(
                "No relevant games found in scoreboard data for match %s.",
                match.id,
            )
            return

        logger.debug(
            "Found %d relevant games for match %s.",
            len(relevant_games),
            match.id,
        )

        team1_score, team2_score = _calculate_team_scores(
            relevant_games, match
        )
        winner = _determine_winner(team1_score, team2_score, match)

        current_score_str = f"{team1_score}-{team2_score}"
        logger.debug(
            "Match %s score: %s. Last announced: %s",
            match.id,
            current_score_str,
            match.last_announced_score,
        )

        if winner:
            await _handle_winner(match, winner, current_score_str, job_id)
            return

        if match.last_announced_score == current_score_str:
            logger.info(
                "Polling for match %s complete. No winner yet. Score: %s.",
                match.id,
                current_score_str,
            )
            return

        logger.info(
            "New score for match %s: %s. Announcing update.",
            match.id,
            current_score_str,
        )
        match.last_announced_score = current_score_str
        session.add(match)
        await session.commit()
        await send_mid_series_update(match, current_score_str)


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
        team1, team2 = await _fetch_teams(session, match)

        embed = _create_reminder_embed(match, team1, team2, minutes)
        await _broadcast_embed_to_guilds(
            bot, embed, f"{minutes}-minute reminder for match {match_id}"
        )


def _create_reminder_embed(
    match: Match, team1: Team | None, team2: Team | None, minutes: int
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


async def send_result_notification(match: Match, result: Result):
    """
    Broadcast a rich Discord embed with the final result of a match
    to all guilds.

    Builds a gold-colored embed showing the winner, final score, and
    pick'em statistics (total picks, correct picks, percentage),
    includes the winner's thumbnail when available, timestamps the
    embed, and broadcasts it to every guild the bot is in.

    Parameters:
        match (Match): Match model instance for which the result
            applies.
        result (Result): Result model instance containing `winner`
            and `score`.
    """
    logger.info(
        "Broadcasting result notification for match %s " "to all guilds.",
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
            ).format(cp=correct_picks, tp=total_picks, pc=correct_percentage)
        else:
            picks_value = "No picks were made for this match."

        embed.add_field(
            name="📊 Pick'em Stats", value=picks_value, inline=False
        )
        embed.set_footer(
            text="Leaguepedia Match ID: %s" % match.leaguepedia_id
        )
        embed.timestamp = datetime.now(timezone.utc)

        await _broadcast_embed_to_guilds(
            bot, embed, f"result notification for match {match.id}"
        )


async def send_mid_series_update(match: Match, score: str):
    """
    Builds and broadcasts a Discord embed announcing a live
    mid-series score update to all guilds.

    Parameters:
        match (Match): Match object containing teams, id, and best_of
            used in the embed.
        score (str): Current series score string (for example, "2-1")
            displayed in the embed.
    """
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

    await _broadcast_embed_to_guilds(
        bot, embed, f"mid-series update for match {match.id} (score: {score})"
    )


async def _fetch_teams(session, match: Match):
    """
    Retrieve the Team objects corresponding to the match's team1 and
    team2 names.

    Parameters:
        session: Database session to execute queries.
        match (Match): Match instance whose `team1` and `team2` name
            fields are used to look up teams.

    Returns:
        tuple: (team1_obj, team2_obj) where each element is the
            matching Team object or `None` if no match was found.
    """
    team1_stmt = select(Team).where(Team.name == match.team1)
    team2_stmt = select(Team).where(Team.name == match.team2)
    team1 = (await session.exec(team1_stmt)).first()
    team2 = (await session.exec(team2_stmt)).first()
    return team1, team2


async def _broadcast_embed_to_guilds(
    bot: discord.Client, embed: discord.Embed, context: str
):
    """
    Broadcast an embed to every guild the bot is a member of and
    record success or failure for each delivery.

    Parameters:
        context (str): Short description included in log messages to
            identify this broadcast.
    """
    for guild in bot.guilds:
        try:
            await send_announcement(guild, embed)
            logger.info("Sent %s to guild %s.", context, guild.id)
        except Exception as e:
            logger.error(
                "Failed to send %s to guild %s: %s", context, guild.id, e
            )


async def _get_matches_starting_soon(session):
    """
    Get the current UTC time and the Match records scheduled to start within the next 5 minutes that have no result.
    
    Parameters:
        session: A SQLModel/SQLAlchemy session used to query Match records.
    
    Returns:
        tuple: (now, matches) where `now` is the current UTC datetime and `matches` is a list of Match objects with `scheduled_time` >= `now`, < 5 minutes after `now`, and `result` is None.
    """
    now = datetime.now(timezone.utc)
    five_minutes_from_now = now + timedelta(minutes=5)
    stmt = select(Match).where(
        Match.scheduled_time >= now,
        Match.scheduled_time < five_minutes_from_now,
        Match.result.is_(None),
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
    Schedule recurring live-polling jobs for matches starting within the next 5 minutes.
    
    Scans the database for matches with no result that are scheduled to begin within the upcoming 5-minute window, logs candidate and currently scheduled poll job counts, and schedules a recurring poll job for each candidate match. Does not return a value.
    """
    logger.debug("Running schedule_live_polling job...")

    async with get_async_session() as session:
        now, matches_starting_soon = await _get_matches_starting_soon(session)

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


def start_scheduler():
    # Local import to avoid circular dependency
    """
    Ensure the module scheduler has the required recurring jobs and start it if not already running.
    
    Registers a 6-hour interval job to sync Leaguepedia data and a 5-minute interval job to schedule live match polling, then starts the scheduler if it is not running. If the scheduler is already running, the function leaves it unchanged.
    """
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
            minutes=5,
            id="schedule_live_polling_job",
            replace_existing=True,
        )
        logger.info("Added 'schedule_live_polling_job' to scheduler.")

        scheduler.start()
        logger.info("Scheduler started.")
    else:
        logger.info("Scheduler is already running.")
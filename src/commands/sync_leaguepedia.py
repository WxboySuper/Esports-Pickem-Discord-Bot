import io
import json
import logging
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from src.auth import is_admin
from src.config import DATA_PATH
from src.leaguepedia_client import leaguepedia_client
from src.db import get_async_session
from src.crud import upsert_contest, upsert_match, upsert_team
from src.scheduler import schedule_reminders, send_result_notification
from src.match_result_utils import (
    filter_relevant_games_from_scoreboard,
    calculate_team_scores,
    determine_winner,
    save_result_and_update_picks,
)
from src import crud
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
CONFIG_PATH = DATA_PATH / "tournaments.json"


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


async def _process_teams_for_match(
    match_data: dict, db_session, summary: dict
) -> None:
    """
    Process and upsert teams for a single match.
    """
    for team_key in ["Team1", "Team2"]:
        team_name = match_data.get(team_key)
        if not team_name:
            logger.warning("Missing '%s' in match data.", team_key)
            continue
        await upsert_team(
            db_session,
            {"leaguepedia_id": team_name, "name": team_name},
        )
        summary["teams"] += 1


@dataclass
class SyncContext:
    contest: object
    db_session: object
    summary: dict
    scoreboard: list | None = None
    notifications: list = field(default_factory=list)


async def _process_match(
    match_data: dict,
    ctx: SyncContext,
) -> tuple | None:
    """
    Process and upsert a single match.
    Returns (match, time_changed) tuple or None if match cannot be processed.
    """
    match_id = match_data.get("MatchId")
    if not match_id:
        logger.warning("Missing MatchId in data: %s", match_data)
        return None

    scheduled_time = _parse_date(match_data.get("DateTime UTC"))
    if not scheduled_time:
        logger.warning("Match %s has no scheduled time. Skipping.", match_id)
        return None
    match, time_changed = await upsert_match(
        ctx.db_session,
        {
            "leaguepedia_id": match_id,
            "contest_id": ctx.contest.id,
            "team1": match_data.get("Team1"),
            "team2": match_data.get("Team2"),
            "best_of": (
                int(match_data["BestOf"]) if match_data.get("BestOf") else None
            ),
            "scheduled_time": scheduled_time,
        },
    )
    ctx.summary["matches"] += 1

    # Delegate scoreboard-based detection/handling to a helper to keep
    # this function focused and easier to test. The helper may append
    # created Result objects to `ctx.notifications` for later
    # notification (after the outer transaction commits).
    await _detect_and_handle_result(match, ctx, match_id)

    return (match, time_changed)


async def _upsert_contest_data(overview_page, contest_matches, db_session):
    match_times = [_parse_date(m.get("DateTime UTC")) for m in contest_matches]
    valid_times = [t for t in match_times if t is not None]

    if not valid_times:
        logger.warning(
            "No valid match times for contest '%s'. Skipping.",
            overview_page,
        )
        return None

    start_date = min(valid_times)
    end_date = max(valid_times)
    tournament_name = contest_matches[0].get("Name")

    contest = await upsert_contest(
        db_session,
        {
            "leaguepedia_id": overview_page,
            "name": tournament_name,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    if not contest:
        logger.warning("Failed to upsert contest '%s'.", tournament_name)

    return contest


async def _fetch_contest_scoreboard(overview_page):
    try:
        return await leaguepedia_client.get_scoreboard_data(overview_page)
    except Exception:
        logger.exception(
            "Failed to fetch scoreboard for contest %s; continuing without",
            overview_page,
        )
        return None


async def _process_contest(
    overview_page: str, contest_matches: list, db_session, summary: dict
) -> tuple:
    """
    Process a single contest and its matches.
    Returns a tuple `(matches_to_schedule, notifications)` where
    `matches_to_schedule` is a list of matches that need reminders
    scheduled and `notifications` is a list of result notifications to
    send after the outer transaction commits.
    """
    matches_to_schedule = []

    contest = await _upsert_contest_data(
        overview_page, contest_matches, db_session
    )
    if not contest:
        # Ensure we always return the same tuple shape so callers can
        # reliably unpack the result. There are no notifications in
        # this early-exit case.
        return matches_to_schedule, []

    summary["contests"] += 1
    await db_session.flush()

    # Fetch the contest scoreboard once to avoid repeating API calls per
    # match. If the fetch fails or returns None, we'll proceed without
    # scoreboard-based result detection.
    scoreboard = await _fetch_contest_scoreboard(overview_page)

    # Build a small context object to avoid long argument lists.
    ctx = SyncContext(
        contest=contest,
        db_session=db_session,
        summary=summary,
        scoreboard=scoreboard,
    )

    for match_data in contest_matches:
        await _process_teams_for_match(match_data, db_session, summary)

        result = await _process_match(match_data, ctx)
        if result:
            match, time_changed = result
            if match and time_changed:
                matches_to_schedule.append(match)

    # Return matches to schedule and any notifications that need to be
    # sent after the outer transaction commits.
    return matches_to_schedule, ctx.notifications


def _calculate_match_outcome(scoreboard, match):
    """
    Analyzes scoreboard to determine if there is a winner.
    Returns (winner, score_str) or (None, None).
    """
    relevant_games = filter_relevant_games_from_scoreboard(scoreboard, match)
    if not relevant_games:
        return None, None

    team1_score, team2_score = calculate_team_scores(relevant_games, match)

    if getattr(match, "best_of", None) is None:
        logger.warning(
            "Skipping result detection for match %s: missing best_of",
            match.id,
        )
        return None, None

    winner = determine_winner(team1_score, team2_score, match)
    if not winner:
        return None, None

    return winner, f"{team1_score}-{team2_score}"


async def _persist_match_outcome(ctx, match, winner, score_str):
    """
    Persists the result if it doesn't already exist.
    """
    try:
        match_in_session = await crud.get_match_with_result_by_id(
            ctx.db_session, match.id
        )

        if match_in_session is None:
            logger.warning(
                "Match %s disappeared before result persistence; skipping",
                match.id,
            )
            return None

        if getattr(match_in_session, "result", None):
            # Log that a result already exists for this match and what it is
            existing = match_in_session.result
            try:
                logger.info(
                    "Match %s already has result: winner=%s score=%s",
                    getattr(match_in_session, "leaguepedia_id", match_in_session.id),
                    getattr(existing, "winner", None),
                    getattr(existing, "score", None),
                )
            except Exception:
                logger.debug("Failed to log existing result for match %s", match_in_session.id)
            return None

        result = await save_result_and_update_picks(
            ctx.db_session, match, winner, score_str
        )

        try:
            await ctx.db_session.flush()
        except Exception:
            logger.exception(
                "Failed to flush session after saving result for match %s",
                match.id,
            )
            return None

        ctx.notifications.append((match.id, result.id))
        return result
    except Exception:
        logger.exception(
            "Failed to persist result in session for match %s", match.id
        )
        return None


async def _detect_and_handle_result(match, ctx: SyncContext, match_id: str):
    """
    Inspect `ctx.scoreboard` for `match`. If the series is complete and no
    local `Result` exists, persist the Result using the provided
    `ctx.db_session` (do NOT commit here) and append the
    `(match.id, result.id)` tuple to `ctx.notifications` so callers can
    notify after the outer
    transaction commits. Errors are logged and do not raise.
    """
    scoreboard = ctx.scoreboard
    match_key = getattr(match, "leaguepedia_id", None) or getattr(match, "id", None)

    if not scoreboard:
        logger.debug(
            "No scoreboard available for contest while checking match %s",
            match_key,
        )
        return None

    # Log if the match already has a persisted result
    try:
        # Fetch the match using a select that eagerly loads the result to
        # avoid triggering sync lazy-loading on an async session-bound
        # instance. This ensures reliable inspection of any existing
        # persisted Result.
        match_with_result = await crud.get_match_with_result_by_id(
            ctx.db_session, match.id
        )
        existing_result = getattr(match_with_result, "result", None) if match_with_result else None
        if existing_result:
            logger.info(
                "Match %s already persisted result: winner=%s score=%s",
                match_key,
                getattr(existing_result, "winner", None),
                getattr(existing_result, "score", None),
            )
            return None
    except Exception:
        logger.exception(
            "Failed to fetch match with result for %s", match_key
        )
        return None

    try:
        winner, score_str = _calculate_match_outcome(scoreboard, match)
        if not winner:
            logger.info("No result detected on scoreboard for match %s", match_key)
            return None

        logger.info(
            "Detected scoreboard result for match %s: winner=%s score=%s",
            match_key,
            winner,
            score_str,
        )

        return await _persist_match_outcome(ctx, match, winner, score_str)
    except Exception:
        logger.exception(
            "Error checking/recording result for match %s", match_id
        )
        return None


async def _sync_single_tournament(
    tournament_name_like: str, db_session, summary: dict
) -> tuple:
    """
    Helper to sync data for a single tournament.
    Returns a tuple (matches_to_schedule, notifications) where
    matches_to_schedule is a list of matches needing reminders and
    notifications is a list of (match_id, result_id) tuples for result
    notifications.
    """
    logger.info(
        "Fetching upcoming matches for tournament pattern: '%s'",
        tournament_name_like,
    )
    matches_to_schedule = []
    notifications = []
    matches_data = await leaguepedia_client.fetch_upcoming_matches(
        tournament_name_like
    )

    if not matches_data:
        logger.warning(
            "No matches found for tournament pattern '%s'.",
            tournament_name_like,
        )
        return matches_to_schedule

    log_msg = "Found %d matches for tournament pattern '%s'"
    logger.info(log_msg, len(matches_data), tournament_name_like)

    # Group matches by contest (OverviewPage)
    contests = {}
    for match_data in matches_data:
        overview_page = match_data.get("OverviewPage")
        if not overview_page:
            logger.warning(
                "Match data is missing OverviewPage. Skipping: %s", match_data
            )
            continue
        if overview_page not in contests:
            contests[overview_page] = []
        contests[overview_page].append(match_data)

    for overview_page, contest_matches in contests.items():
        contest_schedule, contest_notifications = await _process_contest(
            overview_page, contest_matches, db_session, summary
        )
        matches_to_schedule.extend(contest_schedule)
        notifications.extend(contest_notifications)

    logger.info("Finished processing matches for '%s'", tournament_name_like)
    return matches_to_schedule, notifications


async def perform_leaguepedia_sync() -> dict | None:
    """
    Performs a full sync of tournaments, matches, and teams from
    Leaguepedia based on the configured tournament slugs.
    Returns a summary of the sync operation, or None if it fails.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            tournament_slugs = json.load(f)
        logger.info("Loaded %d slugs for sync.", len(tournament_slugs))
        logger.debug("Slugs: %s", tournament_slugs)
    except FileNotFoundError:
        logger.warning("tournaments.json not found. Skipping sync.")
        return None

    if not tournament_slugs:
        logger.info("No tournaments configured. Skipping sync.")
        return None

    summary = {"contests": 0, "matches": 0, "teams": 0}
    all_matches_to_schedule = []
    all_notifications = []

    async with get_async_session() as db_session:
        for slug in tournament_slugs:
            matches_to_schedule, notifications = await _sync_single_tournament(
                slug, db_session, summary
            )
            all_matches_to_schedule.extend(matches_to_schedule)
            all_notifications.extend(notifications)
        await db_session.commit()

    # Schedule reminders after the main transaction is committed
    for match in all_matches_to_schedule:
        await schedule_reminders(match)

    # Send result notifications after the commit so the persisted
    # Result and Pick updates are visible to notification handlers.
    logger.info("Sending result notifications...")
    for match_id, result_id in all_notifications:
        try:
            logger.info(
                "Sending result notification for match %s (result %s)",
                match_id, result_id
            )
            await send_result_notification(match_id, result_id)
        except Exception as exc:
            logger.exception(
                "Failed to send result notification for match %s "
                "(result %s, %s)",
                match_id,
                result_id,
                type(exc).__name__,
            )

    logger.info(
        "Sync complete: %d contests, %d matches, %d teams upserted.",
        summary["contests"],
        summary["matches"],
        summary["teams"],
    )
    return summary


class SyncLeaguepedia(commands.Cog):
    """A cog for syncing data from Leaguepedia."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="sync-leaguepedia",
        description="Syncs configured tournaments from Leaguepedia.",
    )
    @is_admin()
    async def sync_leaguepedia(self, interaction: discord.Interaction):
        """
        Performs a full sync and returns the logs as a file for debugging.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Set up a temporary logger to capture the sync process output
        log_stream = io.StringIO()
        root_logger = logging.getLogger()
        original_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)  # Capture everything

        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        try:
            summary = await perform_leaguepedia_sync()

            # Retrieve the logs
            log_contents = log_stream.getvalue()

            if summary is None:
                message = (
                    "Sync could not be completed. This may be because the "
                    "configuration file was not found or was empty. "
                    "See attached logs for more details."
                )
            else:
                message = (
                    "Leaguepedia sync complete!\n"
                    f"- Upserted {summary['contests']} contests.\n"
                    f"- Upserted {summary['matches']} matches.\n"
                    f"- Upserted {summary['teams']} teams."
                )

            if log_contents:
                # Create a file object from the log contents
                log_file = discord.File(
                    io.BytesIO(log_contents.encode()),
                    filename="sync_logs.txt",
                )
                await interaction.followup.send(
                    message, file=log_file, ephemeral=True
                )
            else:
                await interaction.followup.send(
                    message + "\n_No log output was generated._",
                    ephemeral=True,
                )
        finally:
            # Clean up the logger
            root_logger.removeHandler(handler)
            root_logger.setLevel(original_level)
            log_stream.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncLeaguepedia(bot))

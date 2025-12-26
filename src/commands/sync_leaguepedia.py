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
from src.scheduler import (
    schedule_reminders,
    _filter_relevant_games_from_scoreboard,
    _calculate_team_scores,
    _determine_winner,
    _save_result_and_update_picks,
    send_result_notification,
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


async def _process_contest(
    overview_page: str, contest_matches: list, db_session, summary: dict
) -> tuple:
    """
    Process a single contest and its matches.
    Returns a list of matches that need reminders scheduled.
    """
    matches_to_schedule = []
    match_times = [_parse_date(m.get("DateTime UTC")) for m in contest_matches]
    valid_times = [t for t in match_times if t is not None]

    if not valid_times:
        logger.warning(
            "No valid match times for contest '%s'. Skipping.",
            overview_page,
        )
        return matches_to_schedule

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
        return matches_to_schedule

    summary["contests"] += 1
    await db_session.flush()

    # Fetch the contest scoreboard once to avoid repeating API calls per
    # match. If the fetch fails or returns None, we'll proceed without
    # scoreboard-based result detection.
    try:
        scoreboard = await leaguepedia_client.get_scoreboard_data(
            overview_page
        )
    except Exception:
        logger.exception(
            "Failed to fetch scoreboard for contest %s; continuing without",
            overview_page,
        )
        scoreboard = None

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


async def _detect_and_handle_result(match, ctx: SyncContext, match_id: str):
    """
    Inspect `ctx.scoreboard` for `match`. If the series is complete and no
    local `Result` exists, persist the Result using the provided
    `ctx.db_session` (do NOT commit here) and append the `(match, result)`
    tuple to `ctx.notifications` so callers can notify after the outer
    transaction commits. Errors are logged and do not raise.
    """
    scoreboard = ctx.scoreboard
    if not scoreboard:
        return None

    try:
        relevant_games = _filter_relevant_games_from_scoreboard(
            scoreboard, match
        )
        if not relevant_games:
            return None

        team1_score, team2_score = _calculate_team_scores(
            relevant_games, match
        )
        # Guard against missing `best_of` which would cause a TypeError
        # inside `_determine_winner` when it attempts integer division.
        if getattr(match, "best_of", None) is None:
            logger.warning(
                "Skipping result detection for match %s: missing best_of",
                match.id,
            )
            return None
        winner = _determine_winner(team1_score, team2_score, match)
        if not winner:
            return None

        score_str = f"{team1_score}-{team2_score}"

        try:
            # Fetch the match with its result relationship eagerly loaded
            # to avoid relying on in-memory attributes that may be
            # detached or stale.
            match_in_session = await crud.get_match_with_result_by_id(
                ctx.db_session, match.id
            )

            if match_in_session is None:
                logger.warning(
                    "Match %s disappeared before result persistence; skipping",
                    match.id,
                )
                return None

            # If a Result already exists, bail out to avoid duplicates.
            if getattr(match_in_session, "result", None):
                return None

            # Use the caller's session to persist changes; do not commit
            # here so the outer transaction remains atomic. The helper
            # only requires `match.id`, so pass the original `match`
            # to avoid unnecessary re-fetching.
            result = await _save_result_and_update_picks(
                ctx.db_session, match, winner, score_str
            )
            # Ensure IDs are populated before we leave the transaction
            try:
                await ctx.db_session.flush()
            except Exception:
                # If flush fails, log and skip notification for safety
                logger.exception(
                    "Failed to flush session after saving result for match %s",
                    match.id,
                )
                return None

            # Record IDs for later notification after commit
            ctx.notifications.append((match.id, result.id))
            return result
        except Exception:
            logger.exception(
                "Failed to persist result in session for match %s", match_id
            )
            return None
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
    Returns a list of matches that need reminders scheduled.
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
    for match_id, result_id in all_notifications:
        try:
            await send_result_notification(match_id, result_id)
        except Exception:
            logger.exception(
                "Failed to send result notification for match %s", match_id
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

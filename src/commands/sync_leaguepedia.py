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


async def _sync_single_tournament(
    tournament_name_like: str, db_session, summary: dict
):
    """
    Helper to sync data for a single tournament using the new cargo query.
    """
    logger.info(
        "Fetching upcoming matches for tournament pattern: '%s'",
        tournament_name_like,
    )
    matches_data = await leaguepedia_client.fetch_upcoming_matches(
        tournament_name_like
    )

    if not matches_data:
        logger.warning(
            "No matches found for tournament pattern '%s'.",
            tournament_name_like,
        )
        return

    log_msg = "Found %d matches for tournament pattern '%s'"
    logger.info(log_msg, len(matches_data), tournament_name_like)

    # Keep track of contests we've already processed in this run
    processed_contests = {}

    for match_data in matches_data:
        logger.debug("Processing match data: %s", match_data)

        tournament_name = match_data.get("Name")
        overview_page = match_data.get("OverviewPage")

        if not tournament_name or not overview_page:
            log_msg = (
                "Match data is missing Tournament Name or "
                "OverviewPage. Skipping: %s"
            )
            logger.warning(log_msg, match_data)
            continue

        # Upsert contest if we haven't seen it before in this sync
        if overview_page not in processed_contests:
            contest = await upsert_contest(
                db_session,
                {
                    "leaguepedia_id": overview_page,
                    "name": tournament_name,
                },
            )
            if not contest:
                logger.warning(
                    "Failed to upsert contest for '%s'.", tournament_name
                )
                continue
            summary["contests"] += 1
            await db_session.flush()  # Ensure contest.id is available
            processed_contests[overview_page] = contest
        else:
            contest = processed_contests[overview_page]

        # Upsert teams
        for team_name_key in ["Team1", "Team2"]:
            team_name = match_data.get(team_name_key)
            if not team_name:
                logger.warning(
                    "Match data is missing '%s'. Skipping team sync.",
                    team_name_key,
                )
                continue

            await upsert_team(
                db_session, {"leaguepedia_id": team_name, "name": team_name}
            )
            summary["teams"] += 1

        match_id = match_data.get("MatchId")
        if not match_id:
            logger.warning(
                "Match data is missing MatchId. Skipping match sync: %s",
                match_data,
            )
            continue

        await upsert_match(
            db_session,
            {
                "leaguepedia_id": match_id,
                "contest_id": contest.id,
                "team1": match_data.get("Team1"),
                "team2": match_data.get("Team2"),
                "scheduled_time": _parse_date(match_data.get("DateTime_UTC")),
            },
        )
        summary["matches"] += 1

    logger.info(
        "Finished processing matches for tournament pattern '%s'",
        tournament_name_like,
    )


async def perform_leaguepedia_sync() -> dict | None:
    """
    Performs a full sync of tournaments, matches, and teams from
    Leaguepedia based on the configured tournament slugs.
    Returns a summary of the sync operation, or None if it fails.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            tournament_slugs = json.load(f)
        logger.info(
            "Loaded %d tournament slugs for sync.", len(tournament_slugs)
        )
        logger.debug("Tournament slugs: %s", tournament_slugs)
    except FileNotFoundError:
        logger.warning(
            "data/tournaments.json not found. Skipping scheduled sync."
        )
        return None

    if not tournament_slugs:
        logger.info("No tournaments configured for sync. Skipping.")
        return None

    summary = {"contests": 0, "matches": 0, "teams": 0}
    async with get_async_session() as db_session:
        for slug in tournament_slugs:
            await _sync_single_tournament(slug, db_session, summary)
        await db_session.commit()

    logger.info(
        "Leaguepedia sync complete: "
        f"{summary['contests']} contests, "
        f"{summary['matches']} matches, "
        f"{summary['teams']} teams upserted."
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
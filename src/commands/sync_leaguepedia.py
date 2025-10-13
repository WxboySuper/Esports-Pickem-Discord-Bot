import json
import logging
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from datetime import datetime, timezone

from src.auth import is_admin
from src.config import DATA_PATH
from src.leaguepedia_client import LeaguepediaClient
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
    slug: str, client: LeaguepediaClient, db_session, summary: dict
):
    """Helper to sync data for a single tournament slug."""
    logger.info("Syncing tournament with slug: '%s'", slug)
    contest_data = await client.get_tournament_by_slug(slug)
    if not contest_data:
        logger.warning("No contest data found for slug '%s'. Skipping.", slug)
        return

    logger.debug("Contest data for '%s': %s", slug, contest_data)
    contest = await upsert_contest(
        db_session,
        {
            "leaguepedia_id": slug,
            "name": contest_data.get("Name"),
            "start_date": _parse_date(contest_data.get("DateStart")),
            "end_date": _parse_date(contest_data.get("DateEnd")),
        },
    )
    if not contest:
        logger.warning("Failed to upsert contest for slug '%s'.", slug)
        return

    summary["contests"] += 1
    await db_session.flush()

    logger.info("Fetching matches for tournament '%s'", slug)
    matches_data = await client.get_matches_for_tournament(slug)
    logger.info(
        "Found %d matches for tournament '%s'", len(matches_data), slug
    )

    for match_data in matches_data:
        logger.debug("Processing match data: %s", match_data)
        for team_name_key in ["Team1", "Team2"]:
            team_name = match_data.get(team_name_key)
            if not team_name:
                logger.warning(
                    "Match data is missing '%s'. Skipping team sync.",
                    team_name_key,
                )
                continue

            logger.debug("Fetching team data for: '%s'", team_name)
            team_api_data = await client.get_team(team_name)
            if team_api_data:
                logger.debug(
                    "Got team API data for '%s': %s", team_name, team_api_data
                )
                team_data = {
                    "leaguepedia_id": team_name,
                    "name": team_api_data.get("Name"),
                    "image_url": team_api_data.get("Image"),
                    "roster": json.dumps(team_api_data.get("Roster")),
                }
                await upsert_team(db_session, team_data)
                summary["teams"] += 1
            else:
                logger.warning(
                    "No team data found for team name: '%s'", team_name
                )

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
    logger.info("Finished processing matches for tournament '%s'", slug)


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
    async with aiohttp.ClientSession() as http_session:
        client = LeaguepediaClient(http_session)
        async with get_async_session() as db_session:
            for slug in tournament_slugs:
                await _sync_single_tournament(
                    slug, client, db_session, summary
                )
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
        Performs a full sync of tournaments, matches, and teams from
        Leaguepedia based on the configured tournament slugs.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        summary = await perform_leaguepedia_sync()

        if summary is None:
            await interaction.followup.send(
                "Sync could not be completed. This may be because the "
                "configuration file was not found or was empty. "
                "Check logs for more details.",
                ephemeral=True,
            )
            return

        summary_message = (
            "Leaguepedia sync complete!\n"
            f"- Upserted {summary['contests']} contests.\n"
            f"- Upserted {summary['matches']} matches.\n"
            f"- Upserted {summary['teams']} teams."
        )
        await interaction.followup.send(summary_message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncLeaguepedia(bot))

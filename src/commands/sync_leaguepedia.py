import json
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from datetime import datetime, timezone

from src.auth import is_admin
from src.leaguepedia_client import LeaguepediaClient
from src.db import get_async_session
from src.crud import upsert_contest, upsert_match, upsert_team

CONFIG_PATH = Path("data/tournaments.json")


class SyncLeaguepedia(commands.Cog):
    """A cog for syncing data from Leaguepedia."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _parse_date(self, date_str: str | None) -> datetime | None:
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
        self, slug: str, client: LeaguepediaClient, db_session, summary: dict
    ):
        """Helper to sync data for a single tournament slug."""
        contest_data = await client.get_tournament_by_slug(slug)
        if not contest_data:
            return

        contest = await upsert_contest(
            db_session,
            {
                "leaguepedia_id": slug,
                "name": contest_data.get("Name"),
                "start_date": self._parse_date(contest_data.get("DateStart")),
                "end_date": self._parse_date(contest_data.get("DateEnd")),
            },
        )
        summary["contests"] += 1
        await db_session.flush()

        matches_data = await client.get_matches_for_tournament(slug)
        for match_data in matches_data:
            for team_name_key in ["Team1", "Team2"]:
                team_name = match_data.get(team_name_key)
                if not team_name:
                    continue
                team_api_data = await client.get_team(team_name)
                if team_api_data:
                    team_data = {
                        "leaguepedia_id": team_name,
                        "name": team_api_data.get("Name"),
                        "image_url": team_api_data.get("Image"),
                        "roster": json.dumps(team_api_data.get("Roster")),
                    }
                    await upsert_team(db_session, team_data)
                    summary["teams"] += 1

            await upsert_match(
                db_session,
                {
                    "leaguepedia_id": match_data.get("MatchId"),
                    "contest_id": contest.id,
                    "team1": match_data.get("Team1"),
                    "team2": match_data.get("Team2"),
                    "scheduled_time": self._parse_date(
                        match_data.get("DateTime_UTC")
                    ),
                },
            )
            summary["matches"] += 1

    @app_commands.command(
        name="sync-leaguepedia",
        description="Syncs configured tournaments from Leaguepedia.",
    )
    @app_commands.check(is_admin)
    async def sync_leaguepedia(self, interaction: discord.Interaction):
        """
        Performs a full sync of tournaments, matches, and teams from
        Leaguepedia based on the configured tournament slugs.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            with open(CONFIG_PATH, "r") as f:
                tournament_slugs = json.load(f)
        except FileNotFoundError:
            await interaction.followup.send(
                "Configuration file not found. "
                "Please add tournaments first using `/configure-sync add`."
            )
            return

        if not tournament_slugs:
            await interaction.followup.send(
                "No tournaments configured for sync. "
                "Please add some using `/configure-sync add`."
            )
            return

        summary = {"contests": 0, "matches": 0, "teams": 0}
        async with aiohttp.ClientSession() as http_session:
            client = LeaguepediaClient(http_session)
            async with get_async_session() as db_session:
                for slug in tournament_slugs:
                    await self._sync_single_tournament(
                        slug, client, db_session, summary
                    )
                await db_session.commit()

        summary_message = (
            "Leaguepedia sync complete!\n"
            f"- Upserted {summary['contests']} contests.\n"
            f"- Upserted {summary['matches']} matches.\n"
            f"- Upserted {summary['teams']} teams."
        )
        await interaction.followup.send(summary_message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncLeaguepedia(bot))

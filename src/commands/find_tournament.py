import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from src.leaguepedia_client import LeaguepediaClient


class TournamentSelect(discord.ui.Select):
    def __init__(self, tournaments: list[dict]):
        options = []
        for t in tournaments:
            label = t.get("Name", "Unknown Tournament")
            # Truncate label if it's too long for Discord options
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(
                discord.SelectOption(
                    label=label,
                    description=f"Slug: {t.get('OverviewPage', 'N/A')}",
                    value=t.get("OverviewPage"),
                )
            )

        super().__init__(
            placeholder="Select a tournament to get its slug...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        slug = self.values[0]
        await interaction.response.send_message(
            f"The slug for the selected tournament is:\n```\n{slug}\n```\n"
            f"You can now use `/configure-sync add slug:{slug}` to add it.",
            ephemeral=True,
        )


class TournamentView(discord.ui.View):
    def __init__(self, tournaments: list[dict]):
        super().__init__(timeout=180)
        self.add_item(TournamentSelect(tournaments))


class FindTournament(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="find-tournament",
        description="Search for a tournament on Leaguepedia to find its slug.",
    )
    async def find_tournament(
        self, interaction: discord.Interaction, search_query: str
    ):
        await interaction.response.defer(ephemeral=True)

        async with aiohttp.ClientSession() as session:
            client = LeaguepediaClient(session)
            tournaments = await client.search_tournaments_by_name(search_query)

        if not tournaments:
            await interaction.followup.send(
                f"No tournaments found for query: `{search_query}`.",
                ephemeral=True,
            )
            return

        view = TournamentView(tournaments)
        await interaction.followup.send(
            "Found the following tournaments. Select one to get its slug:",
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(FindTournament(bot))

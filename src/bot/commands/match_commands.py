import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from src.bot.views.match_views import MatchPicksView, MatchesView
import logging

logger = logging.getLogger('bot.matches')

class MatchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot')

    @app_commands.command(name="pick", description="Make picks for upcoming matches")
    @app_commands.guild_only()
    async def pick(self, interaction: discord.Interaction):
        logger.info(f"Pick command used by {interaction.user}")
        try:
            guild_id = interaction.guild_id
            upcoming_matches = self.bot.db.get_upcoming_matches(hours=48)

            if not upcoming_matches:
                embed = discord.Embed(
                    title="No Active Matches",
                    description="No matches available for picks in the next 48 hours.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            active_matches = [m for m in upcoming_matches if m[4] == 1]
            view = MatchPicksView(guild_id, active_matches, self.bot.db)
            embed = view.create_pick_embed()
            logger.info(f"Generated pick view for {interaction.user}")
            await interaction.response.send_message(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error processing pick command: {e}", exc_info=True)
            await interaction.response.send_message("An error occurred while processing your pick.", ephemeral=True)

    @app_commands.command(name="matches", description="Show matches by day")
    async def matches(self, interaction: discord.Interaction):
        logger.info(f"Matches command used by {interaction.user}")
        try:
            all_matches = self.bot.db.get_all_matches()

            if not all_matches:
                await interaction.response.send_message("No matches found.", ephemeral=True)
                return

            matches_by_day = {}
            for match in all_matches:
                match_date = datetime.strptime(str(match[4]), '%Y-%m-%d %H:%M:%S').date()
                if match_date not in matches_by_day:
                    matches_by_day[match_date] = []
                matches_by_day[match_date].append(match)

            current_date = datetime.now()
            dates = sorted(matches_by_day.keys())
            nearest_date = min(dates, key=lambda x: abs((x - current_date.date()).days))
            current_date = datetime.combine(nearest_date, datetime.min.time())

            view = MatchesView(matches_by_day, current_date)
            initial_embed = view.create_matches_embed()
            logger.info("Generated matches view")
            await interaction.response.send_message(embed=initial_embed, view=view)
        except Exception as e:
            logger.error(f"Error displaying matches: {e}", exc_info=True)
            await interaction.response.send_message("An error occurred while fetching matches.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MatchCommands(bot))

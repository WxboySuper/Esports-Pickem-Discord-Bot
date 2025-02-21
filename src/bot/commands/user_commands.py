import discord
import logging
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from src.bot.views.leaderboard_views import LeaderboardView
from src.bot.views.summary_views import SummaryView

class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot')

    @app_commands.command(name="stats", description="View your pick'em statistics")
    @app_commands.guild_only()
    async def stats(self, interaction: discord.Interaction):
        user_stats = self.bot.db.get_user_stats(interaction.guild_id, interaction.user.id)
        completed_ratio = f"{user_stats['correct_picks']}/{user_stats['completed_picks']}"

        embed = discord.Embed(
            title="Your Pick'em Stats",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Picks", value=str(user_stats["total_picks"]))
        embed.add_field(name="Completed Matches", value=completed_ratio)
        embed.add_field(name="Accuracy", value=f"{user_stats['accuracy']:.1%}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View the server's leaderboard")
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction):
        view = LeaderboardView(interaction.guild_id, interaction.guild.name, self.bot.db)
        initial_embed = await view.create_leaderboard_embed(interaction.guild)
        await interaction.response.send_message(embed=initial_embed, view=view)

    @app_commands.command(name="activepicks", description="View your active picks for upcoming matches")
    @app_commands.guild_only()
    async def activepicks(self, interaction: discord.Interaction):
        active_picks = self.bot.db.get_active_picks(interaction.guild_id, interaction.user.id)

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Active Picks",
            color=discord.Color.blue()
        )

        if not active_picks:
            embed.description = "No active picks for upcoming matches."
        else:
            embed.description = f"Currently has {len(active_picks)} active picks"
            for pick in active_picks:
                _, team_a, team_b, match_date, picked_team, league_name, league_region, match_name = pick
                match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

                embed.add_field(
                    name=f"{league_name} - {match_datetime.strftime('%B %d, %Y %I:%M %p')}",
                    value=f"🏆 {team_a} vs {team_b}\n"
                          f"Your Pick: **{picked_team}**\n"
                          f"📊 {match_name}",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="summary", description="View your daily Pick'em summary")
    @app_commands.guild_only()
    async def summary(self, interaction: discord.Interaction):
        matches = self.bot.db.get_all_matches()
        if not matches:
            await interaction.response.send_message("No matches found.", ephemeral=True)
            return

        matches_by_day = {}
        for match in matches:
            match_date = datetime.strptime(str(match[4]), '%Y-%m-%d %H:%M:%S').date()
            if match_date not in matches_by_day:
                matches_by_day[match_date] = []
            matches_by_day[match_date].append(match)

        current_date = datetime.now()
        dates = sorted(matches_by_day.keys())
        nearest_date = min(dates, key=lambda x: abs((x - current_date.date()).days))
        current_date = datetime.combine(nearest_date, datetime.min.time())

        view = SummaryView(interaction.user.id, interaction.guild_id, matches_by_day,
                          self.bot.db, current_date)
        initial_embed = view.create_summary_embed()
        await interaction.response.send_message(embed=initial_embed, view=view)

async def setup(bot):
    await bot.add_cog(UserCommands(bot))

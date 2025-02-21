import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import logging
from src.bot.utils.datetime_utils import parse_datetime, ensure_datetime
from src.bot.views.admin_views import AdminSummaryView, AnnouncementConfirmView

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot')

    @app_commands.command(name="admin_summary", description="View administrative summary [Owner Only]")
    async def admin_summary(self, interaction: discord.Interaction):
        if interaction.user.id != self.bot.config.OWNER_ID:
            await interaction.response.send_message("❌ Owner only command!", ephemeral=True)
            return

        try:
            all_matches = self.bot.db.get_all_matches()
            matches_by_day = {}
            for match in all_matches:
                match_date = datetime.strptime(str(match[4]), '%Y-%m-%d %H:%M:%S').date()
                if match_date not in matches_by_day:
                    matches_by_day[match_date] = []
                matches_by_day[match_date].append(match)

            if not matches_by_day:
                await interaction.response.send_message("No matches found.", ephemeral=True)
                return

            current_date = datetime.now()
            dates = sorted(matches_by_day.keys())
            nearest_date = min(dates, key=lambda x: abs((x - current_date.date()).days))
            current_date = datetime.combine(nearest_date, datetime.min.time())

            view = AdminSummaryView(matches_by_day, current_date)
            initial_embed = view.create_admin_summary_embed()
            await interaction.response.send_message(embed=initial_embed, view=view, ephemeral=True)

        except Exception as e:
            logging.error("Error in admin summary: %s", e)
            await interaction.response.send_message("An error occurred", ephemeral=True)

    @app_commands.command(name="create_match", description="Create a new match [Owner Only]")
    @app_commands.describe(
        team_a="Name of the first team",
        team_b="Name of the second team",
        match_date="Match date (format: YYYY-MM-DD)",
        match_time="Match time (format: HH:MM AM/PM)",
        match_name="Match type (e.g., Groups, Playoffs, Finals)",
        league_name="Name of the league"
    )
    async def create_match(self, interaction: discord.Interaction, team_a: str, team_b: str,
                          match_date: str, match_time: str, match_name: str, league_name: str = "Unknown League"):
        if interaction.user.id != self.bot.config.OWNER_ID:
            await interaction.response.send_message("❌ Owner only command!", ephemeral=True)
            return

        try:
            date_obj = parse_datetime(match_date, match_time)
            is_active = 0 if team_a == "TBD" or team_b == "TBD" else 1
            match_id = self.bot.db.add_match(1, team_a, team_b, date_obj, is_active, match_name)

            if match_id:
                embed = discord.Embed(title="✅ Match Created", color=discord.Color.green())
                embed.add_field(name="Match ID", value=str(match_id))
                embed.add_field(name="Teams", value=f"{team_a} vs {team_b}")
                embed.add_field(name="Date/Time", value=f"{match_date} {match_time}")
                await interaction.response.send_message(embed=embed)

                await self.bot.announcer.announce_new_match(
                    match_id, team_a, team_b, date_obj, league_name, match_name
                )
            else:
                await interaction.response.send_message("❌ Failed to create match", ephemeral=True)

        except Exception as e:
            self.logger.error("Error creating match: %s", e)
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @app_commands.command(name="update_match", description="Update match details [Owner Only]")
    @app_commands.describe(
        match_id="ID of the match to update",
        team_a="New name for team A (or 'keep' to keep current)",
        team_b="New name for team B (or 'keep' to keep current)",
        match_date="New match date (YYYY-MM-DD or 'keep')",
        match_time="New match time (HH:MM AM/PM or 'keep')",
        match_name="New match type (or 'keep' to keep current)"
    )
    async def update_match(self, interaction: discord.Interaction, match_id: int, team_a: str,
                          team_b: str, match_date: str, match_time: str, match_name: str):
        if interaction.user.id != self.bot.config.OWNER_ID:
            await interaction.response.send_message("❌ Owner only command!", ephemeral=True)
            return

        try:
            old_details = self.bot.db.get_match_details(match_id)
            if not old_details:
                await interaction.response.send_message("❌ Match not found!", ephemeral=True)
                return

            new_details = old_details.copy()

            # Update details based on provided values
            if team_a.lower() != 'keep':
                new_details['team_a'] = team_a
            if team_b.lower() != 'keep':
                new_details['team_b'] = team_b
            if match_date.lower() != 'keep' and match_time.lower() != 'keep':
                new_details['match_date'] = parse_datetime(match_date, match_time)
            if match_name.lower() != 'keep':
                new_details['match_name'] = match_name

            success = self.bot.db.update_match(
                match_id,
                new_details['team_a'],
                new_details['team_b'],
                new_details['match_date'],
                new_details['match_name']
            )

            if success:
                await self.bot.announcer.announce_match_update(
                    match_id, old_details, new_details, old_details['league_name']
                )
                await interaction.response.send_message("✅ Match updated successfully!")
            else:
                await interaction.response.send_message("❌ Failed to update match", ephemeral=True)

        except Exception as e:
            self.logger.error("Error updating match: %s", e)
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @app_commands.command(name="set_winner", description="Set the winner for a match [Owner Only]")
    async def set_winner(self, interaction: discord.Interaction, match_id: int, winner: str):
        if interaction.user.id != self.bot.config.OWNER_ID:
            await interaction.response.send_message("❌ Owner only command!", ephemeral=True)
            return

        try:
            match_details = self.bot.db.get_match_details(match_id)
            if not match_details:
                await interaction.response.send_message("❌ Match not found!", ephemeral=True)
                return

            success = self.bot.db.update_match_result(match_id, winner)
            if success:
                await interaction.response.send_message("✅ Winner set successfully!")
                await self.bot.announcer.announce_match_result(
                    match_id,
                    match_details['team_a'],
                    match_details['team_b'],
                    winner,
                    match_details['league_name']
                )
            else:
                await interaction.response.send_message("❌ Failed to set winner", ephemeral=True)

        except Exception as e:
            self.logger.error("Error setting winner: %s", e)
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))

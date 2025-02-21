from datetime import datetime
import discord
from discord import ui, ButtonStyle
from src.utils.db import PickemDB
from src.bot.utils.datetime_utils import get_discord_timestamp

class SummaryView(ui.View):
    def __init__(self, user_id: int, guild_id: int, matches_by_day: dict, db: PickemDB, current_date: datetime):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_id = user_id
        self.guild_id = guild_id
        self.matches = matches_by_day
        self.db = db
        self.current_date = current_date
        self.dates = sorted(matches_by_day.keys())
        self.current_index = self.dates.index(current_date.date())

        # Initialize button states
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

    @ui.button(label="◀️ Previous Day", style=ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    @ui.button(label="Next Day ▶️", style=ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index < len(self.dates) - 1:
            self.current_index += 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = self.create_summary_embed()
        
        # Update button states
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1
        
        await interaction.response.edit_message(embed=embed, view=self)

    def create_summary_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📊 Pick'em Summary for {self.current_date.strftime('%B %d, %Y')}",
            color=discord.Color.blue()
        )

        current_matches = self.matches[self.dates[self.current_index]]
        
        if not current_matches:
            embed.description = "No matches scheduled for this day."
            return embed

        # Initialize counters
        total_matches = len(current_matches)
        unpicked_matches = 0
        completed_matches = 0
        pending_matches = 0
        correct_picks = 0

        for match in current_matches:
            match_id, team_a, team_b, winner, match_date, _, league_name, league_region, match_name = match
            match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

            # Get user's pick for this match
            user_pick = self.db.get_user_pick(self.guild_id, self.user_id, match_id)

            # Determine match status and format field
            if winner:  # Completed match
                completed_matches += 1
                status = "✅ Correct!" if user_pick == winner else "❌ Incorrect"
                if user_pick == winner:
                    correct_picks += 1
                pick_str = f"You picked: **{user_pick}**\nWinner: ||{winner}||"
            elif match_datetime <= datetime.now():  # Ongoing match
                pending_matches += 1
                status = "🔄 In Progress"
                pick_str = f"You picked: **{user_pick}**" if user_pick else "❌ No pick made"
            else:  # Future match
                if not user_pick:
                    unpicked_matches += 1
                status = "⏰ Upcoming"
                pick_str = f"You picked: **{user_pick}**" if user_pick else "❌ No pick made"

            embed.add_field(
                name=f"{league_name} - {get_discord_timestamp(match_datetime, 'T')}",
                value=(
                    f"🏆 **{team_a}** vs **{team_b}**\n"
                    f"📊 {match_name}\n"
                    f"🌍 {league_region}\n"
                    f"📊 {status}\n"
                    f"🎯 {pick_str}"
                ),
                inline=False
            )

        # Add summary statistics
        stats = (
            f"Total Matches: {total_matches}\n"
            f"Completed: {completed_matches} "
            f"({correct_picks}/{completed_matches} correct)\n"
            f"In Progress: {pending_matches}\n"
            f"Upcoming (unpicked): {unpicked_matches}"
        )

        embed.description = stats
        return embed

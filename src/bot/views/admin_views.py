from datetime import datetime
import discord
from discord import ui, ButtonStyle
from src.bot.utils.datetime_utils import get_discord_timestamp

class AdminSummaryView(ui.View):
    def __init__(self, matches_by_day: dict, current_date: datetime):
        super().__init__(timeout=300)
        self.matches = matches_by_day
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
        """Update the message with current day's admin summary"""
        embed = self.create_admin_summary_embed()

        # Update button states
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

        await interaction.response.edit_message(embed=embed, view=self)

    def create_admin_summary_embed(self) -> discord.Embed:
        """Create embed for admin summary"""
        current_matches = self.matches[self.dates[self.current_index]]

        embed = discord.Embed(
            title=f"🔧 Admin Summary for {self.current_date.strftime('%B %d, %Y')}",
            color=discord.Color.dark_blue()
        )

        if not current_matches:
            embed.description = "No matches scheduled for this day."
            return embed

        for match in current_matches:
            match_id, team_a, team_b, winner, match_date, _, league_name, _, match_name = match
            match_time = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

            # Determine match status
            status = "🟢 Open" if not winner else "🔴 Closed"
            if match_time <= datetime.now():
                status = "🟡 In Progress" if not winner else "🔴 Completed"

            embed.add_field(
                name=f"`{match_id}` • {status}",
                value=(
                    f"🏆 {team_a} vs {team_b}\n"
                    f"⏰ {get_discord_timestamp(match_time, 'T')}\n"
                    f"📍 {league_name}\n"
                    f"📊 {match_name}\n"
                    f"{'✅ Winner: ' + winner if winner else '❌ No Winner Set'}"
                ),
                inline=False
            )

        embed.set_footer(text="/update_match <id> - Edit match details\n/set_winner <id> - Set match winner")
        return embed

class AnnouncementConfirmView(ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.value = None

    @ui.button(label="Send", style=ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        """Confirm sending the announcement"""
        self.value = True
        self.stop()
        await interaction.response.defer()

    @ui.button(label="Cancel", style=ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel sending the announcement"""
        self.value = False
        self.stop()
        await interaction.response.defer()

from datetime import datetime
import discord
from discord import ui, ButtonStyle
from src.utils.db import PickemDB

class LeaderboardView(ui.View):
    def __init__(self, guild_id: int, guild_name: str, db: PickemDB):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.db = db
        self.current_timeframe = 'all'

    @ui.button(label="Daily", style=ButtonStyle.primary)
    async def daily_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_timeframe = 'daily'
        await self.update_leaderboard(interaction)

    @ui.button(label="Weekly", style=ButtonStyle.primary)
    async def weekly_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_timeframe = 'weekly'
        await self.update_leaderboard(interaction)

    @ui.button(label="All-Time", style=ButtonStyle.primary)
    async def alltime_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_timeframe = 'all'
        await self.update_leaderboard(interaction)

    async def update_leaderboard(self, interaction: discord.Interaction):
        embed = await self.create_leaderboard_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def create_leaderboard_embed(self, guild) -> discord.Embed:
        timeframe_titles = {
            'daily': "Today's",
            'weekly': "This Week's",
            'all': "All-Time"
        }

        embed = discord.Embed(
            title=f"📊 {timeframe_titles[self.current_timeframe]} {guild.name} Leaderboard",
            color=discord.Color.blue()
        )

        leaderboard_data = self.db.get_leaderboard_by_timeframe(self.guild_id, self.current_timeframe)
        print(leaderboard_data)
        
        if not leaderboard_data:
            embed.description = f"No picks found for {timeframe_titles[self.current_timeframe].lower()} leaderboard!"
            return embed

        for rank, data in enumerate(leaderboard_data, 1):
            if self.current_timeframe == 'all':
                user_id, completed_picks, correct_picks, accuracy = data
            else:
                user_id, completed_picks, correct_picks, accuracy = data

            member = guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"

            medal = "🥇 " if rank == 1 else "🥈 " if rank == 2 else "🥉 " if rank == 3 else ""
            value = f"✅ Accuracy: {accuracy:.1%} ({correct_picks}/{completed_picks})"

            embed.add_field(
                name=f"{medal}#{rank} - {name}",
                value=value,
                inline=False
            )

        return embed

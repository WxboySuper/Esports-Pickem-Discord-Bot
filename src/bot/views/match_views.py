import logging
from datetime import datetime
import discord
from discord import ui, ButtonStyle
from src.utils.db import PickemDB
from src.bot.utils.datetime_utils import get_discord_timestamp

logger = logging.getLogger('bot.views')

class MatchPicksView(ui.View):
    def __init__(self, guild_id: int, matches: list, db: PickemDB):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.matches = matches
        self.db = db
        self.current_index = 0
        self.update_buttons()
        logger.debug(f"Created pick view for guild {guild_id} with {len(matches)} matches")

    def update_buttons(self):
        """Update navigation and team buttons based on current match"""
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.matches) - 1

        # Remove old team buttons
        for child in self.children[:]:
            if isinstance(child, ui.Button) and child.custom_id and child.custom_id.startswith("pick_"):
                self.remove_item(child)

        # Get current match
        current_match = self.matches[self.current_index]
        match_id, team_a, team_b = current_match[0], current_match[1], current_match[2]

        # Create unique custom_ids by including the current_index
        team_a_button = ui.Button(
            label=team_a,
            style=ButtonStyle.primary,
            custom_id=f"pick_{match_id}_{self.current_index}_a"
        )
        team_b_button = ui.Button(
            label=team_b,
            style=ButtonStyle.primary,
            custom_id=f"pick_{match_id}_{self.current_index}_b"
        )

        # Update the callbacks
        team_a_button.callback = lambda i: self.pick_callback(i, team_a)
        team_b_button.callback = lambda i: self.pick_callback(i, team_b)

        self.add_item(team_a_button)
        self.add_item(team_b_button)

    async def pick_callback(self, interaction: discord.Interaction, team: str):
        """Handle team selection"""
        current_match = self.matches[self.current_index]
        match_id = current_match[0]

        logger.info(f"User {interaction.user} picked {team} for match {match_id}")
        try:
            success = self.db.make_pick(self.guild_id, interaction.user.id, match_id, team)
            if success:
                await interaction.response.send_message(f"You picked {team}!", ephemeral=True)
                logger.info(f"Recorded pick for user {interaction.user.id}")
            else:
                await interaction.response.send_message(
                    "Failed to record pick. Match might have already started or finished.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error recording pick: {e}", exc_info=True)
            await interaction.response.send_message("Failed to record your pick.", ephemeral=True)

    @ui.button(label="◀️ Previous Match", style=ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_buttons()
            await self.update_message(interaction)

    @ui.button(label="Next Match ▶️", style=ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index < len(self.matches) - 1:
            self.current_index += 1
            self.update_buttons()
            await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        """Update the message with current match details"""
        embed = self.create_pick_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_pick_embed(self) -> discord.Embed:
        """Create embed for current match"""
        current_match = self.matches[self.current_index]
        match_id, team_a, team_b, match_date, is_active, league_name, league_region, match_name = current_match
        match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

        embed = discord.Embed(
            title=f"🎮 {league_name} - Match {self.current_index + 1}/{len(self.matches)}",
            description=(
                f"📅 {get_discord_timestamp(match_datetime, 'F')}\n"
                f"⏰ Time until match: {get_discord_timestamp(match_datetime, 'R')}\n"
                f"🌍 {league_region}\n"
                f"📊 {match_name}\n\n"
                f"**{team_a}** vs **{team_b}**"
            ),
            color=discord.Color.blue()
        )
        return embed

class MatchesView(ui.View):
    def __init__(self, matches_by_day: dict, current_date: datetime):
        super().__init__(timeout=300)
        self.matches = matches_by_day
        self.current_date = current_date
        self.dates = sorted(matches_by_day.keys())
        self.current_index = self.dates.index(current_date.date())
        logger.debug(f"Created matches view with {len(matches_by_day)} days of matches")

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
        """Update the message with current day's matches"""
        logger.debug(f"Updating matches view to date {self.current_date}")
        try:
            embed = self.create_matches_embed()

            # Update button states
            self.previous_button.disabled = self.current_index == 0
            self.next_button.disabled = self.current_index == len(self.dates) - 1

            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error updating matches view: {e}", exc_info=True)

    def create_matches_embed(self) -> discord.Embed:
        """Create embed for current day's matches"""
        current_matches = self.matches[self.dates[self.current_index]]

        embed = discord.Embed(
            title=f"🎮 Matches for {self.current_date.strftime('%B %d, %Y')}",
            color=discord.Color.blue()
        )

        if not current_matches:
            embed.description = "No matches scheduled for this day."
            return embed

        for match in current_matches:
            match_id, team_a, team_b, winner, match_date, _, league_name, league_region, match_name = match
            match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

            status = f"Winner: ||{winner}||" if winner else (
                "Match Ongoing" if match_datetime <= datetime.now()
                else f"Starts {get_discord_timestamp(match_datetime, 'R')}"
            )

            embed.add_field(
                name=f"{league_name} - {get_discord_timestamp(match_datetime, 'T')}",
                value=(
                    f"🏆 {team_a} vs {team_b}\n"
                    f"📊 {match_name}\n"
                    f"🌍 {league_region}\n"
                    f"📅 {status}"
                ),
                inline=False
            )

        return embed

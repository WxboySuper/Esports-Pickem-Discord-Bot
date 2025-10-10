# src/commands/leaderboard.py

import logging
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from sqlalchemy import func
from sqlmodel import Session, select

from src.db import get_session
from src.models import Contest, Pick, User
from src import crud

logger = logging.getLogger("esports-bot.commands.leaderboard")


# --- Helper Functions ---


async def get_leaderboard_data(
    session: Session,
    days: int = None,
    guild_id: int = None,
    contest_id: int = None,
) -> list[tuple[User, int]]:
    """Fetches and calculates leaderboard data based on the given criteria."""
    query = select(User, func.sum(Pick.score).label("total_score")).join(Pick)

    if days:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.where(Pick.timestamp >= start_date)

    if contest_id:
        query = query.where(Pick.contest_id == contest_id)

    # Guild filtering would require storing guild_id on User or Pick.
    # For now, we'll simulate it by fetching all and then filtering.
    # This is not efficient for large datasets.

    query = query.group_by(User.id).order_by(func.sum(Pick.score).desc())

    results = session.exec(query).all()

    # In a real-world scenario with sharding or many guilds,
    # you would need to store guild information in the database.
    # For this example, we assume the bot is in a manageable number of guilds
    # and can fetch members.
    if guild_id:
        try:
            guild = await bot.fetch_guild(guild_id)
            guild_member_ids = {str(m.id) for m in guild.members}
            results = [
                (user, score)
                for user, score in results
                if user.discord_id in guild_member_ids
            ]
        except (discord.NotFound, discord.Forbidden):
            logger.warning(f"Could not fetch members for guild {guild_id}")

    return results


async def create_leaderboard_embed(
    title: str, leaderboard_data: list, interaction: discord.Interaction
) -> discord.Embed:
    """Creates a standardized embed for leaderboards."""
    embed = discord.Embed(
        title=title,
        color=discord.Color.dark_gold(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(
        name=interaction.user.display_name,
        icon_url=(interaction.user.avatar.url if interaction.user.avatar else None),
    )

    if not leaderboard_data:
        embed.description = "The leaderboard is empty."
    else:
        lines = []
        for i, (user, score) in enumerate(leaderboard_data[:20], 1):  # Show top 20
            username = user.username or f"User ID: {user.discord_id}"
            lines.append(f"**{i}.** {username} - `{score or 0}` points")
        embed.description = "\n".join(lines)

    return embed


# --- Views ---


class LeaderboardView(discord.ui.View):
    """A view with buttons to switch between leaderboard types."""

    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.interaction = interaction

    async def update_leaderboard(
        self, interaction: discord.Interaction, period: str, days: int = None
    ):
        await interaction.response.defer()
        session: Session = next(get_session())
        guild_id = interaction.guild.id if period == "Server" else None

        # Update button styles
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == period:
                    item.style = discord.ButtonStyle.primary
                    item.disabled = True
                else:
                    item.style = discord.ButtonStyle.secondary
                    item.disabled = False

        data = await get_leaderboard_data(
            session,
            days=days,
            guild_id=guild_id,
        )
        title = f"{period} Leaderboard"
        embed = await create_leaderboard_embed(title, data, self.interaction)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Global", style=discord.ButtonStyle.primary)
    async def global_leaderboard(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.update_leaderboard(interaction, "Global")

    @discord.ui.button(label="Server", style=discord.ButtonStyle.secondary)
    async def server_leaderboard(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.update_leaderboard(interaction, "Server")

    @discord.ui.button(label="Weekly", style=discord.ButtonStyle.secondary)
    async def weekly_leaderboard(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.update_leaderboard(interaction, "Weekly", days=7)

    @discord.ui.button(label="Daily", style=discord.ButtonStyle.secondary)
    async def daily_leaderboard(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.update_leaderboard(interaction, "Daily", days=1)


class ContestSelectForLeaderboard(discord.ui.Select):
    """A dropdown to select a contest for the leaderboard."""

    def __init__(self, contests: list[Contest]):
        options = [
            discord.SelectOption(label=c.name, value=str(c.id)) for c in contests
        ]
        super().__init__(placeholder="Choose a contest...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        contest_id = int(self.values[0])
        session: Session = next(get_session())

        contest = crud.get_contest_by_id(session, contest_id)
        data = await get_leaderboard_data(session, contest_id=contest_id)
        title = f"Leaderboard for {contest.name}"
        embed = await create_leaderboard_embed(title, data, interaction)
        await interaction.edit_original_response(embed=embed, view=None)


# --- Commands ---


@app_commands.command(
    name="leaderboard",
    description="Displays the main leaderboards.",
)
async def leaderboard(interaction: discord.Interaction):
    """Shows the main leaderboard with view options."""
    logger.info(f"'{interaction.user.name}' requested the main leaderboard.")
    session: Session = next(get_session())

    # Default to global view
    data = await get_leaderboard_data(session)
    embed = await create_leaderboard_embed(
        "Global Leaderboard",
        data,
        interaction,
    )
    view = LeaderboardView(interaction)

    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True,
    )


@app_commands.command(
    name="leaderboard-contest",
    description="Displays the leaderboard for a specific contest.",
)
async def leaderboard_contest(interaction: discord.Interaction):
    """Shows a dropdown to select a contest leaderboard."""
    logger.info(f"'{interaction.user.name}' requested a contest leaderboard.")
    session: Session = next(get_session())
    contests = crud.list_contests(session)
    if not contests:
        await interaction.response.send_message(
            "No contests found.",
            ephemeral=True,
        )
        return

    view = discord.ui.View(timeout=180)
    view.add_item(ContestSelectForLeaderboard(contests=contests[:25]))
    await interaction.response.send_message(
        "Please select a contest:", view=view, ephemeral=True
    )


async def setup(bot_instance):
    global bot
    bot = bot_instance
    bot.tree.add_command(leaderboard)
    bot.tree.add_command(leaderboard_contest)

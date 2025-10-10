# src/commands/leaderboard.py

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Union

import discord
from discord import app_commands
from sqlalchemy import func, case, Float
from sqlmodel import Session, select

from src.db import get_session
from src.models import Contest, Pick, User
from src import crud

logger = logging.getLogger("esports-bot.commands.leaderboard")


MIN_PICKS_FOR_ACCURACY_LEADERBOARD = 5


# --- Helper Functions ---


LeaderboardData = Union[
    List[tuple[User, float, int]],  # Accuracy, Total Correct
    List[tuple[User, int]],  # Total Correct
]


async def get_leaderboard_data(
    session: Session,
    days: int = None,
    guild_id: int = None,
    contest_id: int = None,
) -> LeaderboardData:
    """
    Fetches and calculates leaderboard data based on the given criteria.

    - If 'days' or 'contest_id' is provided, it's a count-based leaderboard
      (total correct picks).
    - Otherwise, it's an accuracy-based leaderboard (Global/Server).
    """
    is_accuracy_based = not days and not contest_id

    if is_accuracy_based:
        # --- Accuracy-Based Leaderboard (Global/Server) ---
        total_correct = func.sum(case((Pick.status == "correct", 1), else_=0))
        total_resolved = func.sum(
            case((Pick.status.in_(["correct", "incorrect"]), 1), else_=0)
        )

        accuracy = case(
            (
                total_resolved > 0,
                (func.cast(total_correct, Float) / func.cast(total_resolved, Float))
                * 100,
            ),
            else_=0.0,
        ).label("accuracy")

        query = (
            select(User, accuracy, total_correct.label("total_correct"))
            .join(Pick)
            .where(Pick.status.in_(["correct", "incorrect"]))
            .group_by(User.id)
            .having(total_resolved >= MIN_PICKS_FOR_ACCURACY_LEADERBOARD)
            .order_by(accuracy.desc(), total_correct.label("total_correct").desc())
        )
    else:
        # --- Count-Based Leaderboard (Daily/Weekly/Contest) ---
        total_correct = func.count(Pick.id).label("total_correct")
        query = (
            select(User, total_correct)
            .join(Pick)
            .where(Pick.status == "correct")
        )

        if days:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.where(Pick.timestamp >= start_date)

        if contest_id:
            query = query.where(Pick.contest_id == contest_id)

        query = query.group_by(User.id).order_by(total_correct.desc())

    results = session.exec(query).all()

    # Guild filtering logic. This is inefficient for large bots but matches
    # the existing implementation's approach.
    if guild_id:
        try:
            # The 'bot' global is initialized in the setup function.
            guild = await bot.fetch_guild(guild_id)
            guild_member_ids = {str(m.id) for m in guild.members}

            if is_accuracy_based:
                results = [
                    (user, acc, total)
                    for user, acc, total in results
                    if user.discord_id in guild_member_ids
                ]
            else:
                results = [
                    (user, score)
                    for user, score in results
                    if user.discord_id in guild_member_ids
                ]
        except (discord.NotFound, discord.Forbidden):
            logger.warning(f"Could not fetch members for guild {guild_id}")

    return results


async def create_leaderboard_embed(
    title: str, leaderboard_data: LeaderboardData, interaction: discord.Interaction
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
        return embed

    lines = []
    # Check the type of the first element to determine the leaderboard type
    is_accuracy_based = isinstance(leaderboard_data[0], tuple) and len(
        leaderboard_data[0]
    ) == 3

    for i, entry in enumerate(leaderboard_data[:20], 1):  # Show top 20
        username = entry[0].username or f"User ID: {entry[0].discord_id}"
        if is_accuracy_based:
            # entry is (User, accuracy, total_correct)
            accuracy = entry[1]
            lines.append(f"**{i}.** {username} - `{accuracy:.2f}%` accuracy")
        else:
            # entry is (User, total_correct)
            total_correct = entry[1]
            plural = "s" if total_correct != 1 else ""
            lines.append(
                f"**{i}.** {username} - `{total_correct}` correct pick{plural}"
            )

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

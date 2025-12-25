# src/commands/leaderboard.py

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Union

import discord
from discord import app_commands
from sqlalchemy import func, case
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


def _get_pick_correct_attr():
    """Return the attribute on Pick that represents correctness.

    Tries common names so this file doesn't hard-fail if the field name
    differs slightly across schema versions.
    """
    for name in ("correct", "is_correct", "was_correct"):
        if hasattr(Pick, name):
            return getattr(Pick, name)
    raise AttributeError("Pick model has no attribute indicating correctness")


def _build_accuracy_query():
    """Build a query that returns (User, accuracy_percent, total_correct).

    Accuracy is returned as a percentage (0-100). Only users with at least
    MIN_PICKS_FOR_ACCURACY_LEADERBOARD picks are included.
    """
    correct_attr = _get_pick_correct_attr()
    total_picks = func.count(getattr(Pick, "id"))
    total_correct = func.sum(case((correct_attr.is_(True), 1), else_=0))
    # accuracy as percentage
    accuracy = (total_correct * 100.0) / total_picks

    query = (
        select(
            User,
            accuracy.label("accuracy"),
            total_correct.label("total_correct"),
        )
        .join(Pick, getattr(Pick, "user_id") == User.id)
        .group_by(User.id)
        .having(total_picks >= MIN_PICKS_FOR_ACCURACY_LEADERBOARD)
        .order_by(accuracy.desc())
    )
    return query


def _build_count_query(days: int = None, contest_id: int = None):
    """
    Build a query that returns (User, total_correct),
    filtered by time/contest.
    """
    correct_attr = _get_pick_correct_attr()
    total_correct = func.sum(
        case((correct_attr.is_(True), 1), else_=0)
    )

    query = select(User, total_correct.label("total_correct")).join(
        Pick, getattr(Pick, "user_id") == User.id
    )

    # Apply optional filters
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        if hasattr(Pick, "created_at"):
            query = query.where(getattr(Pick, "created_at") >= cutoff)
    if contest_id is not None and hasattr(Pick, "contest_id"):
        query = query.where(getattr(Pick, "contest_id") == contest_id)

    query = query.group_by(User.id).order_by(total_correct.desc())
    return query


def _passes_guild(user, guild_id: int) -> bool:
    if guild_id is None:
        return True
    ug = getattr(user, "guild_id", None) or getattr(user, "server_id", None)
    # If we're filtering by a specific guild, only include users who
    # are associated with that guild (i.e. have a guild/server id that
    # matches). Previously users with no guild_id were incorrectly
    # included when a guild filter was applied.
    return ug is not None and ug == guild_id


def _normalize_row(row):
    if isinstance(row, tuple):
        return row
    try:
        return tuple(row)
    except Exception:
        return (row,)


def _to_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default


def _to_int(val, default=0):
    try:
        return int(val)
    except Exception:
        return default


def _parse_accuracy_row(t: tuple):
    """Parse an accuracy-based leaderboard tuple into (User, accuracy, total)."""
    raw_accuracy = t[1] if len(t) > 1 else None
    accuracy = _to_float(raw_accuracy, default=0.0)

    # Normalize fractions (0-1) to percentage (0-100)
    if 0.0 <= accuracy <= 1.0:
        accuracy = accuracy * 100.0

    # Clamp to sensible bounds
    if accuracy < 0.0:
        accuracy = 0.0
    elif accuracy > 100.0:
        accuracy = 100.0

    total = _to_int(t[2]) if len(t) > 2 and t[2] is not None else 0
    if total < 0:
        total = 0
    return (t[0], accuracy, total)


def _parse_count_row(t: tuple):
    """Parse a count-based leaderboard tuple into (User, total)."""
    total = _to_int(t[1]) if len(t) > 1 and t[1] is not None else 0
    if total < 0:
        total = 0
    return (t[0], total)


def _parse_row(tup, is_accuracy_based: bool):
    """Return a normalized leaderboard tuple or None on parse failure.

    For accuracy-based: (User, accuracy: float, total_correct: int)
    For count-based: (User, total_correct: int)
    """
    if not tup:
        return None
    user = tup[0]
    if user is None:
        return None

    return _parse_accuracy_row(tup) if is_accuracy_based else _parse_count_row(tup)


async def _apply_guild_filter(results, guild_id: int, is_accuracy_based: bool):
    """Normalize DB results into LeaderboardData and apply optional guild filter.

    This version delegates parsing and simple checks to small helpers to
    reduce cognitive complexity of the main loop.
    """
    processed = []
    for row in results:
        tup = _normalize_row(row)
        parsed = _parse_row(tup, is_accuracy_based)
        if parsed is None:
            continue

        user = parsed[0]
        if not _passes_guild(user, guild_id):
            continue

        processed.append(parsed)

    return processed


async def get_leaderboard_data(
    session: Session,
    days: int = None,
    guild_id: int = None,
    contest_id: int = None,
) -> LeaderboardData:
    # Decide leaderboard type
    is_accuracy_based = not days and not contest_id

    # Build appropriate query
    if is_accuracy_based:
        query = _build_accuracy_query()
    else:
        query = _build_count_query(days=days, contest_id=contest_id)

    results = session.exec(query).all()
    return await _apply_guild_filter(results, guild_id, is_accuracy_based)


async def create_leaderboard_embed(
    title: str,
    leaderboard_data: LeaderboardData,
    interaction: discord.Interaction,
) -> discord.Embed:
    """Creates a standardized embed for leaderboards."""
    embed = discord.Embed(
        title=title,
        color=discord.Color.dark_gold(),
        timestamp=datetime.now(timezone.utc),
    )
    icon_url = interaction.user.avatar.url if interaction.user.avatar else None
    embed.set_author(name=interaction.user.display_name, icon_url=icon_url)

    if not leaderboard_data:
        embed.description = "The leaderboard is empty."
        return embed

    # Build description from leaderboard entries
    lines = []
    is_accuracy_based = _is_accuracy_based_data(leaderboard_data)

    for i, entry in enumerate(leaderboard_data[:20], 1):
        if is_accuracy_based:
            lines.append(_format_accuracy_entry(entry, i))
        else:
            lines.append(_format_count_entry(entry, i))

    embed.description = "\n".join(lines)
    return embed


def _is_accuracy_based_data(leaderboard_data: LeaderboardData) -> bool:
    """Return True when leaderboard entries are accuracy tuples."""
    first = leaderboard_data[0]
    return isinstance(first, tuple) and len(first) == 3


def _format_accuracy_entry(entry, index: int) -> str:
    user = entry[0]
    username = user.username or f"User ID: {user.discord_id}"
    accuracy = entry[1]
    return f"**{index}.** {username} - `{accuracy:.2f}%` accuracy"


def _format_count_entry(entry, index: int) -> str:
    user = entry[0]
    username = user.username or f"User ID: {user.discord_id}"
    total = entry[1]
    plural = "s" if total != 1 else ""
    return f"**{index}.** {username} - `{total}` correct pick{plural}"



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
        # Only attempt to read guild id if this interaction occurred in a guild
        guild_id = interaction.guild.id if (period == "Server" and interaction.guild is not None) else None

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
        embed = await create_leaderboard_embed(
            title,
            data,
            self.interaction,
        )
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
            discord.SelectOption(label=c.name, value=str(c.id))
            for c in contests
        ]
        super().__init__(placeholder="Choose a contest...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        contest_id = int(self.values[0])
        session: Session = next(get_session())

        contest = crud.get_contest_by_id(session, contest_id)
        data = await get_leaderboard_data(session, contest_id=contest_id)
        title = f"Leaderboard for {contest.name}"
        embed = await create_leaderboard_embed(
            title,
            data,
            interaction,
        )
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

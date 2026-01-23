# src/commands/picks.py

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from sqlmodel import select
from sqlalchemy.orm import selectinload

from src.db import get_session
from src.models import Match, Pick, Result
from src import crud

logger = logging.getLogger("esports-bot.commands.picks")


def _build_picks_embed(match: Match, picks: list[Pick]) -> discord.Embed:
    embed = discord.Embed(
        title=f"Picks for {match.team1} vs {match.team2}",
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    )

    if not picks:
        embed.description = "No picks have been submitted for this match yet."
        return embed

    team1_picks = []
    team2_picks = []
    for pick in picks:
        user_name = pick.user.username or f"User ID: {pick.user.discord_id}"
        if pick.chosen_team == match.team1:
            team1_picks.append(user_name)
        else:
            team2_picks.append(user_name)

    if team1_picks:
        embed.add_field(
            name=(f"Picks for {match.team1} " f"({len(team1_picks)})"),
            value="\n".join(team1_picks),
            inline=True,
        )
    if team2_picks:
        embed.add_field(
            name=(f"Picks for {match.team2} " f"({len(team2_picks)})"),
            value="\n".join(team2_picks),
            inline=True,
        )

    return embed


picks_group = app_commands.Group(
    name="picks", description="Commands for viewing picks."
)


@picks_group.command(
    name="view-active",
    description="View your active picks for upcoming matches.",
)
async def view_active(interaction: discord.Interaction):
    """Shows a user their own upcoming/active picks."""
    logger.info(
        "'%s' (%s) requested their active picks.",
        interaction.user.name,
        interaction.user.id,
    )
    with get_session() as session:
        db_user = crud.get_user_by_discord_id(
            session, str(interaction.user.id)
        )
        if not db_user:
            await interaction.response.send_message(
                "You have no active picks.", ephemeral=True
            )
            return

        now_utc = datetime.now(timezone.utc)
        # Get picks for matches that haven't started yet
        active_picks_stmt = (
            select(Pick)
            .join(Match)
            .where(Pick.user_id == db_user.id)
            .where(Match.scheduled_time > now_utc)
            .options(selectinload(Pick.match))
            .order_by(Match.scheduled_time)
        )
        active_picks = session.exec(active_picks_stmt).all()

        if not active_picks:
            await interaction.response.send_message(
                "You have no active picks.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Your Active Picks",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        icon_url = (
            interaction.user.avatar.url if interaction.user.avatar else None
        )
        embed.set_author(name=interaction.user.display_name, icon_url=icon_url)

        for pick in active_picks:
            match_info = f"{pick.match.team1} vs {pick.match.team2}"
            time_str = pick.match.scheduled_time.strftime("%Y-%m-%d %H:%M UTC")
            value = f"Your pick: **{pick.chosen_team}**\nScheduled: {time_str}"
            embed.add_field(
                name=match_info,
                value=value,
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


@picks_group.command(
    name="view-history",
    description="View your past picks and their results.",
)
async def view_history(interaction: discord.Interaction):
    """Shows a user their resolved picks history."""
    logger.info(
        "'%s' (%s) requested their pick history.",
        interaction.user.name,
        interaction.user.id,
    )
    with get_session() as session:
        db_user = crud.get_user_by_discord_id(
            session, str(interaction.user.id)
        )
        if not db_user:
            await interaction.response.send_message(
                "You have no picks history.", ephemeral=True
            )
            return

        # Fetch picks that have a result (via Match -> Result)
        stmt = (
            select(Pick)
            .join(Match)
            .join(Result)
            .where(Pick.user_id == db_user.id)
            .options(selectinload(Pick.match).selectinload(Match.result))
            .order_by(Match.scheduled_time.desc())
            .limit(25)
        )
        history_picks = session.exec(stmt).all()

        if not history_picks:
            await interaction.response.send_message(
                "You have no resolved picks.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Your Pick History",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc),
        )
        icon_url = (
            interaction.user.avatar.url if interaction.user.avatar else None
        )
        embed.set_author(name=interaction.user.display_name, icon_url=icon_url)

        for pick in history_picks:
            match = pick.match
            result = match.result

            match_info = f"{match.team1} vs {match.team2}"
            score_str = f" ({result.score})" if result.score else ""

            status_icon = "✅ Correct" if pick.is_correct else "❌ Incorrect"
            # Fallback if is_correct is None but result exists
            if pick.is_correct is None:
                status_icon = "❓ Unresolved"

            value = (
                f"Your pick: **{pick.chosen_team}**\n"
                f"Winner: {result.winner}{score_str}\n"
                f"Result: {status_icon}"
            )
            embed.add_field(
                name=match_info,
                value=value,
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class MatchSelectForPicks(discord.ui.Select):
    """A dropdown to select a match to view picks for."""

    def __init__(self, matches: list[Match]):
        options = [
            discord.SelectOption(
                label=f"{match.team1} vs {match.team2}",
                value=str(match.id),
                description=(
                    "Scheduled: "
                    f"{match.scheduled_time.strftime('%Y-%m-%d %H:%M UTC')}"
                ),
            )
            for match in matches
        ]
        super().__init__(
            placeholder="Choose a match...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        match_id = int(self.values[0])

        with get_session() as session:
            match = crud.get_match_by_id(session, match_id)
            if not match:
                await interaction.followup.send(
                    "Match not found.", ephemeral=True
                )
                return

            picks = crud.list_picks_for_match_with_users(session, match_id)
            embed = _build_picks_embed(match, picks)

            await interaction.followup.send(embed=embed, ephemeral=True)
            await interaction.edit_original_response(view=None)


@picks_group.command(
    name="view-match", description="View all picks for a specific match."
)
async def view_match(interaction: discord.Interaction):
    """Shows all picks for a selected match."""
    logger.info(
        "'%s' (%s) requested to view match picks.",
        interaction.user.name,
        interaction.user.id,
    )
    with get_session() as session:
        matches = session.exec(
            select(Match).order_by(Match.scheduled_time)
        ).all()

        if not matches:
            await interaction.response.send_message(
                "There are no matches to view.", ephemeral=True
            )
            return

        view = discord.ui.View()
        view.add_item(
            MatchSelectForPicks(matches=matches[:25])
        )  # Limit to 25 options for dropdown
        await interaction.response.send_message(
            "Please select a match to view the picks:",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    bot.tree.add_command(picks_group)

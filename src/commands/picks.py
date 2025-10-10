# src/commands/picks.py

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from sqlmodel import Session, select

from src.db import get_session
from src.models import Match, Pick
from src import crud

logger = logging.getLogger("esports-bot.commands.picks")

picks_group = app_commands.Group(
    name="picks", description="Commands for viewing picks."
)


@picks_group.command(
    name="view-active",
    description="View your active picks for upcoming matches.",
)
async def view_active(interaction: discord.Interaction):
    """Shows a user their own upcoming/active picks."""
    log_msg = (
        f"'{interaction.user.name}' ({interaction.user.id}) requested "
        "their active picks."
    )
    logger.info(log_msg)
    session: Session = next(get_session())

    db_user = crud.get_user_by_discord_id(session, str(interaction.user.id))
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
    icon_url = interaction.user.avatar.url if interaction.user.avatar else None
    embed.set_author(name=interaction.user.display_name, icon_url=icon_url)

    for pick in active_picks:
        match_info = f"{pick.match.team1} vs {pick.match.team2}"
        time_str = pick.match.scheduled_time.strftime("%Y-%m-%d %H:%M UTC")
        embed.add_field(
            name=match_info,
            value=f"Your pick: **{pick.chosen_team}**\nScheduled: {time_str}",
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
        session: Session = next(get_session())
        match = crud.get_match_by_id(session, match_id)

        if not match:
            await interaction.followup.send("Match not found.", ephemeral=True)
            return

        picks = crud.list_picks_for_match(session, match_id)

        embed = discord.Embed(
            title=f"Picks for {match.team1} vs {match.team2}",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )

        if not picks:
            embed.description = (
                "No picks have been submitted for this match yet."
            )
        else:
            team1_picks = []
            team2_picks = []
            for pick in picks:
                user_name = (
                    pick.user.username or f"User ID: {pick.user.discord_id}"
                )
                if pick.chosen_team == match.team1:
                    team1_picks.append(user_name)
                else:
                    team2_picks.append(user_name)

            if team1_picks:
                embed.add_field(
                    name=f"Picks for {match.team1} ({len(team1_picks)})",
                    value="\n".join(team1_picks),
                    inline=True,
                )
            if team2_picks:
                embed.add_field(
                    name=f"Picks for {match.team2} ({len(team2_picks)})",
                    value="\n".join(team2_picks),
                    inline=True,
                )

        await interaction.followup.send(embed=embed, ephemeral=True)
        await interaction.edit_original_response(view=None)


@picks_group.command(
    name="view-match", description="View all picks for a specific match."
)
async def view_match(interaction: discord.Interaction):
    """Shows all picks for a selected match."""
    log_msg = (
        f"'{interaction.user.name}' ({interaction.user.id}) requested to "
        "view match picks."
    )
    logger.info(log_msg)
    session: Session = next(get_session())

    matches = session.exec(select(Match).order_by(Match.scheduled_time)).all()

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
        "Please select a match to view the picks:", view=view, ephemeral=True
    )


async def setup(bot):
    bot.tree.add_command(picks_group)

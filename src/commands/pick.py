# src/commands/pick.py

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from sqlmodel import Session, select

from src.db import get_session
from src.models import Match, Pick
from src import crud

logger = logging.getLogger("esports-bot.commands.pick")


class MatchSelect(discord.ui.Select):
    """A dropdown to select a match."""

    def __init__(self, matches: list[Match], user_picks: dict[int, str]):
        options = []
        for match in matches:
            # Indicate if the user has already picked this match
            picked_indicator = " (✓ Picked)" if match.id in user_picks else ""
            label = f"{match.team1} vs {match.team2}{picked_indicator}"
            time_str = match.scheduled_time.strftime("%Y-%m-%d %H:%M UTC")
            description = f"Scheduled: {time_str}"
            options.append(
                discord.SelectOption(
                    label=label, value=str(match.id), description=description
                )
            )

        super().__init__(
            placeholder="Choose a match...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # Defer to allow time for processing
        await interaction.response.defer()

        match_id = int(self.values[0])
        session: Session = next(get_session())
        match = crud.get_match_by_id(session, match_id)

        if not match:
            await interaction.followup.send(
                "This match could not be found.", ephemeral=True
            )
            return

        # Show the team selection view
        view = discord.ui.View()
        view.add_item(TeamSelect(match=match))
        await interaction.followup.send(
            f"You selected: **{match.team1} vs {match.team2}**. Who will win?",
            view=view,
            ephemeral=True,
        )


class TeamSelect(discord.ui.Select):
    """A dropdown to select a team for a given match."""

    def __init__(self, match: Match):
        self.match = match
        options = [
            discord.SelectOption(label=match.team1, value=match.team1),
            discord.SelectOption(label=match.team2, value=match.team2),
        ]
        super().__init__(
            placeholder="Select the winning team...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        chosen_team = self.values[0]
        session: Session = next(get_session())

        # Get or create the user
        db_user = crud.get_user_by_discord_id(
            session,
            str(interaction.user.id),
        )
        if not db_user:
            db_user = crud.create_user(
                session, str(interaction.user.id), interaction.user.name
            )

        # Check if a pick already exists for this user and match
        existing_pick_stmt = (
            select(Pick)
            .where(Pick.user_id == db_user.id)
            .where(Pick.match_id == self.match.id)
        )
        existing_pick = session.exec(existing_pick_stmt).first()

        if existing_pick:
            # Update the existing pick
            existing_pick.chosen_team = chosen_team
            session.add(existing_pick)
            session.commit()
            message = (
                f"Your pick for **{self.match.team1} vs {self.match.team2}** "
                f"has been updated to **{chosen_team}**."
            )
        else:
            # Create a new pick
            crud.create_pick(
                session=session,
                user_id=db_user.id,
                contest_id=self.match.contest_id,
                match_id=self.match.id,
                chosen_team=chosen_team,
            )
            message = (
                f"You have picked **{chosen_team}** to win the match: "
                f"**{self.match.team1} vs {self.match.team2}**."
            )

        await interaction.response.send_message(message, ephemeral=True)
        # Remove the view after selection
        await interaction.edit_original_response(view=None)


@app_commands.command(
    name="pick", description="Submit or update a pick for an upcoming match."
)
async def pick(interaction: discord.Interaction):
    """The main command to initiate picking a match."""
    logger.info(
        "'%s' (%s) initiated a pick.",
        interaction.user.name,
        interaction.user.id,
    )
    session: Session = next(get_session())

    # Get user and their existing picks
    db_user = crud.get_user_by_discord_id(
        session,
        str(interaction.user.id),
    )
    user_picks = {}
    if db_user:
        picks = crud.list_picks_for_user(session, db_user.id)
        user_picks = {pick.match_id: pick.chosen_team for pick in picks}

    # Fetch active matches (not yet started)
    now_utc = datetime.now(timezone.utc)
    active_matches_stmt = (
        select(Match)
        .where(Match.scheduled_time > now_utc)
        .order_by(Match.scheduled_time)
    )
    active_matches = session.exec(active_matches_stmt).all()

    if not active_matches:
        await interaction.response.send_message(
            "There are no active matches available to pick.", ephemeral=True
        )
        return

    view = discord.ui.View()
    view.add_item(MatchSelect(matches=active_matches, user_picks=user_picks))
    await interaction.response.send_message(
        "Please select a match to place your pick:", view=view, ephemeral=True
    )


async def setup(bot):
    bot.tree.add_command(pick)

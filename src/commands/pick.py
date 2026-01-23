# src/commands/pick.py

import logging
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from sqlmodel import select

from src.db import get_session
from src.models import Match
from src import crud

logger = logging.getLogger("esports-bot.commands.pick")

# Number of days in advance (from now) that matches are available for picking.
# The pick window extends this many days into the future.
PICK_WINDOW_DAYS = 5


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
        with get_session() as session:
            match = crud.get_match_by_id(session, match_id)

            if not match:
                await interaction.followup.send(
                    "This match could not be found.", ephemeral=True
                )
                return

            # Check for existing pick for this match to highlight buttons
            db_user = crud.get_user_by_discord_id(
                session, str(interaction.user.id)
            )
            current_pick_team = None
            if db_user:
                existing_pick = crud.get_pick(session, db_user.id, match.id)
                if existing_pick:
                    current_pick_team = existing_pick.chosen_team

            # Show the team selection view (buttons)
            view = TeamPickView(match=match, current_pick=current_pick_team)
            msg = (
                f"You selected: **{match.team1} vs {match.team2}**. "
                "Who will win?"
            )
            await interaction.followup.send(
                msg,
                view=view,
                ephemeral=True,
            )


class TeamButton(discord.ui.Button):
    """A button to select a winning team."""

    def __init__(
        self, team: str, match: Match, style: discord.ButtonStyle = None
    ):
        if style is None:
            style = discord.ButtonStyle.primary
        super().__init__(label=team, style=style)
        self.team = team
        self.match = match

    async def callback(self, interaction: discord.Interaction):
        chosen_team = self.team
        with get_session() as session:
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
            existing_pick = crud.get_pick(session, db_user.id, self.match.id)

            if existing_pick:
                # Update the existing pick
                existing_pick.chosen_team = chosen_team
                session.add(existing_pick)
                session.commit()
                match_str = f"**{self.match.team1} vs {self.match.team2}**"
                message = (
                    f"Your pick for {match_str} "
                    f"has been updated to **{chosen_team}**."
                )
            else:
                # Create a new pick
                crud.create_pick(
                    session,
                    crud.PickCreateParams(
                        user_id=db_user.id,
                        contest_id=self.match.contest_id,
                        match_id=self.match.id,
                        chosen_team=chosen_team,
                    ),
                )
                message = (
                    f"You have picked **{chosen_team}** to win the match: "
                    f"**{self.match.team1} vs {self.match.team2}**."
                )

        # Replace the buttons with the confirmation message
        await interaction.response.edit_message(content=message, view=None)


class TeamPickView(discord.ui.View):
    """A view with buttons to pick a team."""

    def __init__(self, match: Match, current_pick: str | None = None):
        super().__init__()
        # Add buttons for each team
        # If the user has already picked a team, highlight it (Success/Green)
        # Otherwise use Primary (Blurple)

        style1 = (
            discord.ButtonStyle.success
            if current_pick == match.team1
            else discord.ButtonStyle.primary
        )
        self.add_item(TeamButton(team=match.team1, match=match, style=style1))

        style2 = (
            discord.ButtonStyle.success
            if current_pick == match.team2
            else discord.ButtonStyle.primary
        )
        self.add_item(TeamButton(team=match.team2, match=match, style=style2))


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
    with get_session() as session:
        # Get user and their existing picks
        db_user = crud.get_user_by_discord_id(
            session,
            str(interaction.user.id),
        )
        user_picks = {}
        if db_user:
            picks = crud.list_picks_for_user(session, db_user.id)
            user_picks = {pick.match_id: pick.chosen_team for pick in picks}

        # Fetch active matches that are within the pick window
        now_utc = datetime.now(timezone.utc)
        pick_cutoff = now_utc + timedelta(days=PICK_WINDOW_DAYS)
        active_matches_stmt = (
            select(Match)
            .where(Match.scheduled_time > now_utc)
            .where(Match.scheduled_time <= pick_cutoff)
            .where(Match.team1 != "TBD")
            .where(Match.team2 != "TBD")
            .order_by(Match.scheduled_time)
            .limit(25)
        )
        active_matches = session.exec(active_matches_stmt).all()

        if not active_matches:
            await interaction.response.send_message(
                "There are no active matches available to pick.",
                ephemeral=True,
            )
            return

        view = discord.ui.View()
        view.add_item(
            MatchSelect(matches=active_matches, user_picks=user_picks)
        )
        await interaction.response.send_message(
            "Please select a match to place your pick:",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    bot.tree.add_command(pick)

# src/commands/matches.py

import logging
import io
import csv
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from sqlmodel import Session

from src.db import get_session
from src.models import Contest, Match
from src import crud
from src.config import ADMIN_IDS

logger = logging.getLogger("esports-bot.commands.matches")

matches_group = app_commands.Group(
    name="matches", description="Commands for viewing and managing matches."
)

# --- Helper Functions and Classes ---


async def contest_autocompletion(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for contests, showing active and upcoming contests."""
    with next(get_session()) as session:
        all_contests = crud.list_contests(session)
        now = datetime.now(timezone.utc)

        active_contests = []
        upcoming_contests = []

        for contest in all_contests:
            # Make naive datetimes timezone-aware (assume UTC)
            start_date = (
                contest.start_date.replace(tzinfo=timezone.utc)
                if contest.start_date.tzinfo is None
                else contest.start_date
            )
            end_date = (
                contest.end_date.replace(tzinfo=timezone.utc)
                if contest.end_date.tzinfo is None
                else contest.end_date
            )

            if end_date > now:  # Not ended
                if start_date <= now:
                    active_contests.append(contest)
                else:
                    upcoming_contests.append(contest)

        # Sort active and upcoming contests by start date (earliest first)
        active_contests.sort(key=lambda c: c.start_date)
        upcoming_contests.sort(key=lambda c: c.start_date)

        # Combine lists, active first, and get the top 25
        sorted_contests = (active_contests + upcoming_contests)[:25]

        choices = []
        # Now, filter these 25 based on the user's input
        for contest in sorted_contests:
            if current.lower() in contest.name.lower():
                choice_name = f"{contest.name} (ID: {contest.id})"
                # Discord has a 100-char limit for choice names
                if len(choice_name) > 100:
                    suffix = f"... (ID: {contest.id})"
                    max_name_length = 100 - len(suffix)
                    choice_name = f"{contest.name[:max_name_length]}{suffix}"
                choices.append(
                    app_commands.Choice(
                        name=choice_name,
                        value=contest.id,
                    )
                )

    return choices


async def create_matches_embed(
    title: str, matches: list[Match], interaction: discord.Interaction
) -> discord.Embed:
    """Creates a standard embed for displaying a list of matches."""
    embed = discord.Embed(
        title=title,
        color=discord.Color.purple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(
        name=interaction.user.display_name,
        icon_url=(
            interaction.user.avatar.url if interaction.user.avatar else None
        ),
    )

    if not matches:
        embed.description = "No matches found."
    else:
        for match in matches:
            time_str = match.scheduled_time.strftime("%H:%M UTC")
            embed.add_field(
                name=f"{match.team1} vs {match.team2}",
                value=f"Time: {time_str}\nContest: {match.contest.name}",
                inline=False,
            )
    return embed


class DayNavigationView(discord.ui.View):
    """A view with buttons to navigate between days."""

    def __init__(
        self,
        current_date: datetime.date,
        interaction: discord.Interaction,
    ):
        super().__init__(timeout=180)
        self.current_date = current_date
        self.interaction = interaction

    async def update_embed(self, interaction: discord.Interaction):
        """Updates the embed with matches for the current date."""
        await interaction.response.defer()
        session: Session = next(get_session())
        matches = crud.get_matches_by_date(session, self.current_date)
        title = f"Matches for {self.current_date.strftime('%Y-%m-%d')}"
        embed = await create_matches_embed(title, matches, self.interaction)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(
        label="< Previous Day",
        style=discord.ButtonStyle.secondary,
    )
    async def previous_day(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_date -= timedelta(days=1)
        await self.update_embed(interaction)

    @discord.ui.button(
        label="Next Day >",
        style=discord.ButtonStyle.secondary,
    )
    async def next_day(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current_date += timedelta(days=1)
        await self.update_embed(interaction)


class TournamentSelect(discord.ui.Select):
    """A dropdown to select a tournament."""

    def __init__(self, contests: list[Contest]):
        options = [
            discord.SelectOption(label=c.name, value=str(c.id))
            for c in contests
        ]
        super().__init__(placeholder="Choose a tournament...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        contest_id = int(self.values[0])
        session: Session = next(get_session())
        matches = crud.list_matches_for_contest(session, contest_id)
        contest = crud.get_contest_by_id(session, contest_id)
        title = f"Matches for {contest.name}"
        embed = await create_matches_embed(title, matches, interaction)
        await interaction.edit_original_response(embed=embed, view=None)


# --- Commands ---


@matches_group.command(
    name="view-by-day",
    description="View matches scheduled for a specific day.",
)
async def view_by_day(interaction: discord.Interaction):
    """Shows matches for the current day with navigation."""
    logger.info(f"'{interaction.user.name}' requested matches by day.")
    current_date = datetime.now(timezone.utc).date()
    session: Session = next(get_session())
    matches = crud.get_matches_by_date(session, current_date)
    title = f"Matches for {current_date.strftime('%Y-%m-%d')}"
    embed = await create_matches_embed(title, matches, interaction)
    view = DayNavigationView(current_date, interaction)
    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True,
    )


@matches_group.command(
    name="view-by-tournament",
    description="View all matches for a specific tournament.",
)
async def view_by_tournament(interaction: discord.Interaction):
    """Shows a dropdown to select a tournament and view its matches."""
    logger.info(f"'{interaction.user.name}' requested matches by tournament.")
    session: Session = next(get_session())
    contests = crud.list_contests(session)
    if not contests:
        await interaction.response.send_message(
            "No tournaments found.",
            ephemeral=True,
        )
        return

    view = discord.ui.View(timeout=180)
    view.add_item(TournamentSelect(contests=contests[:25]))
    await interaction.response.send_message(
        "Please select a tournament:", view=view, ephemeral=True
    )


@matches_group.command(
    name="upload", description="Upload a match schedule via CSV (Admin only)."
)
@app_commands.autocomplete(contest_id=contest_autocompletion)
@app_commands.describe(
    contest_id="The ID of the contest to add matches to.",
    attachment="The CSV file with the match schedule.",
)
async def upload(
    interaction: discord.Interaction,
    contest_id: int,
    attachment: discord.Attachment,
):
    """Handles CSV upload for match schedules."""
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return

    logger.info(
        f"Admin '{interaction.user.name}' is uploading matches for contest "
        f"{contest_id}."
    )
    await interaction.response.defer(ephemeral=True)

    session: Session = next(get_session())
    contest = crud.get_contest_by_id(session, contest_id)
    if not contest:
        await interaction.followup.send(
            f"Contest with ID {contest_id} not found.", ephemeral=True
        )
        return

    try:
        csv_data = await attachment.read()
        csv_file = io.StringIO(csv_data.decode("utf-8"))
        reader = csv.DictReader(csv_file)

        matches_to_create = []
        errors = []
        for i, row in enumerate(reader, 1):
            try:
                matches_to_create.append(
                    {
                        "contest_id": contest_id,
                        "team1": row["team1"],
                        "team2": row["team2"],
                        "scheduled_time": datetime.fromisoformat(
                            row["scheduled_time"]
                        ),
                    }
                )
            except (KeyError, ValueError) as e:
                errors.append(f"Row {i+1}: Invalid data or format. {e}")

        if errors:
            await interaction.followup.send(
                "Errors found in CSV:\n" + "\n".join(errors), ephemeral=True
            )
            return

        crud.bulk_create_matches(session, matches_to_create)
        await interaction.followup.send(
            f"Successfully uploaded {len(matches_to_create)} matches for "
            f"'{contest.name}'.",
            ephemeral=True,
        )

    except Exception as e:
        logger.exception("Error during match upload.")
        await interaction.followup.send(
            f"An unexpected error occurred: {e}", ephemeral=True
        )
    finally:
        session.close()


async def setup(bot):
    bot.tree.add_command(matches_group)

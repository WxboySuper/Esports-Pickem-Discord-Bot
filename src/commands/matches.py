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
from src.auth import is_admin

logger = logging.getLogger("esports-bot.commands.matches")

matches_group = app_commands.Group(
    name="matches", description="Commands for viewing and managing matches."
)

# --- Helper Functions and Classes ---


def _make_aware(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def _status_for(c: Contest, now_dt: datetime) -> str:
    start = _make_aware(c.start_date)
    end = _make_aware(c.end_date)
    return "Active" if start <= now_dt <= end else "Upcoming"


def _label_for(c: Contest, now_dt: datetime) -> str:
    start = _make_aware(c.start_date)
    status = _status_for(c, now_dt)
    label = f"{c.name} — {status} " f"({start.strftime('%Y-%m-%d %H:%M UTC')})"
    if len(label) <= 100:
        return label
    suffix = f"... (ID: {c.id})"
    max_name_length = 100 - len(suffix)
    return f"{(c.name or '')[:max_name_length]}{suffix}"


def _matches_name(current_norm: str, c: Contest) -> bool:
    """Return True if contest `c` matches the normalized `current_norm`.

    Encapsulates the conditional logic used for filtering by name so
    callers don't include complex expressions inline.
    """
    if not current_norm:
        return True
    name = (c.name or "").lower()
    return current_norm in name


def _build_entries(
    contests: list[Contest],
    current_norm: str,
    now: datetime,
) -> list[tuple[str, datetime, Contest]]:
    entries: list[tuple[str, datetime, Contest]] = []
    for c in contests:
        start = _make_aware(c.start_date)
        end = _make_aware(c.end_date)
        if end <= now:
            continue
        if not _matches_name(current_norm, c):
            continue
        status = _status_for(c, now)
        entries.append((status, start, c))
    entries.sort(key=lambda t: (0 if t[0] == "Active" else 1, t[1]))
    return entries


def _get_autocomplete_choices(
    session: Session,
    current: str,
    limit: int = 25,
) -> list[app_commands.Choice[int]]:
    """Build autocomplete `Choice` objects for contests using helpers.

    Separated so the public async handler is a tiny wrapper and its
    complexity is minimal.
    """
    all_contests = crud.list_contests(session)
    now = datetime.now(timezone.utc)
    current_norm = (current or "").strip().lower()

    entries = _build_entries(all_contests, current_norm, now)

    choices: list[app_commands.Choice[int]] = []
    for _, _, contest in entries:
        choices.append(
            app_commands.Choice(
                name=_label_for(contest, now),
                value=contest.id,
            )
        )
        if len(choices) >= limit:
            break

    return choices


async def contest_autocompletion(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for contests, showing active and upcoming contests.

    This handler is a small wrapper that delegates work to
    `_get_autocomplete_choices` so its complexity stays minimal.
    """

    with get_session() as session:
        return _get_autocomplete_choices(session, current, limit=25)


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
            value = f"Time: {time_str}\nContest: {match.contest.name}"

            if match.result:
                score_str = (
                    f" ({match.result.score})" if match.result.score else ""
                )
                value += f"\n**Result: {match.result.winner} won{score_str}**"

            embed.add_field(
                name=f"{match.team1} vs {match.team2}",
                value=value,
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
        with get_session() as session:
            matches = crud.get_matches_by_date(session, self.current_date)
            title = f"Matches for {self.current_date.strftime('%Y-%m-%d')}"
            embed = await create_matches_embed(
                title, matches, self.interaction
            )
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
        with get_session() as session:
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
    logger.info("'%s' requested matches by day.", interaction.user.name)
    current_date = datetime.now(timezone.utc).date()
    with get_session() as session:
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
    logger.info("'%s' requested matches by tournament.", interaction.user.name)
    with get_session() as session:
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
@is_admin()
async def upload(
    interaction: discord.Interaction,
    contest_id: int,
    attachment: discord.Attachment,
):
    """Handles CSV upload for match schedules."""

    logger.info(
        "Admin '%s' is uploading matches for contest %s.",
        interaction.user.name,
        contest_id,
    )
    await interaction.response.defer(ephemeral=True)

    with get_session() as session:
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
                    team1 = row["team1"]
                    team2 = row["team2"]
                    scheduled_time = datetime.fromisoformat(
                        row["scheduled_time"]
                    )
                    # Extract leaguepedia_id or generate a fallback
                    leaguepedia_id = row.get("leaguepedia_id")
                    if not leaguepedia_id:
                        # Deterministic fallback for manual uploads
                        leaguepedia_id = (
                            f"manual-{contest_id}-{team1}-{team2}-"
                            f"{scheduled_time.isoformat()}"
                        )

                    matches_to_create.append(
                        {
                            "contest_id": contest_id,
                            "leaguepedia_id": leaguepedia_id,
                            "team1": team1,
                            "team2": team2,
                            "scheduled_time": scheduled_time,
                        }
                    )
                except (KeyError, ValueError) as e:
                    errors.append(f"Row {i}: Invalid data or format. {e}")

            if errors:
                await interaction.followup.send(
                    "Errors found in CSV:\n" + "\n".join(errors),
                    ephemeral=True,
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


async def setup(bot):
    bot.tree.add_command(matches_group)

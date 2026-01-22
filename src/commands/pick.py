# src/commands/pick.py

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

import discord
from discord import app_commands
from sqlmodel import select
from sqlalchemy.orm import selectinload

from src.db import get_session
from src.models import Match, Pick, Contest
from src import crud

logger = logging.getLogger("esports-bot.commands.pick")

# Number of days in advance (from now) that matches are available for picking.
PICK_WINDOW_DAYS = 5


class PickView(discord.ui.View):
    """
    A persistent view that allows users to browse matches and make picks.
    """

    def __init__(
        self,
        matches: List[Match],
        user_picks: Dict[int, str],
        user_id: int,
        interaction_user_id: int
    ):
        super().__init__(timeout=None)
        self.matches = matches
        self.user_picks = user_picks
        self.db_user_id = user_id # Database ID of the user
        self.interaction_user_id = interaction_user_id # Discord ID of the user
        self.current_index = 0
        self.message: Optional[discord.Message] = None

        # Initialize the view state
        self._update_components()

    def _get_current_match(self) -> Match:
        return self.matches[self.current_index]

    def _update_components(self):
        """Updates the state of buttons based on the current match."""
        match = self._get_current_match()
        current_pick = self.user_picks.get(match.id)

        # Clear existing items to rebuild them
        self.clear_items()

        # Row 1: Team Buttons
        # Team 1 Button
        style_t1 = discord.ButtonStyle.secondary
        if current_pick == match.team1:
            style_t1 = discord.ButtonStyle.success

        button_t1 = discord.ui.Button(
            label=match.team1,
            style=style_t1,
            custom_id=f"pick_t1_{match.id}",
            row=0
        )
        button_t1.callback = self.pick_team1_callback
        self.add_item(button_t1)

        # VS Label (disabled button or just implicit by position)
        # We can't put text between buttons easily, so just Team 1 | Team 2

        # Team 2 Button
        style_t2 = discord.ButtonStyle.secondary
        if current_pick == match.team2:
            style_t2 = discord.ButtonStyle.success

        button_t2 = discord.ui.Button(
            label=match.team2,
            style=style_t2,
            custom_id=f"pick_t2_{match.id}",
            row=0
        )
        button_t2.callback = self.pick_team2_callback
        self.add_item(button_t2)

        # Row 2: Navigation
        prev_disabled = self.current_index == 0
        next_disabled = self.current_index == len(self.matches) - 1

        btn_prev = discord.ui.Button(
            label="Previous Match",
            style=discord.ButtonStyle.primary,
            disabled=prev_disabled,
            row=1
        )
        btn_prev.callback = self.prev_match_callback
        self.add_item(btn_prev)

        btn_next = discord.ui.Button(
            label="Next Match",
            style=discord.ButtonStyle.primary,
            disabled=next_disabled,
            row=1
        )
        btn_next.callback = self.next_match_callback
        self.add_item(btn_next)

    def _build_embed(self) -> discord.Embed:
        match = self._get_current_match()
        contest_name = match.contest.name if match.contest else "Unknown Contest"

        # Determine current pick status for display
        pick_status = self.user_picks.get(match.id)
        if pick_status:
            status_text = f"✅ You have picked **{pick_status}**"
        else:
            status_text = "⚠️ No pick made yet"

        embed = discord.Embed(
            title=f"Match {self.current_index + 1} of {len(self.matches)}",
            description=f"**{match.team1}** vs **{match.team2}**",
            color=discord.Color.blue()
        )

        embed.add_field(name="Tournament", value=contest_name, inline=False)

        time_str = match.scheduled_time.strftime("%Y-%m-%d %H:%M UTC")
        embed.add_field(name="Scheduled Time", value=time_str, inline=True)

        if match.best_of:
            embed.add_field(name="Format", value=f"Best of {match.best_of}", inline=True)

        embed.add_field(name="Your Pick", value=status_text, inline=False)

        embed.set_footer(text=f"Match ID: {match.id}")
        return embed

    async def _handle_pick(self, interaction: discord.Interaction, team: str):
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message(
                "This pick session is not for you.", ephemeral=True
            )
            return

        match = self._get_current_match()

        # DB Operation
        with get_session() as session:
            # Re-fetch user to ensure attached to session (though we have ID)
            # Actually we can just query directly or use the ID.
            # We need to make sure we don't duplicate logic unnecessarily.

            # Check for existing pick
            stmt = select(Pick).where(
                Pick.user_id == self.db_user_id,
                Pick.match_id == match.id
            )
            existing_pick = session.exec(stmt).first()

            if existing_pick:
                existing_pick.chosen_team = team
                session.add(existing_pick)
            else:
                # Create new pick
                new_pick = Pick(
                    user_id=self.db_user_id,
                    contest_id=match.contest_id,
                    match_id=match.id,
                    chosen_team=team
                )
                session.add(new_pick)

            session.commit()

            # Update local state
            self.user_picks[match.id] = team

        # Update UI
        self._update_components()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def pick_team1_callback(self, interaction: discord.Interaction):
        match = self._get_current_match()
        await self._handle_pick(interaction, match.team1)

    async def pick_team2_callback(self, interaction: discord.Interaction):
        match = self._get_current_match()
        await self._handle_pick(interaction, match.team2)

    async def prev_match_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message(
                "This controls are not for you.", ephemeral=True
            )
            return

        if self.current_index > 0:
            self.current_index -= 1
            self._update_components()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()

    async def next_match_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message(
                "This controls are not for you.", ephemeral=True
            )
            return

        if self.current_index < len(self.matches) - 1:
            self.current_index += 1
            self._update_components()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.defer()


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

    await interaction.response.defer(ephemeral=True)

    with get_session() as session:
        # Get user (create if not exists)
        db_user = crud.get_user_by_discord_id(
            session,
            str(interaction.user.id),
        )
        if not db_user:
            db_user = crud.create_user(
                session, str(interaction.user.id), interaction.user.name
            )

        # Fetch active matches
        now_utc = datetime.now(timezone.utc)
        pick_cutoff = now_utc + timedelta(days=PICK_WINDOW_DAYS)

        active_matches_stmt = (
            select(Match)
            .where(Match.scheduled_time > now_utc)
            .where(Match.scheduled_time <= pick_cutoff)
            .where(Match.team1 != "TBD")
            .where(Match.team2 != "TBD")
            .options(selectinload(Match.contest))
            .order_by(Match.scheduled_time)
            # We remove the limit of 25 since we are paging,
            # though too many matches in memory might be an issue eventually.
            # For now, let's keep a reasonable limit or no limit if expected volume is low.
            # Discord limit for select was 25, here we are paging.
            # Let's cap at 50 to be safe.
            .limit(50)
        )
        active_matches = session.exec(active_matches_stmt).all()

        if not active_matches:
            await interaction.followup.send(
                "There are no active matches available to pick.",
                ephemeral=True,
            )
            return

        # Fetch existing picks for these matches
        match_ids = [m.id for m in active_matches]
        picks_stmt = select(Pick).where(
            Pick.user_id == db_user.id,
            Pick.match_id.in_(match_ids)
        )
        picks = session.exec(picks_stmt).all()
        user_picks = {p.match_id: p.chosen_team for p in picks}

        # Create View
        view = PickView(
            matches=active_matches,
            user_picks=user_picks,
            user_id=db_user.id,
            interaction_user_id=interaction.user.id
        )

        embed = view._build_embed()

        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )


async def setup(bot):
    bot.tree.add_command(pick)

# src/commands/result.py

import logging
from typing import List

import discord
from discord import app_commands

from src.db import get_async_session
from src import crud
from src.auth import is_admin

logger = logging.getLogger("esports-bot.commands.result")


async def winner_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    """Autocompletes the winner argument with the teams from the specified
    match."""
    match_id_str = interaction.namespace.match_id
    if not match_id_str:
        return []

    try:
        match_id = int(match_id_str)
    except ValueError:
        return []

    async with get_async_session() as session:
        match = await crud.get_match_by_id(session, match_id)

        if not match:
            return []

        choices = [
            app_commands.Choice(name=match.team1, value=match.team1),
            app_commands.Choice(name=match.team2, value=match.team2),
        ]

    # Filter choices based on what the user has already typed
    return [
        choice for choice in choices if current.lower() in choice.name.lower()
    ]


async def match_autocompletion(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete for matches, prioritizing those without results."""
    async with get_async_session() as session:
        all_matches = await crud.list_all_matches(session)

        matches_with_results = []
        matches_without_results = []

        for match in all_matches:
            if await crud.get_result_for_match(session, match.id):
                matches_with_results.append(match)
            else:
                matches_without_results.append(match)

        # Prioritize matches without results, then show matches with results
        sorted_matches = matches_without_results + matches_with_results

        choices = []
        for match in sorted_matches:
            has_result = match in matches_with_results
            prefix = "[HAS RESULT] " if has_result else ""
            choice_name = (
                f"{prefix}{match.team1} vs {match.team2} (ID: {match.id})"
            )

            # Truncate if necessary
            if len(choice_name) > 100:
                suffix = f"... (ID: {match.id})"
                max_len = 100 - len(suffix)
                choice_name = f"{choice_name[:max_len]}{suffix}"

            # Only add to choices if it matches the user's input
            if current.lower() in choice_name.lower():
                choices.append(
                    app_commands.Choice(name=choice_name, value=match.id)
                )

            # Respect Discord's 25-choice limit
            if len(choices) >= 25:
                break

    return choices


@app_commands.command(
    name="enter-result",
    description="Enter the result of a match (Admin only).",
)
@app_commands.describe(
    match_id="The ID of the match to enter a result for.",
    winner="The winning team.",
)
@app_commands.autocomplete(
    match_id=match_autocompletion, winner=winner_autocomplete
)
@is_admin()
async def enter_result(
    interaction: discord.Interaction,
    match_id: int,
    winner: str,
):
    """Admin command to enter a match result and score all related picks."""

    logger.info(
        "Admin '%s' is entering a result for match %s.",
        interaction.user.name,
        match_id,
    )
    await interaction.response.defer(ephemeral=True)

    async with get_async_session() as session:
        # --- Validation ---
        match = await crud.get_match_by_id(session, match_id)
        if not match:
            await interaction.followup.send(
                f"Match with ID {match_id} not found.", ephemeral=True
            )
            return

        if winner not in [match.team1, match.team2]:
            await interaction.followup.send(
                f"Invalid winner. Please choose either '{match.team1}' or "
                f"'{match.team2}'.",
                ephemeral=True,
            )
            return

        if await crud.get_result_for_match(session, match_id):
            await interaction.followup.send(
                f"A result for match {match_id} has already been entered.",
                ephemeral=True,
            )
            return

        # --- Process Result and Score Picks ---
        try:
            # 1. Create the result
            await crud.create_result(session, match_id=match_id, winner=winner)

            # 2. Get all picks for the match
            picks = await crud.list_picks_for_match(session, match_id)

            updated_picks_count = 0
            for pick in picks:
                if pick.chosen_team == winner:
                    pick.status = "correct"
                    pick.score = 10  # Award 10 points for a correct pick
                else:
                    pick.status = "incorrect"
                    pick.score = 0

                session.add(pick)
                updated_picks_count += 1

            await session.commit()

            await interaction.followup.send(
                (
                    "Result for match "
                    f"**{match.team1} vs {match.team2}** has been entered as "
                    f"**{winner}**.\nProcessed and scored "
                    f"{updated_picks_count} user picks."
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.exception(f"Error entering result for match {match_id}")
            await session.rollback()
            await interaction.followup.send(
                f"An unexpected error occurred: {e}", ephemeral=True
            )


async def setup(bot):
    bot.tree.add_command(enter_result)

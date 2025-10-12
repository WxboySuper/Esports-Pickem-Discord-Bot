# src/commands/stats.py

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from sqlalchemy import func
from sqlmodel import select

from src.db import get_async_session
from src.models import Pick, User
from src import crud

logger = logging.getLogger("esports-bot.commands.stats")


@app_commands.command(
    name="stats", description="View your or another user's pick statistics."
)
@app_commands.describe(
    user="The user to view stats for (defaults to yourself)."
)
async def stats(interaction: discord.Interaction, user: discord.Member = None):
    """Displays statistics for a user."""
    target_user = user or interaction.user
    logger.info(
        f"'{interaction.user.name}' requested stats for '{target_user.name}'."
    )

    async with get_async_session() as session:
        db_user = await crud.get_user_by_discord_id(
            session, str(target_user.id)
        )

        if not db_user:
            message = (
                "You have not made any picks yet."
                if not user
                else f"{target_user.display_name} has not made any picks yet."
            )
            await interaction.response.send_message(message, ephemeral=True)
            return

        # Calculate basic stats
        picks = await crud.list_picks_for_user(session, db_user.id)
        total_picks = len(picks)
        correct_picks = len([p for p in picks if p.status == "correct"])
        win_rate = (
            (correct_picks / total_picks) * 100 if total_picks > 0 else 0
        )

        # Calculate global rank
        # This query calculates the total score for each user and orders them.
        ranking_query = (
            select(User.id, func.sum(Pick.score).label("total_score"))
            .join(Pick)
            .group_by(User.id)
            .order_by(func.sum(Pick.score).desc())
        )
        result = await session.exec(ranking_query)
        all_user_scores = result.all()

        global_rank = "N/A"
        for i, (user_id, score) in enumerate(all_user_scores):
            if user_id == db_user.id:
                global_rank = i + 1
                break

        # Create embed
        embed = discord.Embed(
            title=f"Statistics for {target_user.display_name}",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(
            url=target_user.avatar.url if target_user.avatar else None
        )
        embed.add_field(
            name="Total Picks Made", value=str(total_picks), inline=True
        )
        embed.add_field(
            name="Correct Picks", value=str(correct_picks), inline=True
        )
        embed.add_field(name="Win Rate", value=f"{win_rate:.2f}%", inline=True)
        embed.add_field(
            name="Global Rank", value=f"#{global_rank}", inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    bot.tree.add_command(stats)

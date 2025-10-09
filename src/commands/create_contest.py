# src/commands/create_contest.py
# Admin command to create a new pick'em contest

import logging
import discord
from discord import app_commands
from datetime import datetime

from src.admin_utils import is_admin
from src.db import engine
from sqlmodel import Session
from src import crud

logger = logging.getLogger("esports-bot.commands.create_contest")


async def setup(bot):
    @bot.tree.command(
        name="create_contest",
        description="[Admin] Create a new pick'em contest"
    )
    @app_commands.describe(
        name="Contest name",
        start_date="Start date (ISO format: YYYY-MM-DDTHH:MM:SS)",
        end_date="End date (ISO format: YYYY-MM-DDTHH:MM:SS)"
    )
    async def create_contest(
        interaction: discord.Interaction,
        name: str,
        start_date: str,
        end_date: str
    ):
        logger.debug(
            "create_contest command invoked by user %s",
            interaction.user.id
        )

        # Check admin permissions
        if not is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )
            return

        # Parse dates
        try:
            start_dt = datetime.fromisoformat(
                start_date.replace("Z", "+00:00")
            )
            end_dt = datetime.fromisoformat(
                end_date.replace("Z", "+00:00")
            )
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid date format: {e}\n"
                "Please use ISO format (e.g., 2025-01-15T10:00:00)",
                ephemeral=True
            )
            return

        # Validate dates
        if end_dt <= start_dt:
            await interaction.response.send_message(
                "❌ End date must be after start date.",
                ephemeral=True
            )
            return

        # Create contest in database
        try:
            with Session(engine) as session:
                contest = crud.create_contest(
                    session,
                    name=name,
                    start_date=start_dt,
                    end_date=end_dt
                )

                embed = discord.Embed(
                    title="✅ Contest Created",
                    description=f"Contest **{contest.name}** created "
                                f"successfully!",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="Contest ID",
                    value=str(contest.id),
                    inline=True
                )
                embed.add_field(
                    name="Start Date",
                    value=contest.start_date.strftime("%Y-%m-%d %H:%M:%S"),
                    inline=True
                )
                embed.add_field(
                    name="End Date",
                    value=contest.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                    inline=True
                )

                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True
                )
                logger.info(
                    "Contest created: id=%s, name=%s by user %s",
                    contest.id,
                    contest.name,
                    interaction.user.id
                )

        except Exception as e:
            logger.exception("Error creating contest")
            await interaction.response.send_message(
                f"❌ Error creating contest: {e}",
                ephemeral=True
            )

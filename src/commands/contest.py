# src/commands/contest.py
import logging
import discord
from discord import app_commands

from src.app import ADMIN_IDS
from src.crud import create_contest
from src.db import get_session

logger = logging.getLogger("esports-bot.commands.contest")


class ContestModal(discord.ui.Modal, title="Create New Contest"):
    name = discord.ui.TextInput(
        label="Contest Name",
        placeholder="Enter the name of the contest",
        required=True,
    )
    start_date = discord.ui.TextInput(
        label="Start Date (YYYY-MM-DD)",
        placeholder="YYYY-MM-DD",
        required=True,
    )
    end_date = discord.ui.TextInput(
        label="End Date (YYYY-MM-DD)",
        placeholder="YYYY-MM-DD",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        session = next(get_session())
        from datetime import datetime

        try:
            start_date_val = datetime.strptime(
                self.start_date.value,
                "%Y-%m-%d",
            )
            end_date_val = datetime.strptime(
                self.end_date.value,
                "%Y-%m-%d",
            )

            contest = create_contest(
                session,
                name=self.name.value,
                start_date=start_date_val,
                end_date=end_date_val,
            )
            await interaction.response.send_message(
                f"Contest '{contest.name}' created with ID {contest.id}",
                ephemeral=True,
            )
        except ValueError:
            logger.exception("Invalid date format for contest creation")
            await interaction.response.send_message(
                "Invalid date format. Please use YYYY-MM-DD.", ephemeral=True
            )
        except Exception as e:
            logger.exception("Error creating contest")
            await interaction.response.send_message(
                f"Failed to create contest. Error: {e}", ephemeral=True
            )
        finally:
            session.close()


class Contest(app_commands.Group, name="contest", description="Manage contests"):
    @app_commands.command(name="create", description="Create a new contest")
    async def create(self, interaction: discord.Interaction):
        if interaction.user.id not in ADMIN_IDS:
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ContestModal())


async def setup(bot):
    bot.tree.add_command(Contest())

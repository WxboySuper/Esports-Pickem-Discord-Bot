import logging
import discord
from discord import app_commands, ui
from discord.ext import commands
from sqlalchemy import delete

from src.db import get_async_session
from src.models import Contest, Match, Pick, Result
from src.auth import is_admin


CONFIRM_PHRASE = "WIPE DATABASE"
logger = logging.getLogger("esports-bot.commands.wipe")


class WipeConfirmModal(ui.Modal, title="Confirm Wipe Database"):
    confirm_text = ui.TextInput(
        label=f"Type '{CONFIRM_PHRASE}' to confirm",
        style=discord.TextStyle.short,
        placeholder=CONFIRM_PHRASE,
        max_length=64,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if self.confirm_text.value.strip().upper() != CONFIRM_PHRASE:
            await interaction.followup.send(
                "Confirmation phrase did not match. Aborting.", ephemeral=True
            )
            logger.info(
                "Wipe aborted: user %s (%s) provided incorrect confirmation",
                interaction.user.name,
                interaction.user.id,
            )
            return

        # Perform the destructive operation under confirmation
        try:
            async with get_async_session() as session:
                await session.exec(delete(Result))
                await session.exec(delete(Pick))
                await session.exec(delete(Match))
                await session.exec(delete(Contest))
                await session.commit()

            logger.info(
                "Database wipe performed by user %s (%s)",
                interaction.user.name,
                interaction.user.id,
            )

            message = (
                "All contest data has been wiped by "
                f"{interaction.user.display_name}."
            )
            await interaction.followup.send(message, ephemeral=True)
        except Exception:
            # Log full exception with stacktrace for debugging/audit, but
            # avoid exposing internal details to the user.
            logger.exception("Error performing wipe-data")
            await interaction.followup.send(
                "An error occurred while wiping data. Please contact support.",
                ephemeral=True,
            )


class Wipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="wipe-data",
        description="Wipe all contest data from the database.",
    )
    @is_admin()
    async def wipe_data(self, interaction: discord.Interaction):
        """Show a confirmation modal before wiping all contest data."""
        modal = WipeConfirmModal(self.bot)
        await interaction.response.send_modal(modal)


async def setup(bot):
    await bot.add_cog(Wipe(bot))

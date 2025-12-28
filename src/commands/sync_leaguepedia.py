import io
import logging
import discord
from discord import app_commands
from discord.ext import commands

from src.auth import is_admin
from src.sync_logic import perform_leaguepedia_sync

logger = logging.getLogger(__name__)


class SyncLeaguepedia(commands.Cog):
    """A cog for syncing data from Leaguepedia."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="sync-leaguepedia",
        description="Syncs configured tournaments from Leaguepedia.",
    )
    @is_admin()
    async def sync_leaguepedia(self, interaction: discord.Interaction):
        """
        Performs a full sync and returns the logs as a file for debugging.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Set up a temporary logger to capture the sync process output
        log_stream = io.StringIO()
        root_logger = logging.getLogger()
        original_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)  # Capture everything

        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        try:
            summary = await perform_leaguepedia_sync()

            # Retrieve the logs
            log_contents = log_stream.getvalue()

            if summary is None:
                message = (
                    "Sync could not be completed. This may be because the "
                    "configuration file was not found or was empty. "
                    "See attached logs for more details."
                )
            else:
                message = (
                    "Leaguepedia sync complete!\n"
                    f"- Upserted {summary['contests']} contests.\n"
                    f"- Upserted {summary['matches']} matches.\n"
                    f"- Upserted {summary['teams']} teams."
                )

            if log_contents:
                # Create a file object from the log contents
                log_file = discord.File(
                    io.BytesIO(log_contents.encode()),
                    filename="sync_logs.txt",
                )
                await interaction.followup.send(
                    message, file=log_file, ephemeral=True
                )
            else:
                await interaction.followup.send(
                    message + "\n_No log output was generated._",
                    ephemeral=True,
                )
        finally:
            # Clean up the logger
            root_logger.removeHandler(handler)
            root_logger.setLevel(original_level)
            log_stream.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncLeaguepedia(bot))

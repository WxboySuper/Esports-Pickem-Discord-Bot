import json
import logging
import discord
from discord import app_commands
from discord.ext import commands

from src.auth import is_admin
from src.config import DATA_PATH

from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = DATA_PATH / "tournaments.json"

# Ensure the configured DATA_PATH is usable; if not, fall back to a
# project-local `data/` directory so local dev on Windows works.
try:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
except Exception:
    fallback = Path("data")
    fallback.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH = fallback / "tournaments.json"

# Ensure the config file exists
if not CONFIG_PATH.exists():
    with open(CONFIG_PATH, "w") as f:
        json.dump([], f)


class ConfigureSync(commands.Cog):
    """A cog for managing the tournament sync configuration."""

    def __init__(self, bot: commands.Bot):
        """
        Initialize the ConfigureSync cog and retain a reference to the
        bot for use by the cog's commands and handlers.
        """
        self.bot = bot

    configure_group = app_commands.Group(
        name="configure-sync",
        description="Commands to configure the Leaguepedia sync.",
        default_permissions=discord.Permissions(administrator=True),
    )

    @configure_group.command(
        name="add", description="Add a tournament slug to the sync list."
    )
    @is_admin()
    async def add_tournament(
        self, interaction: discord.Interaction, slug: str
    ):
        """Adds a tournament slug to the configuration file."""
        with open(CONFIG_PATH, "r+") as f:
            tournaments = json.load(f)
            if slug in tournaments:
                await interaction.response.send_message(
                    f"Tournament slug `{slug}` is already in the sync list.",
                    ephemeral=True,
                )
                return
            tournaments.append(slug)
            f.seek(0)
            json.dump(tournaments, f, indent=4)
            f.truncate()

        await interaction.response.send_message(
            f"Successfully added `{slug}` to the sync list.", ephemeral=True
        )

    @configure_group.command(
        name="remove",
        description="Remove a tournament slug from the sync list.",
    )
    @is_admin()
    async def remove_tournament(
        self, interaction: discord.Interaction, slug: str
    ):
        """Removes a tournament slug from the configuration file."""
        with open(CONFIG_PATH, "r+") as f:
            tournaments = json.load(f)
            if slug not in tournaments:
                await interaction.response.send_message(
                    f"Tournament slug `{slug}` is not in the sync list.",
                    ephemeral=True,
                )
                return
            tournaments.remove(slug)
            f.seek(0)
            json.dump(tournaments, f, indent=4)
            f.truncate()

        await interaction.response.send_message(
            f"Successfully removed `{slug}` from the sync list.",
            ephemeral=True,
        )

    @configure_group.command(
        name="list", description="List all tournament slugs in the sync list."
    )
    @is_admin()
    async def list_tournaments(self, interaction: discord.Interaction):
        """Lists all configured tournament slugs."""
        try:
            with open(CONFIG_PATH, "r") as f:
                tournaments = json.load(f)
        except FileNotFoundError:
            tournaments = []
        except json.JSONDecodeError:
            logger.error(
                "Failed to decode tournament config JSON.", exc_info=True
            )
            await interaction.response.send_message(
                "Error reading configuration file: Invalid JSON.",
                ephemeral=True
            )
            return
        except Exception as e:
            logger.error(
                "Unexpected error reading tournament config: %s",
                e,
                exc_info=True
            )
            await interaction.response.send_message(
                "An unexpected error occurred reading the configuration.",
                ephemeral=True
            )
            return

        if not tournaments:
            await interaction.response.send_message(
                "The sync list is currently empty.", ephemeral=True
            )
            return

        formatted_list = "\n".join(f"- `{slug}`" for slug in tournaments)
        embed = discord.Embed(
            title="Tournament Sync List",
            description=(
                "The following tournaments are configured for syncing:\n"
                f"{formatted_list}"
            ),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigureSync(bot))

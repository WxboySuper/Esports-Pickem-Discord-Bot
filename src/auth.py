import os
import discord
from discord import app_commands


def get_admin_ids() -> list[int]:
    """Reads and returns the list of admin user IDs from the environment."""
    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    if not raw_admin_ids:
        return []
    admin_ids = []
    for x in raw_admin_ids.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            admin_ids.append(int(x))
        except ValueError:
            continue
    return admin_ids


def is_admin() -> bool:
    """Custom check decorator to verify if the user is an admin."""

    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id in get_admin_ids()

    return app_commands.check(predicate)

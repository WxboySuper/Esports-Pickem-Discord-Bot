import discord
from discord import app_commands
from discord.ext import commands
from src.db import get_session
from src.models import Contest, Match, Pick, Result
from src.config import ADMIN_IDS


def is_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id in ADMIN_IDS

    return app_commands.check(predicate)


class Wipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="wipe-data",
        description="Wipe all contest data from the database.",
    )
    @is_admin()
    async def wipe_data(self, interaction: discord.Interaction):
        async with get_session() as session:
            await session.exec(Result).delete()
            await session.exec(Pick).delete()
            await session.exec(Match).delete()
            await session.exec(Contest).delete()
            await session.commit()
        await interaction.response.send_message(
            "All contest data has been wiped.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Wipe(bot))

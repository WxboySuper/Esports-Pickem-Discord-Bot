import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import delete
from src.db import get_session
from src.models import Contest, Match, Pick, Result
from src.auth import is_admin




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
            await session.exec(delete(Result))
            await session.exec(delete(Pick))
            await session.exec(delete(Match))
            await session.exec(delete(Contest))
            await session.commit()
        await interaction.response.send_message(
            "All contest data has been wiped.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Wipe(bot))

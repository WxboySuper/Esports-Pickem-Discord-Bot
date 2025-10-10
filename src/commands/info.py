# src/commands/info.py
# Info/help command as a slash command

import logging
import discord

logger = logging.getLogger("esports-bot.commands.info")


async def setup(bot):
    @bot.tree.command(name="info", description="Bot and repository information")
    async def info(interaction: discord.Interaction):
        logger.debug("Info command invoked by user %s", interaction.user.id)
        embed = discord.Embed(
            title="Esports Pick'em Bot",
            description="A list of commands plus extra tips.",
            color=0x2D9CDB,
        )
        embed.add_field(
            name="Commands",
            value="\n".join(
                [f"/{c.name} - {c.description}" for c in bot.tree.get_commands()]
            ),
            inline=False,
        )
        embed.set_footer(text="Configured to use slash commands (app_commands).")
        await interaction.response.send_message(embed=embed, ephemeral=True)

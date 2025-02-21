import discord
from discord.ext import commands
from discord import app_commands
import logging
import sqlite3
from datetime import datetime

class EventHandlers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot')

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("=== Bot Ready ===")
        self.logger.info("Connected as %s", self.bot.user.name)
        
        guild_info = [f"- {guild.name} (id: {guild.id})" for guild in self.bot.guilds]
        self.logger.info("Connected to %d guilds:\n%s", len(self.bot.guilds), '\n'.join(guild_info))

        try:
            self.logger.info("Syncing commands...")
            await self.bot.tree.sync()
        except Exception as e:
            self.logger.error("Error syncing commands: %s", e)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.logger.info("Joined new guild: %s (ID: %s)", guild.name, guild.id)
        try:
            channel = await self.bot.announcer.get_announcement_channel(guild)
            if channel:
                welcome_embed = discord.Embed(
                    title="🎮 Pick'em Bot Setup Complete",
                    description="Thanks for adding Pick'em Bot! Use `/help` to get started!",
                    color=discord.Color.green()
                )
                await channel.send(embed=welcome_embed)
        except Exception as e:
            self.logger.error("Error setting up new guild %s: %s", guild.name, e)

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        self.logger.error("An error occurred in %s", event, exc_info=True)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.errors.CommandInvokeError):
            if 'audioop' in str(error):
                await ctx.send("Voice functionality is currently unavailable.")
            else:
                await ctx.send(f"An error occurred: {str(error)}")
        self.logger.error("Command error: %s", error, exc_info=True)

    @commands.Cog.listener()
    async def on_interaction_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        error_msg = "An error occurred while processing your command."
        if isinstance(error, app_commands.CommandOnCooldown):
            error_msg = f"This command is on cooldown. Try again in {error.retry_after:.1f}s"
        elif isinstance(error, app_commands.MissingPermissions):
            error_msg = "You don't have permission to use this command."

        try:
            await interaction.response.send_message(error_msg, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(error_msg, ephemeral=True)

        self.logger.error("Interaction error: %s", error, exc_info=True)

async def setup(bot):
    await bot.add_cog(EventHandlers(bot))

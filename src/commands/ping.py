# src/commands/ping.py
# Simple ping/health slash command using app_commands

import logging
import discord

logger = logging.getLogger("esports-bot.commands.ping")


async def setup(bot):
    @bot.tree.command(name="ping", description="Check bot latency")
    async def ping(interaction: discord.Interaction):
        logger.debug("Ping command invoked by user %s", interaction.user.id)
        # Use bot.latency for websocket heartbeat latency and report ms
        latency_ms = int(bot.latency * 1000) if bot.latency else "unknown"
        await interaction.response.send_message(
            f"Pong! websocket latency: {latency_ms} ms",
            ephemeral=True
            )

"""
src/app.py - Minimal Discord bot using app_commands (slash commands).
Environment variables used:
- DISCORD_TOKEN
- DEVELOPER_GUILD_ID (optional; for fast dev guild command registration)
- LOG_LEVEL (optional; DEBUG/INFO/WARNING/ERROR)
- ADMIN_IDS (optional, comma-separated user IDs)
"""

import os
import logging
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("esports-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEV_GUILD_ID = os.getenv("DEVELOPER_GUILD_ID")
_raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = []
if _raw_admin_ids.strip():
    for part in _raw_admin_ids.split(","):
        token = part.strip()
        if not token:
            continue
        if token.isdigit():
            try:
                ADMIN_IDS.append(int(token))
            except ValueError:
                logger.warning(
                    "ADMIN_IDS entry could not be converted to int: %r",
                    token,
                )
        else:
            logger.warning("Ignoring non-numeric ADMIN_IDS entry: %r", token)

intents = discord.Intents.default()


class EsportsBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Import and register command modules
        # Each command module exposes async def setup(bot)
        from commands import ping, info  # local imports
        await ping.setup(self)
        await info.setup(self)

        # Always perform GLOBAL sync; guild-specific sync disabled.
        try:
            logger.info("Starting Global Sync...")
            await self.tree.sync()
            logger.info("Performed GLOBAL command sync.")
        except Exception as exc:
            logger.exception("Failed performing global command sync: %s", exc)


bot = EsportsBot()


@bot.event
async def on_ready():
    logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id)


@bot.event
async def on_error(event, *args, **kwargs):
    logger.exception("Unhandled exception in event %s", event)


def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set. Exiting.")
        sys.exit(1)
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Shutting down.")
    except Exception:
        logger.exception("Bot terminated unexpectedly.")
        raise


if __name__ == "__main__":
    main()

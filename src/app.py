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
import importlib
import pkgutil
import inspect

import discord
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("esports-bot")

logger.info("Startup cwd=%s", os.getcwd())
logger.debug("Startup sys.path (first entries)=%s", sys.path[:6])

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
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
        # Dynamically discover and load all commands in the commands directory.
        commands_pkg = None

        # Prefer importing the commands package relative to this module's
        # package.
        if __package__:
            pkg_name = f"{__package__}.commands"
            try:
                commands_pkg = importlib.import_module(pkg_name)
            except ImportError:
                logger.debug("Package %s not found: %s",
                             pkg_name, sys.path[:6])

        # Fallback: try importing top-level 'commands' package
        if commands_pkg is None:
            try:
                commands_pkg = importlib.import_module("commands")
            except ImportError:
                logger.error(
                    "Could not import 'commands' package; no commands loaded. "
                    "Ensure either: (1) you run the app as a module "
                    "or (2) /path/to/src is on PYTHONPATH, or change imports "
                    "to be relative."
                )
                commands_pkg = None

        if commands_pkg is not None:
            for module_info in pkgutil.iter_modules(commands_pkg.__path__):
                name = module_info.name
                if name.startswith("_"):
                    continue  # skip private/dunder modules
                full_name = f"{commands_pkg.__name__}.{name}"
                try:
                    mod = importlib.import_module(full_name)
                    setup_fn = getattr(mod, "setup", None)
                    if setup_fn is None:
                        logger.debug(
                            "Module %s has no setup(bot); skipping", full_name
                        )
                        continue
                    if inspect.iscoroutinefunction(setup_fn):
                        await setup_fn(self)
                    else:
                        setup_fn(self)
                    logger.info("Loaded command module: %s", full_name)
                except Exception:
                    logger.exception(
                        "Failed loading command module %s",
                        full_name,
                    )

        # Global sync
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

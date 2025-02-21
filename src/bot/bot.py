import sys
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import discord
from discord.ext import commands
import asyncio
from src.utils.db import PickemDB
from src.utils import path_helper
from src.utils.bot_instance import BotInstance
from src.bot.config.config import Config
from src.bot.announcer import AnnouncementManager

# Setup paths
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

path_helper.setup_path()
load_dotenv()

def setup_bot_logging():
    """Set up bot logging"""
    logger = logging.getLogger('bot')
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    logger.handlers.clear()

    # Configure format
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Set up file handler
    log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / 'bot.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Create logger instance
logger = setup_bot_logging()

# Load config
config = Config.get_config()
logger.info("Running in %s mode", 'PRODUCTION' if config.is_production else 'TEST')

TOKEN = config.DISCORD_TOKEN
APP_ID = config.APP_ID


class CustomBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.all(),
            application_id=config.APP_ID
        )
        self.config = config
        logger.info("Initializing bot...")
        self.announcer = AnnouncementManager(self)
        logger.info("Announcer created")
        self.db = PickemDB()
        logger.info("Database initialized")
        self.db.set_announcer(self.announcer)
        logger.info("Announcer set on database")
        self.status_task = None
        logger.info("Bot initialization complete")

    async def setup_hook(self):
        """Load extensions and sync commands"""
        logger.info("Loading extensions...")
        await self.load_extension("src.bot.commands.admin_commands")
        await self.load_extension("src.bot.commands.user_commands")
        await self.load_extension("src.bot.commands.match_commands")
        await self.load_extension("src.bot.events.handlers")

        logger.info("Syncing commands...")
        await self.tree.sync()

    async def update_status(self):
        """Background task to update bot status"""
        try:
            while not self.is_closed():
                ongoing_matches = self.db.get_ongoing_matches()
                if ongoing_matches:
                    current_match = ongoing_matches[0]
                    activity = discord.Activity(
                        type=discord.ActivityType.watching,
                        name=f"{current_match[2]} vs {current_match[3]}"
                    )
                else:
                    activity = discord.Activity(
                        type=discord.ActivityType.listening,
                        name="your picks | /pick"
                    )
                await self.change_presence(activity=activity)
                await asyncio.sleep(300)
        except Exception as e:
            logger.error("Status update error: %s", e)

# Create bot instance
bot = CustomBot()
BotInstance.set_bot(bot)

if __name__ == '__main__':
    try:
        logger.info("Starting bot...")
        bot.run(config.DISCORD_TOKEN)
    except Exception as e:
        logger.critical("Failed to start bot: %s", e)
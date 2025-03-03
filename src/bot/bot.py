import sys
import os
from pathlib import Path
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands, ui, ButtonStyle
import asyncio
import sqlite3
from src.utils.db import PickemDB  # Import db from utils
from src.utils import path_helper
from src.utils.bot_instance import BotInstance
from src.bot.config.config import Config

# Get the src directory path
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

path_helper.setup_path()

# Load environment variables
load_dotenv()

bot_logger = logging.getLogger('bot')

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent.parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Configure logging
log_file = logs_dir / "bot.log"
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=5*1024*1024,  # 5MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)

# Set up root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Remove any existing handlers

# Add handlers
logger.addHandler(file_handler)


# Add this helper function near the top of the file after imports
def get_discord_timestamp(dt: datetime, style: str = 'R') -> str:
    """Convert datetime to Discord timestamp
    Styles:
    t: Short Time (16:20)
    T: Long Time (16:20:30)
    d: Short Date (20/04/2021)
    D: Long Date (20 April 2021)
    f: Short Date/Time (20 April 2021 16:20)
    F: Long Date/Time (Tuesday, 20 April 2021 16:20)
    R: Relative Time (2 months ago)
    """
    return f"<t:{int(dt.timestamp())}:{style}>"

# Add this helper function near the top with other helpers
def parse_datetime(date_str: str, time_str: str) -> datetime:
    """Convert date and AM/PM time to datetime object"""
    try:
        # Parse the time in 12-hour format
        time_obj = datetime.strptime(time_str.strip(), "%I:%M %p").time()
        # Parse the date
        date_obj = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        # Combine them
        return datetime.combine(date_obj, time_obj)
    except ValueError as date_error:
        raise ValueError("Invalid date/time format. Use: YYYY-MM-DD for date and HH:MM AM/PM for time") from date_error

# Add this helper function near other helpers at the top of the file
def ensure_datetime(date_value) -> datetime:
    """Convert string or datetime to datetime object"""
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
        except ValueError as val_error:
            raise ValueError(f"Invalid datetime format: {date_value}") from val_error
    elif isinstance(date_value, datetime):
        return date_value
    else:
        raise ValueError(f"Cannot convert {type(date_value)} to datetime")


config = Config.get_config()
bot_logger.info("Running in %s mode", {'PRODUCTION' if config.is_production else 'TEST'})

# Replace TOKEN and APP_ID assignment
TOKEN = config.DISCORD_TOKEN
APP_ID = config.APP_ID

def validate_user_id(user_id: str) -> int:
    """Validate and convert user ID to integer"""
    if not user_id:
        raise ValueError("Owner user ID not set in environment variables")
    try:
        return int(user_id)
    except ValueError:
        raise ValueError("Invalid owner user ID. Must be an integer") from None


USER_ID = validate_user_id(os.getenv("OWNER_USER_DISCORD_ID"))

class AnnouncementManager:
    def __init__(self, bot_instance):  # Renamed parameter from 'bot' to 'bot_instance'
        self.bot = bot_instance  # More explicit naming of the instance

    @staticmethod
    async def get_announcement_channel(guild):
        """Find the pickem-updates channel in a guild"""
        channel = discord.utils.get(guild.text_channels, name="pickem-updates")
        if not channel:
            try:
                channel = await guild.create_text_channel(
                    'pickem-updates',
                    topic="Match announcements and results for Pick'em",
                    reason="Required for Pick'em announcements"
                )
            except discord.Forbidden:
                return None
        return channel

    async def announce_match_result(self, match_id: int, team_a: str, team_b: str, winner: str, league_name: str):
        """Send match result announcement to all guilds"""
        # Get voting statistics from database
        total_picks = 0
        correct_picks = 0
        try:
            with sqlite3.connect(self.bot.db.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT COUNT(*) as total_picks,
                           SUM(CASE WHEN pick = ? THEN 1 ELSE 0 END) as correct_picks
                    FROM picks
                    WHERE match_id = ?
                """, (winner, match_id))
                result = c.fetchone()
                if result:
                    total_picks = result[0]
                    correct_picks = result[1] or 0
        except sqlite3.Error as sqlite_error:
            bot_logger.error("Database error in match result announcement: %s", sqlite_error)
        except discord.errors.Forbidden as permission_error:
            bot_logger.error("Permission error in match result announcement: %s", permission_error)
        except discord.errors.HTTPException as discord_http_error:
            bot_logger.error("HTTP error in match result announcement: %s", discord_http_error)

        # Create embed with voting statistics
        embed = discord.Embed(
            title="🏆 Match Result!",
            description="The winner has been decided!",
            color=discord.Color.gold()
        )

        # Calculate percentage
        accuracy = (correct_picks / total_picks * 100) if total_picks > 0 else 0

        embed.add_field(
            name="Match Details",
            value=f"🏆 **{team_a}** vs **{team_b}**\n"
                  f"Winner: **||{winner}||**\n\n"
                  f"📊 **Pick Statistics**\n"
                  f"Total Picks: {total_picks}\n"
                  f"Correct Picks: {correct_picks}\n"
                  f"Accuracy: {accuracy:.1f}%",  # Changed from .1 to .1f
            inline=False
        )
        embed.set_footer(text=f"Match ID: {match_id} 🎮 {league_name}")

        for guild in self.bot.guilds:
            if channel := await self.get_announcement_channel(guild):
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    continue

    async def announce_bot_status(self, status: str, shutdown_type: str = None):
        """Send bot status announcement to all guilds"""
        if status == "online":
            embed = discord.Embed(
                title="🤖 Bot Status Update",
                description="Pick'em Bot is now online and ready!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Status",
                value="🟢 Online and accepting picks",
                inline=False
            )
        else:  # offline
            colors = {
                "normal": discord.Color.red(),
                "update": discord.Color.blue(),
                "restart": discord.Color.gold(),
                "bugfix": discord.Color.orange()
            }
            messages = {
                "normal": "Bot is shutting down for maintenance",
                "update": "Bot is being updated with new features",
                "restart": "Bot is restarting",
                "bugfix": "Bot is being shutdown to fix bugs"
            }

            embed = discord.Embed(
                title="🤖 Bot Status Update",
                description=messages.get(shutdown_type, "Bot is going offline"),
                color=colors.get(shutdown_type, discord.Color.red())
            )
            embed.add_field(
                name="Status",
                value="🔴 Going offline",
                inline=False
            )

        for guild in self.bot.guilds:
            if channel := await self.get_announcement_channel(guild):
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    continue

    # Replace the update_match_update function in AnnouncementManager class
    async def announce_match_update(self, match_id: int, old_details: dict, new_details: dict, league_name: str):
        """Send announcement for match updates"""
        embed = discord.Embed(
            title="📝 Match Details Updated",
            color=discord.Color.blue()
        )

        try:
            # Format datetime objects for display
            old_date = ensure_datetime(old_details['match_date'])
            new_date = ensure_datetime(new_details['match_date'])

            changes = []
            if old_details['team_a'] != new_details['team_a'] or old_details['team_b'] != new_details['team_b']:
                changes.append(f"Teams: {old_details['team_a']} vs {old_details['team_b']} ➔ "
                            f"{new_details['team_a']} vs {new_details['team_b']}")
            if old_date != new_date:
                changes.append(f"Date: {get_discord_timestamp(old_date, 'F')} ➔ "
                            f"{get_discord_timestamp(new_date, 'F')}")
            if old_details['match_name'] != new_details['match_name']:
                changes.append(f"Type: {old_details['match_name']} ➔ {new_details['match_name']}")

            embed.description = (
                f"**{league_name}** - Match #{match_id}\n\n"
                "**Changes:**\n" + "\n".join(f"• {change}" for change in changes)
            )

            for guild in self.bot.guilds:
                if channel := await self.get_announcement_channel(guild):
                    try:
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        continue

        except ValueError as datetime_error:
            bot_logger.error("Date parsing error in match update announcement: %s", datetime_error)
        except Exception as announce_error:
            bot_logger.error("Error in match update announcement: %s", announce_error)

    async def send_custom_announcement(self, title: str, message: str, color: discord.Color = discord.Color.blue()):
        """Send a custom announcement to all guilds"""
        embed = discord.Embed(
            title=title,
            description=message,
            color=color,
            timestamp=datetime.now()
        )

        success_count = 0
        fail_count = 0

        for guild in self.bot.guilds:
            if channel := await self.get_announcement_channel(guild):
                try:
                    await channel.send(embed=embed)
                    success_count += 1
                except discord.Forbidden:
                    fail_count += 1
                    continue

        return success_count, fail_count

    async def announce_new_match(self, match_id: int, team_a: str, team_b: str, match_date: datetime, league_name: str, match_name: str) -> bool:
        """Send new match announcement to all guilds"""
        try:
            embed = discord.Embed(
                title="🎮 New Match Scheduled!",
                color=discord.Color.blue()
            )

            embed.add_field(
                name=f"{league_name}",
                value=(
                    f"🏆 **{team_a}** vs **{team_b}**\n"
                    f"⏰ {get_discord_timestamp(match_date, 'F')}\n"
                    f"📊 {match_name}"
                ),
                inline=False
            )
            embed.set_footer(text=f"Match ID: {match_id}")

            success = False
            for guild in self.bot.guilds:
                if channel := await self.get_announcement_channel(guild):
                    try:
                        await channel.send(embed=embed)
                        success = True
                    except discord.Forbidden:
                        continue

            return success

        except Exception as e:
            logging.error("Error announcing new match: %s", e)
            return False

class CustomBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.all(),
            application_id=config.APP_ID
        )

        self.config = config

        bot_logger.info("Initializing bot...")
        self.announcer = AnnouncementManager(self)
        bot_logger.info("Announcer created")
        self.db = PickemDB()  # Use imported class directly
        bot_logger.info("Database initialized")
        self.db.set_announcer(self.announcer)  # Set announcer for database events
        bot_logger.info("Announcer set on database")
        self.status_task = None  # Add this line
        bot_logger.info("Bot initialization complete")

    async def setup_hook(self):
        """This is called when the bot starts, sets up the command tree"""
        bot_logger.info("Setting up command tree...")
        await self.tree.sync()
        bot_logger.info("Command tree synced")

    async def update_status(self):
        """Background task to update bot status based on match state"""
        try:
            while not self.is_closed():
                # Get current ongoing matches
                ongoing_matches = self.db.get_ongoing_matches()

                if ongoing_matches:
                    # Get the first ongoing match - rename to current_match to avoid shadowing
                    current_match = ongoing_matches[0]
                    team_a, team_b = current_match[2], current_match[3]

                    # Set watching status for the match
                    activity = discord.Activity(
                        type=discord.ActivityType.watching,
                        name=f"{team_a} vs {team_b}"
                    )
                    await self.change_presence(activity=activity, status=discord.Status.online)
                else:
                    # Set default status when no matches are ongoing
                    activity = discord.Activity(
                        type=discord.ActivityType.listening,
                        name="your picks | /pick"
                    )
                    await self.change_presence(activity=activity, status=discord.Status.online)

                # Update every 5 minutes
                await asyncio.sleep(300)
        except discord.errors.ConnectionClosed as discord_conn_error:
            bot_logger.error("Connection error in status update task: %s", discord_conn_error)
        except discord.errors.HTTPException as status_http_error:
            bot_logger.error("HTTP error in status update task: %s", status_http_error)
        except asyncio.CancelledError:
            bot_logger.info("Status update task cancelled")
            raise
        except Exception as update_error:
            bot_logger.error("Unexpected error in status update task: %s", update_error)


# Replace bot initialization
bot = CustomBot()
BotInstance.set_bot(bot)  # Store bot instance globally

class StartupView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Button won't timeout

    @discord.ui.button(label="Make Picks!", style=ButtonStyle.primary, emoji="🎮")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get the pick command
        pick_command = bot.tree.get_command("pick")

        # Execute the pick command
        if pick_command:
            await pick_command.callback(interaction)
        else:
            await interaction.response.send_message("Pick command not found!", ephemeral=True)

class ShutdownView(ui.View):
    def __init__(self):
        super().__init__(timeout=10)  # Button disappears after 10 seconds

    @ui.button(label="Cancel Shutdown", style=ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Shutdown cancelled!", ephemeral=True)
        self.stop()

class MatchPicksView(ui.View):
    def __init__(self, guild_id: int, matches: list, db: PickemDB):
        super().__init__(timeout=300)  # 5 minute timeout
        self.guild_id = guild_id
        self.matches = matches
        self.db = db
        self.current_index = 0

        # Update navigation button states
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.matches) - 1

        # Remove old team buttons
        for child in self.children[:]:
            if isinstance(child, ui.Button) and child.custom_id and child.custom_id.startswith("pick_"):
                self.remove_item(child)

        # Get current match - rename to current_match
        current_match = self.matches[self.current_index]
        match_id, team_a, team_b = current_match[0], current_match[1], current_match[2]

        # Add new team buttons
        team_a_button = ui.Button(label=team_a, style=ButtonStyle.primary, custom_id=f"pick_{match_id}_{team_a}")
        team_b_button = ui.Button(label=team_b, style=ButtonStyle.primary, custom_id=f"pick_{match_id}_{team_b}")

        team_a_button.callback = self.pick_callback
        team_b_button.callback = self.pick_callback

        self.add_item(team_a_button)
        self.add_item(team_b_button)

    async def pick_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        _, match_id, team = custom_id.split("_")

        success = self.db.make_pick(self.guild_id, interaction.user.id, int(match_id), team)
        if success:
            await interaction.response.send_message(f"You picked {team}!", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Failed to record pick. Match might have already started or finished.",
                ephemeral=True
            )

    @ui.button(label="◀️ Previous Match", style=ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_buttons()
            await self.update_message(interaction)

    @ui.button(label="Next Match ▶️", style=ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index < len(self.matches) - 1:
            self.current_index += 1
            self.update_buttons()
            await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = self.create_pick_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_pick_embed(self) -> discord.Embed:
        # Rename match to current_match
        current_match = self.matches[self.current_index]
        # Unpack all 9 values from the match tuple
        # skipcq: PYL-W0612
        match_id, team_a, team_b, match_date, is_active, league_name, league_region, match_name = current_match

        match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

        embed = discord.Embed(
            title=f"🎮 {league_name} - Match {self.current_index + 1}/{len(self.matches)}",
            description=f"📅 {get_discord_timestamp(match_datetime, 'F')}\n"
                       f"⏰ Time until match: {get_discord_timestamp(match_datetime, 'R')}\n"
                       f"🌍 {league_region}\n"
                       f"📊 {match_name}\n\n"
                       f"**{team_a}** vs **{team_b}**",
            color=discord.Color.blue()
        )
        return embed

class MatchesView(ui.View):
    def __init__(self, matches_by_day: dict, current_date: datetime):
        super().__init__(timeout=300)  # 5 minute timeout
        self.matches = matches_by_day
        self.current_date = current_date
        self.dates = sorted(matches_by_day.keys())
        self.current_index = self.dates.index(current_date.date())

        # Disable buttons if at start/end of date range
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

    @ui.button(label="◀️ Previous Day", style=ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    @ui.button(label="Next Day ▶️", style=ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index < len(self.dates) - 1:
            self.current_index += 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = create_matches_embed(self.matches[self.dates[self.current_index]], self.current_date)

        # Update button states
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

        await interaction.response.edit_message(embed=embed, view=self)

def create_matches_embed(matches: list, date: datetime) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎮 Matches for {date.strftime('%B %d, %Y')}",
        color=discord.Color.blue()
    )

    for match_data in matches:  # Rename match to match_data
        try:
            _, team_a, team_b, winner, match_date, _, league_name, league_region, match_name = match_data
        except ValueError:
            # Fallback for matches without match_name
            _, team_a, team_b, winner, match_date, _, league_name, league_region = match_data
            match_name = "N/A"  # Default value

        match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

        # Format status/winner text
        if winner:
            status = f"Winner: ||{winner}||"
        elif match_datetime <= datetime.now():
            status = "Match Ongoing"
        else:
            status = f"Starts {get_discord_timestamp(match_datetime, 'R')}"

        embed.add_field(
            name=f"{league_name} - {get_discord_timestamp(match_datetime, 'T')}",
            value=f"🏆 {team_a} vs {team_b}\n"
                  f"📊 {match_name}\n"
                  f"🌍 {league_region}\n"
                  f"📅 {status}",
            inline=False
        )

    if not matches:
        embed.description = "No matches scheduled for this day."

    return embed

class SummaryView(ui.View):
    def __init__(self, user_id: int, guild_id: int, matches_by_day: dict, db: PickemDB, current_date: datetime):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_id = user_id
        self.guild_id = guild_id
        self.match_data = matches_by_day  # Renamed from matches to match_data
        self.db = db
        self.current_date = current_date
        self.dates = sorted(matches_by_day.keys())
        self.current_index = self.dates.index(current_date.date())

        # Disable navigation buttons if at start/end of date range
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

    @ui.button(label="◀️ Previous Day", style=ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    @ui.button(label="Next Day ▶️", style=ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index < len(self.dates) - 1:
            self.current_index += 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = create_summary_embed(
            self.user_id,
            self.guild_id,
            self.match_data[self.dates[self.current_index]],  # Using self.match_data instead of self.matches
            self.current_date,
            self.db
        )

        # Update button states
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

        await interaction.response.edit_message(embed=embed, view=self)

def create_summary_embed(user_id: int, guild_id: int, matches: list, date: datetime, db: PickemDB) -> discord.Embed:
    embed = discord.Embed(
        title=f"📊 Pick'em Summary for {date.strftime('%B %d, %Y')}",
        color=discord.Color.blue()
    )

    # Initialize counters
    total_matches = len(matches)
    unpicked_matches = 0
    completed_matches = 0
    pending_matches = 0
    correct_picks = 0

    if total_matches == 0:
        embed.description = "No matches scheduled for this day."
        return embed

    # Process each match - rename match to match_data
    for match_data in matches:
        match_id, team_a, team_b, winner, match_date, _, league_name, league_region, match_name = match_data
        match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

        # Get user's pick for this match - rename pick to user_pick to be more specific
        user_pick = db.get_user_pick(guild_id, user_id, match_id)

        # Determine match status and format field
        if winner:  # Completed match
            completed_matches += 1
            status = "✅ Correct!" if user_pick == winner else "❌ Incorrect"
            if user_pick == winner:
                correct_picks += 1
            pick_str = f"You picked: **{user_pick}**\nWinner: ||{winner}||"
        elif match_datetime <= datetime.now():  # Ongoing match
            pending_matches += 1
            status = "🔄 In Progress"
            pick_str = f"You picked: **{user_pick}**" if user_pick else "❌ No pick made"
        else:  # Future match
            if not user_pick:
                unpicked_matches += 1
            status = "⏰ Upcoming"
            pick_str = f"You picked: **{user_pick}**" if user_pick else "❌ No pick made"

        embed.add_field(
            name=f"{league_name} - {get_discord_timestamp(match_datetime, 'T')}",
            value=f"🏆 **{team_a}** vs **{team_b}**\n"
                  f"📊 {match_name}\n"
                  f"🌍 {league_region}\n"
                  f"📊 {status}\n"
                  f"🎯 {pick_str}",
            inline=False
        )

    # Add summary statistics
    stats = (
        f"Total Matches: {total_matches}\n"
        f"Completed: {completed_matches} "
        f"({correct_picks}/{completed_matches} correct)\n"
        f"In Progress: {pending_matches}\n"
        f"Upcoming (unpicked): {unpicked_matches}"
    )

    embed.description = stats
    return embed

@bot.tree.command(name="shutdown", description="Shutdown the bot")
@app_commands.describe(
    shutdown_type="Type of Shutdown Message. Options: [normal, update, restart, bugfix]"
)
@app_commands.guild_only()
async def shutdown_bot(interaction: discord.Interaction, shutdown_type: str):
    """Shuts down the bot"""
    bot_logger.info("Shutdown command initiated by %s (ID: %s) with type: %s", interaction.user.name, interaction.user.id, shutdown_type)
    if interaction.user.id != USER_ID:
        await interaction.response.send_message("❌ This command is only available to the bot owner!", ephemeral=True)
        return

    valid_types = ["normal", "update", "restart", "bugfix"]
    if shutdown_type not in valid_types:
        await interaction.response.send_message(
            f"❌ Invalid shutdown type. Please use one of: {', '.join(valid_types)}",
            ephemeral=True
        )
        return

    messages = {
        "normal": ("🔄 Bot Shutdown Initiated", discord.Color.red()),
        "update": ("🔄 Bot Update Initiated", discord.Color.blue()),
        "restart": ("🔄 Bot Restart Initiated", discord.Color.gold()),
        "bugfix": ("🔄 Bot Bugfix Initiated", discord.Color.orange())
    }

    embed = discord.Embed(
        title=messages[shutdown_type][0],
        description="Bot is preparing to shutdown...",
        color=messages[shutdown_type][1]
    )
    embed.set_footer(text="Bot will be offline in 10 seconds")

    view = ShutdownView()
    await interaction.response.send_message(embed=embed, view=view)

    # Wait for potential cancel button press
    timeout = await view.wait()

    if not timeout:  # If button was pressed
        return

    # Send announcement before shutting down
    await bot.announcer.announce_bot_status("offline", shutdown_type)

    # Send final message to command channel
    final_embed = discord.Embed(
        title="💤 Bot Shut Down",
        description="🔴 Bot is now offline.",
        color=discord.Color.dark_grey()
    )
    await interaction.channel.send(embed=final_embed)

    # Cancel the status update task before shutting down
    if bot.status_task:
        bot.status_task.cancel()

    # Proper shutdown sequence
    await bot.change_presence(status=discord.Status.invisible)
    await bot.close()

# Replace the pick command implementation
@bot.tree.command(name="pick", description="Make picks for upcoming matches (next 48 hours)")
@app_commands.guild_only()
async def make_pick(interaction: discord.Interaction):  # Rename pick to make_pick
    """Command to make picks for matches within the next 48 hours"""
    guild_id = interaction.guild_id
    bot_logger.info("Pick command used by %s (ID: %s) in guild: %s (ID: %s)", interaction.user.name, interaction.user.id, interaction.guild.name, guild_id)

    upcoming_matches = bot.db.get_upcoming_matches(hours=48)
    matches_to_close = []
    active_matches = []

    if not upcoming_matches:
        embed = discord.Embed(
            title="No Active Matches",
            description="There are no matches available for picks in the next 48 hours.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    for match in upcoming_matches:
        match_id, team_a, team_b, _, _, _, _, _ = match
        if team_a == 'TBD' or team_b == 'TBD':
            matches_to_close.append(match_id)

    for match_id in matches_to_close:
        bot.db.close_match(match_id)

    for match in upcoming_matches:
        match_id, _, _, _, is_active, _, _, _ = match
        if is_active == 1:
            active_matches.append(match)

    view = MatchPicksView(guild_id, active_matches, bot.db)
    embed = view.create_pick_embed()
    await interaction.response.send_message(embed=embed, view=view)

# Update other commands to include guild_id
@bot.tree.command(name="stats", description="View your pick'em statistics")
async def get_stats(interaction: discord.Interaction):  # Renamed from stats to get_stats
    bot_logger.info("Stats command used by %s (ID: %s) in guild: %s",
                   interaction.user.name, interaction.user.id, interaction.guild.name)
    user_stats = bot.db.get_user_stats(interaction.guild_id, interaction.user.id)  # Renamed from stats to user_stats

    # Create ratio string for correct/completed picks
    completed_ratio = f"{user_stats['correct_picks']}/{user_stats['completed_picks']}" \
                    if user_stats['completed_picks'] > 0 else "0/0"

    embed = discord.Embed(
        title="Your Pick'em Stats",
        color=discord.Color.blue()
    )
    embed.add_field(name="Total Picks", value=str(user_stats["total_picks"]))
    embed.add_field(name="Completed Matches", value=completed_ratio)
    embed.add_field(name="Accuracy", value=f"{user_stats['accuracy']:.1%}")

    # Add active picks count
    active_picks = user_stats["total_picks"] - user_stats["completed_picks"]
    embed.add_field(name="Active Picks", value=str(active_picks), inline=False)

    await interaction.response.send_message(embed=embed)

# Modify set_winner command to use the announcer
@bot.tree.command(name="set_winner", description="Set the winner for a match [Owner Only]")
async def set_winner(interaction: discord.Interaction, match_id: int, winner: str):
    """Set the winner for a match and update pick results"""
    bot_logger.info("Set winner command initiated by %s (ID: %s) for match %d", interaction.user.name, interaction.user.id, match_id)
    try:
        # Check if user is owner
        if interaction.user.id != USER_ID:
            await interaction.response.send_message("❌ This command is only available to the bot owner!", ephemeral=True)
            return

        # Get match details before updating
        match_details = bot.db.get_match_details(match_id)
        if not match_details:
            await interaction.response.send_message("❌ Match not found!", ephemeral=True)
            return

        success = bot.db.update_match_result(match_id, winner)
        if success:
            embed = discord.Embed(
                title="✅ Match Result Updated",
                description=f"Match {match_id} winner set to: {winner}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

            try:
                # Send announcement
                team_a, team_b = match_details['team_a'], match_details['team_b']
                await bot.announcer.announce_match_result(match_id, team_a, team_b, winner, match_details['league_name'])
            except Exception as announce_error:
                # Log the announcement error but don't fail the command
                logging.error("Failed to announce match result: %s", announce_error)
        else:
            await interaction.response.send_message("❌ Failed to update match result.", ephemeral=True)

    except sqlite3.Error as db_sqlite_error:
        await interaction.response.send_message(
            f"❌ Database error: {str(db_sqlite_error)}",
            ephemeral=True
        )
    except discord.errors.Forbidden as discord_permission_error:
        await interaction.response.send_message(
            f"❌ Permission error: {str(discord_permission_error)}",
            ephemeral=True
        )
    except discord.errors.HTTPException as cmd_http_error:
        await interaction.response.send_message(
            f"❌ HTTP error: {str(cmd_http_error)}",
            ephemeral=True
        )
    except ValueError as input_error:
        await interaction.response.send_message(
            f"❌ Invalid input: {str(input_error)}",
            ephemeral=True
        )
    except Exception as unexpected_cmd_error:
        await interaction.response.send_message(
            f"❌ An error occurred: {str(unexpected_cmd_error)}",
            ephemeral=True
        )
        logging.error("Error setting match winner: %s", unexpected_cmd_error, exc_info=True)

# Update create_match command
@bot.tree.command(name="create_match", description="Create a new match [Owner Only]")
@app_commands.describe(
    team_a="Name of the first team",
    team_b="Name of the second team",
    match_date="Match date (format: YYYY-MM-DD)",
    match_time="Match time (format: HH:MM AM/PM)",
    match_name="Match type (e.g., Groups, Playoffs, Finals)",
    league_name="Name of the league"
)
async def create_match(
    interaction: discord.Interaction,
    team_a: str,
    team_b: str,
    match_date: str,
    match_time: str,
    match_name: str,
    league_name: str = "Unknown League"
):
    """Create a new match in the database"""
    bot_logger.info("Create match command initiated by %s (ID: %s)", interaction.user.name, interaction.user.id)

    if interaction.user.id != USER_ID:
        bot_logger.warning("Unauthorized create match attempt by %s (ID: %s)", interaction.user.name, interaction.user.id)
        await interaction.response.send_message("❌ This command is only available to the bot owner!", ephemeral=True)
        return

    try:
        # Parse the date and time strings
        try:
            date_obj = parse_datetime(match_date, match_time)
            bot_logger.debug("Parsed datetime: %s", date_obj)
        except ValueError as e:
            bot_logger.error("Date/time parsing error: %s", e)
            await interaction.response.send_message(
                f"❌ {str(e)}",
                ephemeral=True
            )
            return

        bot_logger.info("Creating match: %s vs %s at %s, Type: %s, League: %s", team_a, team_b, date_obj, match_name, league_name)

        # Get league ID (use default league if not found)
        league_id = 1  # Default league ID

        if team_a == "TBD" or team_b == "TBD":
            is_active = 0
        else:
            is_active = 1

        # Create the match with all required parameters
        match_id = bot.db.add_match(
            league_id=league_id,
            team_a=team_a,
            team_b=team_b,
            match_date=date_obj,
            is_active=is_active,
            match_name=match_name
        )

        if match_id:
            bot_logger.info("Match created successfully with ID: %d", match_id)
            embed = discord.Embed(
                title="✅ Match Created",
                description=f"Match #{match_id} has been created globally",
                color=discord.Color.green()
            )
            embed.add_field(name="Team 1", value=team_a, inline=True)
            embed.add_field(name="Team 2", value=team_b, inline=True)
            embed.add_field(name="Type", value=match_name, inline=True)
            embed.add_field(name="Date/Time", value=f"{match_date} at {match_time}", inline=False)
            embed.add_field(name="League", value=league_name, inline=False)

            await interaction.response.send_message(embed=embed)

            # Announce the new match
            await bot.announcer.announce_new_match(match_id, team_a, team_b, date_obj, league_name, match_name)
        else:
            bot_logger.error("Failed to create match: Database returned None")
            await interaction.response.send_message("❌ Failed to create match", ephemeral=True)

    except sqlite3.Error as db_error:
        bot_logger.error("Database error creating match: %s", db_error)
        await interaction.response.send_message(
            "❌ Failed to create match in database",
            ephemeral=True
        )
    except discord.errors.HTTPException as http_error:
        bot_logger.error("Failed to send response: %s", http_error)
        await interaction.response.send_message(
            "❌ Failed to send response",
            ephemeral=True
        )
    except ValueError as val_error:
        await interaction.response.send_message(
            f"❌ Invalid input: {str(val_error)}",
            ephemeral=True
        )

@bot.tree.command(name="matches", description="Show matches by day")
async def show_matches(interaction: discord.Interaction):  # Renamed from matches to show_matches
    bot_logger.info("Matches command used by %s (ID: %s) in guild: %s",
                   interaction.user.name, interaction.user.id, interaction.guild.name)
    # Display matches organized by day with navigation
    all_matches = bot.db.get_all_matches()

    if not all_matches:
        await interaction.response.send_message("No matches found.", ephemeral=True)
        return

    # Group matches by day
    matches_by_day = {}
    for match_data in all_matches:  # Renamed from match to match_data
        match_date = datetime.strptime(str(match_data[4]), '%Y-%m-%d %H:%M:%S').date()
        if match_date not in matches_by_day:
            matches_by_day[match_date] = []
        matches_by_day[match_date].append(match_data)

    # Start with current day or nearest future day
    current_date = datetime.now()
    future_dates = [d for d in matches_by_day if d >= current_date.date()]
    if future_dates:
        current_date = datetime.combine(min(future_dates), datetime.min.time())
    else:
        current_date = datetime.combine(max(matches_by_day.keys()), datetime.min.time())

    # Create initial embed and view
    initial_embed = create_matches_embed(matches_by_day[current_date.date()], current_date)
    view = MatchesView(matches_by_day, current_date)

    await interaction.response.send_message(embed=initial_embed, view=view)

@bot.tree.command(name="activepicks", description="View your active picks for upcoming matches")
@app_commands.guild_only()
async def activepicks(interaction: discord.Interaction):
    bot_logger.info("Active picks command used by %s (ID: %s) in guild: %s", interaction.user.name, interaction.user.id, interaction.guild.name)
    # Display all active picks for the user
    guild_id = interaction.guild_id
    user_id = interaction.user.id

    # Get user's display name (nickname if set, otherwise username)
    user_display_name = interaction.user.display_name

    # Get active picks from database
    active_picks = bot.db.get_active_picks(guild_id, user_id)

    if not active_picks:
        embed = discord.Embed(
            title=f"{user_display_name}'s Active Picks",
            description="No active picks for upcoming matches.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"{user_display_name}'s Active Picks",
        description=f"Currently has {len(active_picks)} active picks",
        color=discord.Color.blue()
    )

    # Rest of the embed creation remains the same
    for pick in active_picks:
        _, team_a, team_b, match_date, picked_team, league_name, league_region, match_name = pick

        # Format match date
        match_datetime = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

        # Create field for each pick
        embed.add_field(
            name=f"{league_name} - {get_discord_timestamp(match_datetime, 'f')}",
            value=f"🏆 {team_a} vs {team_b}\n"
                  f"🎯 Your Pick: **{picked_team}**\n"
                  f"⏰ Starts {get_discord_timestamp(match_datetime, 'R')}\n"
                  f"🌍 {league_region}\n"
                  f"📊 {match_name}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# Add this new class after other View classes
class LeaderboardView(ui.View):
    def __init__(self, guild_id: int, guild_name: str, db: PickemDB):
        super().__init__(timeout=300)  # 5 minute timeout
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.db = db
        self.current_timeframe = 'all'

    @ui.button(label="Daily", style=ButtonStyle.primary)
    async def daily_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_timeframe = 'daily'
        await self.update_leaderboard(interaction)

    @ui.button(label="Weekly", style=ButtonStyle.primary)
    async def weekly_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_timeframe = 'weekly'
        await self.update_leaderboard(interaction)

    @ui.button(label="All-Time", style=ButtonStyle.primary)
    async def alltime_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_timeframe = 'all'
        await self.update_leaderboard(interaction)

    async def update_leaderboard(self, interaction: discord.Interaction):
        embed = await self.create_leaderboard_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def create_leaderboard_embed(self, guild) -> discord.Embed:
        timeframe_titles = {
            'daily': "Today's",
            'weekly': "This Week's",
            'all': "All-Time"
        }

        timeframe_desc = {
            'daily': "Top players by correct picks today",
            'weekly': "Top players by correct picks this week",
            'all': "Top players by accuracy (minimum 10 picks)"
        }

        embed = discord.Embed(
            title=f"📊 {timeframe_titles[self.current_timeframe]} {guild.name} Leaderboard",
            description=timeframe_desc[self.current_timeframe],
            color=discord.Color.blue()
        )

        # Get leaderboard data
        leaderboard_data = self.db.get_leaderboard_by_timeframe(self.guild_id, self.current_timeframe)

        if not leaderboard_data:
            embed.description = f"No picks found for {timeframe_titles[self.current_timeframe].lower()} leaderboard!"
            return embed

        # Process each user in the leaderboard
        for rank, data in enumerate(leaderboard_data, 1):
            # Try to get member from guild
            if self.current_timeframe == 'all':
                user_id, completed_picks, correct_picks, accuracy = data
            else:
                user_id, completed_picks, correct_picks = data
                accuracy = correct_picks / completed_picks if completed_picks > 0 else 0

            member = guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"

            # Add medal emoji for top 3
            medal = ""
            if rank == 1:
                medal = "🥇 "
            elif rank == 2:
                medal = "🥈 "
            elif rank == 3:
                medal = "🥉 "

            # Format the value based on timeframe
            if self.current_timeframe == 'all':
                value = f"✅ Accuracy: {accuracy:.1%} ({correct_picks}/{completed_picks})"
            else:
                value = f"✅ Correct: {correct_picks}/{completed_picks} ({accuracy:.1%})"

            embed.add_field(
                name=f"{medal}#{rank} - {name}",
                value=value,
                inline=False
            )

        # Update the appearance of buttons based on current timeframe
        for button in self.children:
            button.style = ButtonStyle.primary
            if button.label.lower() == self.current_timeframe or \
               (button.label == "All-Time" and self.current_timeframe == "all"):
                button.style = ButtonStyle.success

        return embed

# Replace the existing leaderboard command with this updated version
@bot.tree.command(name="leaderboard", description="View the server's Pick'em leaderboard")
@app_commands.guild_only()
async def leaderboard(interaction: discord.Interaction):
    bot_logger.info("Leaderboard command used by %s (ID: %s) in guild: %s", interaction.user.name, interaction.user.id, interaction.guild.name)
    # Display the server's leaderboard with timeframe options
    guild_id = interaction.guild_id
    guild_name = interaction.guild.name

    # Create view with initial state
    view = LeaderboardView(guild_id, guild_name, bot.db)

    # Create initial embed
    initial_embed = await view.create_leaderboard_embed(interaction.guild)

    await interaction.response.send_message(embed=initial_embed, view=view)

@bot.tree.command(name="summary", description="View your daily Pick'em summary")
@app_commands.guild_only()
async def summary(interaction: discord.Interaction):
    bot_logger.info("Summary command used by %s (ID: %s) in guild: %s", interaction.user.name, interaction.user.id, interaction.guild.name)
    # Display a comprehensive daily summary of matches and picks
    guild_id = interaction.guild_id
    user_id = interaction.user.id

    # Get all matches
    all_matches = bot.db.get_all_matches()

    if not all_matches:
        embed = discord.Embed(
            title="📊 Pick'em Summary",
            description="No matches found in the database.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Group matches by day
    matches_by_day = {}
    for match in all_matches:
        match_date = datetime.strptime(str(match[4]), '%Y-%m-%d %H:%M:%S').date()
        if match_date not in matches_by_day:
            matches_by_day[match_date] = []
        matches_by_day[match_date].append(match)

    # Start with current day or nearest future day
    current_date = datetime.now()
    future_dates = [d for d in matches_by_day if d >= current_date.date()]
    if future_dates:
        current_date = datetime.combine(min(future_dates), datetime.min.time())
    else:
        current_date = datetime.combine(max(matches_by_day.keys()), datetime.min.time())

    # Create initial embed and view
    initial_embed = create_summary_embed(user_id, guild_id, matches_by_day[current_date.date()], current_date, bot.db)
    view = SummaryView(user_id, guild_id, matches_by_day, bot.db, current_date)

    await interaction.response.send_message(embed=initial_embed, view=view)

# Update update_match command
async def validate_update_match_request(interaction: discord.Interaction, match_id: int) -> tuple[dict, dict]:
    """Validate update request and get match details"""
    if interaction.user.id != USER_ID:
        await interaction.response.send_message("❌ This command is only available to the bot owner!", ephemeral=True)
        return None, None

    # Get current match details
    old_details = bot.db.get_match_details(match_id)
    if not old_details:
        await interaction.response.send_message("❌ Match not found!", ephemeral=True)
        return None, None

    # Ensure old_details['match_date'] is a datetime object
    old_details['match_date'] = ensure_datetime(old_details['match_date'])
    return old_details, old_details.copy()

def update_match_teams(new_details: dict, team_a: str, team_b: str) -> None:
    """Update team names if provided"""
    if team_a.lower() != 'keep':
        new_details['team_a'] = team_a
    if team_b.lower() != 'keep':
        new_details['team_b'] = team_b

def update_match_datetime(new_details: dict, old_details: dict, match_date: str, match_time: str) -> bool:
    """Update match date/time if provided"""
    try:
        if match_date.lower() != 'keep' and match_time.lower() != 'keep':
            new_details['match_date'] = parse_datetime(match_date, match_time)
        elif match_date.lower() != 'keep':
            old_time = old_details['match_date'].time()
            new_date = datetime.strptime(match_date, "%Y-%m-%d").date()
            new_details['match_date'] = datetime.combine(new_date, old_time)
        elif match_time.lower() != 'keep':
            new_time = datetime.strptime(match_time, "%I:%M %p").time()
            new_details['match_date'] = datetime.combine(old_details['match_date'].date(), new_time)
        return True
    except ValueError:
        return False

async def handle_update_result(interaction: discord.Interaction, success: bool, match_id: int,
                             old_details: dict, new_details: dict) -> None:
    """Handle the result of the update operation"""
    if success:
        bot_logger.info("Match %d updated by %s (ID: %s)",
                       match_id, interaction.user.name, interaction.user.id)

        # Send update announcement
        await bot.announcer.announce_match_update(
            match_id,
            old_details,
            new_details,
            old_details['league_name']
        )

        # Send confirmation to command user
        embed = discord.Embed(
            title="✅ Match Updated",
            description=f"Match #{match_id} has been updated successfully",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Failed to update match", ephemeral=True)

def update_match_active_status(match_id: int):
    """Check team names and if a match is active and update if necessary"""
    match_data = bot.db.get_match_details(match_id)

    match_id = match_data['match_id']
    team_a = match_data['team_a']
    team_b = match_data['team_b']
    is_active = match_data['is_active']

    if is_active == 0 and (team_a != "TBD" or team_b != "TBD"):
        bot.db.open_match(match_id)
    elif is_active == 1 and (team_a == "TBD" or team_b == "TBD"):
        bot.db.close_match(match_id)
    else:
        pass

@bot.tree.command(name="update_match", description="Update match details [Owner Only]")
@app_commands.describe(
    match_id="ID of the match to update",
    team_a="New name for team A (or 'keep' to keep current)",
    team_b="New name for team B (or 'keep' to keep current)",
    match_date="New match date (format: YYYY-MM-DD) (or 'keep' to keep current)",
    match_time="New match time (format: HH:MM AM/PM) (or 'keep' to keep current)",
    match_name="New match type (or 'keep' to keep current)"
)
async def update_match(
    interaction: discord.Interaction,
    match_id: int,
    team_a: str,
    team_b: str,
    match_date: str,
    match_time: str,
    match_name: str
):
    """Update match details and announce changes"""
    bot_logger.info("Update match command initiated by %s (ID: %s) for match %d",
                   interaction.user.name, interaction.user.id, match_id)

    try:
        # Validate request and get match details
        old_details, new_details = await validate_update_match_request(interaction, match_id)
        if not old_details:
            return

        # Update team names
        update_match_teams(new_details, team_a, team_b)

        # Update date/time
        if not update_match_datetime(new_details, old_details, match_date, match_time):
            await interaction.response.send_message(
                "❌ Invalid date/time format",
                ephemeral=True
            )
            return

        # Update match name
        if match_name.lower() != 'keep':
            new_details['match_name'] = match_name

        # Update the match in database
        success = bot.db.update_match(
            match_id,
            new_details['team_a'],
            new_details['team_b'],
            new_details['match_date'],
            new_details['match_name']
        )

        update_match_active_status(match_id)

        await handle_update_result(interaction, success, match_id, old_details, new_details)

    except sqlite3.Error as db_sqlite_error:
        await interaction.response.send_message(
            f"❌ Database error: {str(db_sqlite_error)}",
            ephemeral=True
        )
    except discord.errors.Forbidden as discord_permission_error:
        await interaction.response.send_message(
            f"❌ Permission error: {str(discord_permission_error)}",
            ephemeral=True
        )
    except discord.errors.HTTPException as cmd_http_error:
        await interaction.response.send_message(
            f"❌ HTTP error: {str(cmd_http_error)}",
            ephemeral=True
        )
    except Exception as unexpected_cmd_error:
        await interaction.response.send_message(
            f"❌ An error occurred: {str(unexpected_cmd_error)}",
            ephemeral=True
        )
        bot_logger.error("Error updating match: %s", unexpected_cmd_error)

# Add this new class after other View classes
class AdminSummaryView(ui.View):
    def __init__(self, matches_by_day: dict, current_date: datetime):
        super().__init__(timeout=300)  # 5 minute timeout
        self.matches = matches_by_day
        self.current_date = current_date
        self.dates = sorted(matches_by_day.keys())
        self.current_index = self.dates.index(current_date.date())

        # Disable buttons if at start/end of date range
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

    @ui.button(label="◀️ Previous Day", style=ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    @ui.button(label="Next Day ▶️", style=ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_index < len(self.dates) - 1:
            self.current_index += 1
            self.current_date = datetime.combine(self.dates[self.current_index], datetime.min.time())
            await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = create_admin_summary_embed(self.matches[self.dates[self.current_index]], self.current_date)

        # Update button states
        self.previous_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index == len(self.dates) - 1

        await interaction.response.edit_message(embed=embed, view=self)

# Add this new helper function near other embed creation functions
def create_admin_summary_embed(matches: list, date: datetime) -> discord.Embed:
    embed = discord.Embed(
        title=f"🔧 Admin Summary for {date.strftime('%B %d, %Y')}",
        color=discord.Color.dark_blue()
    )

    if not matches:
        embed.description = "No matches scheduled for this day."
        return embed

    for match in matches:
        match_id, team_a, team_b, winner, match_date, _, league_name, _, match_name = match
        match_time = datetime.strptime(str(match_date), '%Y-%m-%d %H:%M:%S')

        status = "🟢 Open" if not winner else "🔴 Closed"
        if match_time <= datetime.now():
            status = "🟡 In Progress" if not winner else "🔴 Completed"

        field_value = (
            f"🏆 {team_a} vs {team_b}\n"
            f"⏰ {get_discord_timestamp(match_time, 'T')}\n"
            f"📍 {league_name}\n"
            f"📊 {match_name}\n"
            f"{'✅ Winner: ' + winner if winner else '❌ No Winner Set'}"
        )

        embed.add_field(
            name=f"`{match_id}` • {status}",
            value=field_value,
            inline=False
        )

    # Add command help footer
    embed.set_footer(text="/update_match <id> - Edit match details\n/set_winner <id> - Set match winner")

    return embed

# Replace the existing admin_summary command with this updated version
@bot.tree.command(name="admin_summary", description="View administrative summary [Owner Only]")
async def admin_summary(interaction: discord.Interaction):
    bot_logger.info("Admin summary command used by %s (ID: %s)", interaction.user.name, interaction.user.id)
    # Display administrative summary of matches with day-by-day navigation
    if interaction.user.id != USER_ID:
        await interaction.response.send_message("❌ This command is only available to the bot owner!", ephemeral=True)
        return

    try:
        # Get all matches
        all_matches = bot.db.get_all_matches()

        # Group matches by day (include all matches, not just future ones)
        matches_by_day = {}
        for match in all_matches:
            match_date = datetime.strptime(str(match[4]), '%Y-%m-%d %H:%M:%S').date()
            if match_date not in matches_by_day:
                matches_by_day[match_date] = []
            matches_by_day[match_date].append(match)

        if not matches_by_day:
            embed = discord.Embed(
                title="🔧 Administrative Summary",
                description="No matches found.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Start with current day or nearest day (past or future)
        current_date = datetime.now()
        dates = sorted(matches_by_day.keys())
        nearest_date = min(dates, key=lambda x: abs((x - current_date.date()).days))
        current_date = datetime.combine(nearest_date, datetime.min.time())

        # Create initial embed and view
        view = AdminSummaryView(matches_by_day, current_date)
        initial_embed = create_admin_summary_embed(matches_by_day[current_date.date()], current_date)

        await interaction.response.send_message(embed=initial_embed, view=view, ephemeral=True)

    except Exception as e:  # skipcq: PYL-W0621
        await interaction.response.send_message(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )
        logging.error("Error in admin summary: %s", e)

class AnnouncementConfirmView(ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)
        self.value = None

    @ui.button(label="Send", style=ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @ui.button(label="Cancel", style=ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()

@bot.tree.command(
    name="announce",
    description="Send an announcement to all servers [Owner Only]"
)
@app_commands.describe(
    title="The title of the announcement",
    message="The announcement message",
    color="Color of the embed (red, green, blue, gold, orange, purple)",
)
async def announce(
    interaction: discord.Interaction,
    title: str,
    message: str,
    color: str = "blue"
):
    bot_logger.info("Announce command initiated by %s (ID: %s)", interaction.user.name, interaction.user.id)
    # Send an announcement to all servers
    if interaction.user.id != USER_ID:
        await interaction.response.send_message(
            "❌ This command is only available to the bot owner!",
            ephemeral=True
        )
        return

    # Color mapping
    colors = {
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "blue": discord.Color.blue(),
        "gold": discord.Color.gold(),
        "orange": discord.Color.orange(),
        "purple": discord.Color.purple()
    }

    embed_color = colors.get(color.lower(), discord.Color.blue())

    # Show preview to the owner
    preview = discord.Embed(
        title="📢 Announcement Preview",
        color=discord.Color.yellow()
    )
    preview.add_field(
        name="Title",
        value=title,
        inline=False
    )
    preview.add_field(
        name="Message",
        value=message,
        inline=False
    )
    preview.set_footer(text="Click ✅ to send or ❌ to cancel")

    view = AnnouncementConfirmView()
    await interaction.response.send_message(
        "Please confirm the announcement:",
        embed=preview,
        view=view,
        ephemeral=True
    )

    # Wait for the user's response
    await view.wait()

    if view.value is None:
        # Timeout
        timeout = discord.Embed(
            title="⏰ Announcement Cancelled",
            description="Confirmation timed out",
            color=discord.Color.red()
        )
        await interaction.edit_original_response(content="", embed=timeout, view=None)
    elif view.value:
        # Confirmed - send the announcement
        try:
            success, fails = await bot.announcer.send_custom_announcement(title, message, embed_color)

            result = discord.Embed(
                title="✅ Announcement Sent",
                description=f"Sent to {success} servers\nFailed in {fails} servers",
                color=discord.Color.green()
            )
            await interaction.edit_original_response(content="", embed=result, view=None)
        except discord.errors.Forbidden as permission_error:
            bot_logger.error("Insufficient permissions to send announcement: %s", permission_error)
            await interaction.edit_original_response(content="", embed=discord.Embed(
                title="❌ Announcement Failed",
                description=f"Insufficient permissions: {permission_error}",
                color=discord.Color.red()
            ), view=None)
        except discord.errors.HTTPException as discord_http_error:
            bot_logger.error("HTTP error sending announcement: %s", discord_http_error)
            await interaction.edit_original_response(content="", embed=discord.Embed(
                title="❌ Announcement Failed",
                description=f"HTTP error: {discord_http_error}",
                color=discord.Color.red()
            ), view=None)
    else:
        # Cancelled
        cancel = discord.Embed(
            title="❌ Announcement Cancelled",
            color=discord.Color.red()
        )
        await interaction.edit_original_response(content="", embed=cancel, view=None)

async def prompt_online_announcement():
    """Prompt user for online announcement"""
    print("\nSend online announcement?")
    print("y = Yes")
    print("n = No")
    while True:
        response = input("Choice (y/n): ").lower()
        if response in ['y', 'n']:
            return response == 'y'

@bot.event
async def on_ready():
    bot_logger.info("=== Bot Ready ===")
    bot_logger.info("Bot connected as %s", bot.user.name)
    bot_logger.info("Application ID: %s", bot.application_id)
    bot_logger.info("Bot owner ID set to: %s", USER_ID)
    bot_logger.debug("Announcer exists: %s", bot.announcer is not None)
    bot_logger.debug("DB has announcer: %s", bot.db.announcer is not None)

    guild_info = [f"- {guild.name} (id: {guild.id})" for guild in bot.guilds]
    bot_logger.info("Connected to %d guilds:\n%s", len(bot.guilds), '\n'.join(guild_info))

    for guild in bot.guilds:
        channel = await bot.announcer.get_announcement_channel(guild)
        bot_logger.debug("Guild %s has announcement channel: %s", guild.name, channel is not None)

    try:
        bot_logger.info("Syncing commands globally...")
        synced = await bot.tree.sync()
        bot_logger.info("Synced %d commands", len(synced))
    except discord.errors.HTTPException as startup_http_error:
        bot_logger.error("HTTP error syncing commands: %s", startup_http_error)
    except discord.errors.ClientException as startup_client_error:
        bot_logger.error("Client error during startup: %s", startup_client_error)

    try:
        # Start the status update task
        if bot.status_task is None:
            bot.status_task = bot.loop.create_task(bot.update_status())
            bot_logger.info("Status update task started")

        # Prompt for online announcement
        should_announce = await prompt_online_announcement()
        if should_announce:
            bot_logger.info("Sending online announcement...")
            await bot.announcer.announce_bot_status("online")
            bot_logger.info("Online announcement sent successfully")
        else:
            bot_logger.info("Online announcement skipped")
    except discord.errors.HTTPException as startup_http_error:
        bot_logger.error("HTTP error during startup: %s", startup_http_error)
    except discord.errors.ClientException as startup_client_error:
        bot_logger.error("Client error during startup: %s", startup_client_error)
    except asyncio.CancelledError as startup_cancel_error:
        bot_logger.info("Startup task cancelled: %s", startup_cancel_error)
    except ConnectionError as startup_conn_error:
        bot_logger.error("Connection error during startup: %s", startup_conn_error)

    bot_logger.info("=== Bot Ready Complete ===")

@bot.event
async def on_error(event, *args, **kwargs):
    bot_logger.error("An error occurred in %s", event, exc_info=True)

# Add specific error handler for voice-related errors
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandInvokeError):
        if 'audioop' in str(error):
            await ctx.send("Voice functionality is currently unavailable. Please ensure voice dependencies are properly installed.")
        else:
            await ctx.send(f"An error occurred: {str(error)}")
    logging.error("Command error: %s", error, exc_info=True)

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Handle new guild joins"""
    bot_logger.info("Joined new guild: %s (ID: %s)", guild.name, guild.id)

    try:
        # Sync commands for the new guild
        bot_logger.info("Starting bot...")
        await bot.tree.sync()
        bot_logger.info("Commands synced for guild: %s", guild.name)

        # Set up announcement channel
        channel = await bot.announcer.get_announcement_channel(guild)
        if channel:
            welcome_embed = discord.Embed(
                title="🎮 Pick'em Bot Setup Complete",
                description=(
                    "Thanks for adding Pick'em Bot! Create friendly competition by predicting "
                    "professional League of Legends match winners.\n\n"
                    "Use `/help` to see available commands and get started!"
                ),
                color=discord.Color.green()
            )
            await channel.send(embed=welcome_embed)
    except discord.errors.Forbidden as guild_permission_error:
        bot_logger.error("Permission error setting up guild %s: %s", guild.name, guild_permission_error)
    except discord.errors.HTTPException as guild_http_error:
        bot_logger.error("HTTP error setting up guild %s: %s", guild.name, guild_http_error)
    except sqlite3.Error as guild_db_error:
        bot_logger.error("Database error setting up guild %s: %s", guild.name, guild_db_error)
    except Exception as guild_error:
        bot_logger.error("Error setting up new guild %s: %s", guild.name, guild_error)

# Add the help command after your other commands
@bot.tree.command(name="help", description="Show available commands and bot information")
async def help_command(interaction: discord.Interaction):
    """Display help information about the bot and its commands"""
    bot_logger.info("Help command used by %s (ID: %s)", interaction.user.name, interaction.user.id)

    embed = discord.Embed(
        title="📖 Pick'em Bot Help",
        description=(
            "Welcome to Pick'em Bot! Create friendly competition by predicting "
            "the winners of professional League of Legends matches. Make your picks, "
            "track your stats, and compete with others on the leaderboard!\n\n"
            "**How it works:**\n"
            "• Use `/pick` to predict match winners\n"
            "• Get points for correct predictions\n"
            "• Compare your performance on the leaderboard\n"
        ),
        color=discord.Color.blue()
    )

    # Public Commands Section
    embed.add_field(
        name="📝 Making Predictions",
        value=(
            "`/pick` - Make predictions for upcoming matches\n"
            "`/activepicks` - View your current predictions\n"
            "`/matches` - See all scheduled matches"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 Statistics",
        value=(
            "`/stats` - View your prediction statistics\n"
            "`/summary` - See a daily summary of matches and your picks\n"
            "`/leaderboard` - Compare performance with other members"
        ),
        inline=False
    )

    embed.set_footer(
        text="Need more help? Contact your server admin or the bot owner weatherboysuper."
    )

    await interaction.response.send_message(embed=embed)

if __name__ == '__main__':
    try:
        bot_logger.info("Starting bot...")
        bot.run(TOKEN)
    except discord.errors.LoginFailure as bot_login_error:
        bot_logger.critical("Login failed: %s", bot_login_error)
    except discord.errors.ConnectionClosed as bot_conn_error:
        bot_logger.critical("Connection closed: %s", bot_conn_error)
    except ConnectionError as bot_net_error:
        bot_logger.critical("Network error: %s", bot_net_error)
    except discord.DiscordException as bot_error:
        bot_logger.critical("Unexpected error: %s", bot_error, exc_info=True)

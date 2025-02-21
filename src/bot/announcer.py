import discord
import logging
from datetime import datetime
import sqlite3
from src.bot.utils.datetime_utils import get_discord_timestamp

logger = logging.getLogger('bot.announcer')

class AnnouncementManager:
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot')
        logger.info("Announcer initialized")

    async def get_announcement_channel(self, guild):
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
        try:
            total_picks = 0
            correct_picks = 0
            
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

            accuracy = (correct_picks / total_picks * 100) if total_picks > 0 else 0

            embed = discord.Embed(
                title="🏆 Match Result!",
                description="The winner has been decided!",
                color=discord.Color.gold()
            )

            embed.add_field(
                name="Match Details",
                value=(
                    f"🏆 **{team_a}** vs **{team_b}**\n"
                    f"Winner: **||{winner}||**\n\n"
                    f"📊 **Pick Statistics**\n"
                    f"Total Picks: {total_picks}\n"
                    f"Correct Picks: {correct_picks}\n"
                    f"Accuracy: {accuracy:.1f}%"
                ),
                inline=False
            )
            embed.set_footer(text=f"Match ID: {match_id} 🎮 {league_name}")

            await self._send_to_all_guilds(embed)

        except Exception as e:
            self.logger.error("Error announcing match result: %s", e)

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
        else:
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

        await self._send_to_all_guilds(embed)

    async def announce_match_update(self, match_id: int, old_details: dict, new_details: dict, league_name: str):
        """Send announcement for match updates"""
        try:
            embed = discord.Embed(
                title="📝 Match Details Updated",
                color=discord.Color.blue()
            )

            changes = []
            if old_details['team_a'] != new_details['team_a'] or old_details['team_b'] != new_details['team_b']:
                changes.append(
                    f"Teams: {old_details['team_a']} vs {old_details['team_b']} ➔ "
                    f"{new_details['team_a']} vs {new_details['team_b']}"
                )
            if old_details['match_date'] != new_details['match_date']:
                changes.append(
                    f"Date: {get_discord_timestamp(old_details['match_date'], 'F')} ➔ "
                    f"{get_discord_timestamp(new_details['match_date'], 'F')}"
                )
            if old_details['match_name'] != new_details['match_name']:
                changes.append(f"Type: {old_details['match_name']} ➔ {new_details['match_name']}")

            embed.description = (
                f"**{league_name}** - Match #{match_id}\n\n"
                "**Changes:**\n" + "\n".join(f"• {change}" for change in changes)
            )

            await self._send_to_all_guilds(embed)

        except Exception as e:
            self.logger.error("Error announcing match update: %s", e)

    async def announce_new_match(self, match_id: int, team_a: str, team_b: str, match_date: datetime, 
                               league_name: str, match_name: str) -> bool:
        """Send new match announcement to all guilds"""
        logger.info(f"Announcing new match: {team_a} vs {team_b} ({match_id})")
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

            successful_announcements = 0
            for guild in self.bot.guilds:
                try:
                    if channel := await self.get_announcement_channel(guild):
                        await channel.send(embed=embed)
                        successful_announcements += 1
                except Exception as e:
                    logger.error(f"Failed to announce in guild {guild.id}: {e}")

            logger.info(f"Match announced in {successful_announcements} guilds")
            return successful_announcements > 0

        except Exception as e:
            logger.error(f"Error announcing match: {e}", exc_info=True)
            return False

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

        return success_count, fail_count

    async def _send_to_all_guilds(self, embed: discord.Embed) -> bool:
        """Helper method to send an embed to all guilds"""
        success = False
        for guild in self.bot.guilds:
            if channel := await self.get_announcement_channel(guild):
                try:
                    await channel.send(embed=embed)
                    success = True
                except discord.Forbidden:
                    continue
        return success

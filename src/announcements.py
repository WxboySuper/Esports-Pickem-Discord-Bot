import logging
import discord

logger = logging.getLogger(__name__)

ANNOUNCEMENT_CHANNEL_NAME = "pickem-announcements"
ADMIN_CHANNEL_NAME = "admin-updates"


async def get_announcement_channel(
    guild: discord.Guild,
) -> discord.TextChannel:
    for channel in guild.text_channels:
        if channel.name == ANNOUNCEMENT_CHANNEL_NAME:
            return channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False),
        guild.me: discord.PermissionOverwrite(send_messages=True),
    }
    return await guild.create_text_channel(
        ANNOUNCEMENT_CHANNEL_NAME, overwrites=overwrites
    )


async def send_announcement(guild: discord.Guild, embed: discord.Embed):
    channel = await get_announcement_channel(guild)
    await channel.send(embed=embed)


async def get_admin_channel(guild: discord.Guild) -> discord.TextChannel:
    for channel in guild.text_channels:
        if channel.name == ADMIN_CHANNEL_NAME:
            return channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False),
        guild.me: discord.PermissionOverwrite(send_messages=True),
    }
    return await guild.create_text_channel(ADMIN_CHANNEL_NAME, overwrites=overwrites)


async def send_admin_update(message: str, mention_user_id: int | None = None):
    """Sends a plain-text admin update to the developer guild's admin-updates channel.

    If `mention_user_id` is provided it will be mentioned at the start of the message.
    """
    import os
    from src.bot_instance import get_bot_instance

    bot = get_bot_instance()
    if not bot:
        logger.debug("Bot instance not available; cannot send admin update.")
        return

    dev_guild_id = os.getenv("DEVELOPER_GUILD_ID")
    if not dev_guild_id:
        logger.debug("DEVELOPER_GUILD_ID not set; skipping admin update.")
        return

    try:
        guild = bot.get_guild(int(dev_guild_id))
    except Exception:
        guild = None

    if not guild:
        logger.warning("Developer guild id %s not found or bot not in guild.", dev_guild_id)
        return

    try:
        channel = await get_admin_channel(guild)
        body = message
        if mention_user_id:
            body = f"<@{mention_user_id}> {message}"
        await channel.send(body)
        logger.info("Sent admin update to guild %s channel %s", guild.id, channel.name)
    except Exception as e:
        logger.exception("Failed sending admin update: %s", e)

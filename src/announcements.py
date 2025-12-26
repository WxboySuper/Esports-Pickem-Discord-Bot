import logging
import os
from typing import Optional

import discord

from src.bot_instance import get_bot_instance

logger = logging.getLogger(__name__)

ANNOUNCEMENT_CHANNEL_NAME = "pickem-announcements"
ADMIN_CHANNEL_NAME = "admin-updates"


def _find_existing_channel(
    guild: discord.Guild,
) -> Optional[discord.TextChannel]:
    """
    Finds a text channel in the guild with the announcement channel name
    (case-insensitive).

    Ignores channels whose name cannot be accessed during the search.

    Returns:
        The matching discord.TextChannel if found, `None` otherwise.
    """
    name_lower = ANNOUNCEMENT_CHANNEL_NAME.lower()
    for channel in guild.text_channels:
        # channel.name access can raise in rare cases; ignore such channels
        try:
            if channel.name.lower() == name_lower:
                return channel
        except Exception:
            continue
    return None


def _get_bot_member(guild: discord.Guild) -> Optional[discord.Member]:
    """
    Resolve the bot's Member object for the given guild.

    Returns:
        discord.Member: The bot's member in the guild, or `None` if
            the bot's member or user information is unavailable.
    """
    bot = get_bot_instance()
    bot_member = getattr(guild, "me", None)
    if bot_member:
        return bot_member
    if not bot or not getattr(bot, "user", None):
        return None
    try:
        return guild.get_member(bot.user.id)
    except Exception:
        return None


def _can_send(
    channel: discord.TextChannel,
    bot_member: Optional[discord.Member],
) -> bool:
    """
    Determine whether the bot can send messages in the given text
    channel.

    If `bot_member` is provided, evaluate the channel permissions for
    that member. If `bot_member` is `None`, the function treats the
    channel as usable.

    Parameters:
        bot_member (discord.Member | None): The guild-specific Member
            object for the bot; may be `None` if unavailable.

    Returns:
        True if the bot can send messages in the channel, False
            otherwise.
    """
    try:
        if bot_member is None:
            # If we don't know the bot member, assume channel is usable
            return True
        perms = channel.permissions_for(bot_member)
        return perms.send_messages
    except Exception:
        return False


async def _try_create_announcement_channel(
    guild: discord.Guild,
    bot_member: Optional[discord.Member],
) -> Optional[discord.TextChannel]:
    """
    Attempt to create the dedicated announcement text channel with
    restricted send permissions.

    If creation succeeds, returns the newly created TextChannel. The
    channel is created so that the default role is denied the ability
    to send messages; if `bot_member` is provided it is granted send
    permission.

    Parameters:
        guild (discord.Guild): The guild in which to create the
            channel.
        bot_member (Optional[discord.Member]): The bot's Member object
            in the guild, or None if unavailable.

    Returns:
        discord.TextChannel or None: The created announcement channel
            on success, or `None` if creation failed or was not
            permitted.
    """
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False)
    }
    if bot_member:
        overwrites[bot_member] = discord.PermissionOverwrite(
            send_messages=True
        )

    try:
        return await guild.create_text_channel(
            ANNOUNCEMENT_CHANNEL_NAME, overwrites=overwrites
        )
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.warning(
            "Could not create announcement channel in guild %s: %s. "
            "Falling back to existing channels.",
            getattr(guild, "id", "unknown"),
            e,
        )
        return None
    except Exception:
        # Be conservative: don't raise for unexpected runtime issues here
        return None


async def get_announcement_channel(
    guild: discord.Guild,
) -> Optional[discord.TextChannel]:
    """
    Resolve a suitable text channel in a guild for posting
    announcements.

    The selection prefers an existing channel named
    "pickem-announcements" (case-insensitive), attempts to create that
    dedicated channel, falls back to the first channel the bot can
    send messages in, and finally returns the guild's first text
    channel if available.

    Parameters:
        guild (discord.Guild): Guild to search or create the
            announcement channel in.

    Returns:
        discord.TextChannel or None: The chosen text channel for
            announcements, or `None` if the guild has no text
            channels.
    """
    existing = _find_existing_channel(guild)
    if existing:
        return existing

    bot_member = _get_bot_member(guild)

    # Try creating the dedicated announcement channel with restrictive
    # overwrites
    created = await _try_create_announcement_channel(guild, bot_member)
    if created:
        return created

    # Fallback: return first channel where the bot can send messages
    for channel in guild.text_channels:
        if _can_send(channel, bot_member):
            return channel

    # If we know the bot member and no usable channel was found, return None
    if bot_member is not None:
        return None

    # As a last resort, return the first text channel or None
    return guild.text_channels[0] if guild.text_channels else None


async def send_announcement(
    guild: discord.Guild, embed: discord.Embed
) -> bool:
    """
    Send an embed announcement to an appropriate channel in the guild.

    Returns:
        bool: True if the embed was sent successfully, False otherwise.
    """
    channel = await get_announcement_channel(guild)
    if channel is None:
        logger.error(
            "No available announcement channel in guild %s",
            getattr(guild, "id", "unknown"),
        )
        return False

    try:
        await channel.send(embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.error(
            "Failed to send announcement in guild %s, channel %s: %s",
            getattr(guild, "id", "unknown"),
            getattr(channel, "id", "unknown"),
            e,
        )
        return False


async def get_admin_channel(
    guild: discord.Guild,
) -> Optional[discord.TextChannel]:
    """
    Locate or create the administrator updates channel in the given guild.

    Requires the 'Manage Channels' permission if the channel does not
    already exist.

    Returns:
        discord.TextChannel: The existing or newly created admin channel,
            or `None` if creation failed or was not permitted.
    """
    for channel in guild.text_channels:
        if channel.name == ADMIN_CHANNEL_NAME:
            return channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False),
        guild.me: discord.PermissionOverwrite(send_messages=True),
    }
    try:
        return await guild.create_text_channel(
            ADMIN_CHANNEL_NAME, overwrites=overwrites
        )
    except (discord.Forbidden, discord.HTTPException) as e:
        logger.warning(
            "Could not create admin channel in guild %s: %s",
            getattr(guild, "id", "unknown"),
            e,
        )
        return None
    except Exception:
        return None


async def send_admin_update(message: str, mention_user_id: int | None = None):
    """
    Send a plain-text admin update to the developer guild's
    "admin-updates" channel.

    Parameters:
        message (str): The message text to send.
        mention_user_id (int | None): Optional user ID to mention at the
            start of the message.

    Behavior:
        - Looks up the developer guild using the `DEVELOPER_GUILD_ID`
          environment variable and requires the bot instance to be
          available. If the env var is missing, the bot instance is not
          available, or the guild cannot be found, the function returns
          early without sending.
        - Attempts to locate or create the admin-updates channel and will
          log and return early on failures.
    """
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
        logger.warning(
            "Developer guild id %s not found or bot not in guild.",
            dev_guild_id,
        )
        return

    try:
        channel = await get_admin_channel(guild)
        if channel is None:
            logger.warning("No admin channel available in guild %s", guild.id)
            return

        body = message
        if mention_user_id:
            body = f"<@{mention_user_id}> {message}"
        await channel.send(body)
        logger.info(
            "Sent admin update to guild %s channel %s", guild.id, channel.name
        )
    except Exception as e:
        logger.exception("Failed sending admin update: %s", e)

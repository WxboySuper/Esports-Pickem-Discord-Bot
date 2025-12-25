import logging
from typing import Optional

import discord

from src.bot_instance import get_bot_instance

logger = logging.getLogger(__name__)

ANNOUNCEMENT_CHANNEL_NAME = "pickem-announcements"


def _find_existing_channel(
    guild: discord.Guild,
) -> Optional[discord.TextChannel]:
    """
    Locate a text channel in the guild whose name matches the
    announcement channel name (case-insensitive).

    Channels where the channel name cannot be accessed are ignored
    during the search.

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
        guild.default_role: discord.PermissionOverwrite(
            send_messages=False
        )
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

    # As a last resort, return the first text channel or None
    return guild.text_channels[0] if guild.text_channels else None


async def send_announcement(guild: discord.Guild, embed: discord.Embed):
    """
    Send an embed announcement to an appropriate channel in the given
    guild.

    Resolves a target channel using the module's channel-resolution
    logic and sends the provided embed. If no suitable channel is
    available, an error is logged and no message is sent.

    Parameters:
        guild (discord.Guild): Guild to send the announcement in.
        embed (discord.Embed): Embed to send as the announcement.
    """
    channel = await get_announcement_channel(guild)
    if channel is None:
        logger.error(
            "No available announcement channel in guild %s",
            getattr(guild, "id", "unknown")
        )
        return
    await channel.send(embed=embed)

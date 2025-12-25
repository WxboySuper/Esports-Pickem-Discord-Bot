import logging
from typing import Optional

import discord

from src.bot_instance import get_bot_instance

logger = logging.getLogger(__name__)

ANNOUNCEMENT_CHANNEL_NAME = "pickem-announcements"


def _find_existing_channel(
    guild: discord.Guild,
) -> Optional[discord.TextChannel]:
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
    # Prefer exact-match channel if it already exists (case-insensitive)
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
    channel = await get_announcement_channel(guild)
    if channel is None:
        logger.error(
            "No available announcement channel in guild %s",
            getattr(guild, "id", "unknown")
            )
        return
    await channel.send(embed=embed)

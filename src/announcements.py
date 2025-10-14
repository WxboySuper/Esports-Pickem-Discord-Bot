import logging
import discord

logger = logging.getLogger(__name__)

ANNOUNCEMENT_CHANNEL_NAME = "pickem-announcements"


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

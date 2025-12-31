# src/commands/info.py
# Info/help command as a slash command

import logging
import discord

logger = logging.getLogger("esports-bot.commands.info")


async def setup(bot):
    @bot.tree.command(
        name="info", description="Bot and repository information"
    )
    async def info(interaction: discord.Interaction):
        logger.debug("Info command invoked by user %s", interaction.user.id)
        embed = discord.Embed(
            title="Esports Pick'em Bot",
            description="Useful commands and links.",
            color=0x2D9CDB,
        )

        # Organize commands: list top-level commands and group subcommands
        lines = []
        for c in bot.tree.get_commands():
            children = getattr(c, "commands", None)
            if children:
                lines.append(
                    f"**/{c.name}** — {c.description or 'No description'}"
                )
                for sub in children:
                    sub_desc = sub.description or "No description"
                    lines.append(f"• /{c.name} {sub.name} — {sub_desc}")
            else:
                lines.append(
                    f"**/{c.name}** — {c.description or 'No description'}"
                )

        if not lines:
            lines = ["No commands available."]

        # Discord embed field value limit is 1024 characters. Split
        # the commands list into multiple fields if necessary to avoid
        # runtime errors when sending large command lists.
        def _chunk_lines(lines_list, limit=1024):
            chunks = []
            current = []
            current_len = 0
            for ln in lines_list:
                ln_len = len(ln) + 1  # account for the newline when joined
                if current and (current_len + ln_len) > limit:
                    chunks.append("\n".join(current))
                    current = [ln]
                    current_len = ln_len
                else:
                    current.append(ln)
                    current_len += ln_len

            if current:
                chunks.append("\n".join(current))
            return chunks

        chunks = _chunk_lines(lines, limit=1024)
        if len(chunks) == 1:
            embed.add_field(name="Commands", value=chunks[0], inline=False)
        else:
            for i, chunk in enumerate(chunks, start=1):
                name_text = f"Commands ({i}/{len(chunks)})"
                embed.add_field(name=name_text, value=chunk, inline=False)
        embed.add_field(
            name="Repository",
            value="https://github.com/WxboySuper/Esports-Pickem-Discord-Bot",
            inline=False,
        )
        embed.set_footer(
            text="Configured to use slash commands (app_commands)."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# src/commands/info.py
# Info/help command as a slash command

import logging
import discord

logger = logging.getLogger("esports-bot.commands.info")


def _format_command(cmd):
    """Return a one-line description for a command (shows subcommand count)."""
    children = getattr(cmd, "commands", None)
    if children:
        return (
            f"**/{cmd.name}** — {cmd.description or 'No description'} "
            f"({len(children)} subcommands)"
        )
    return f"**/{cmd.name}** — {cmd.description or 'No description'}"


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

        # Simplified command listing: show top-level commands and the
        # number of subcommands for command groups. Formatting logic
        # lives in a small helper to avoid deep nesting inside this
        # function.
        lines = [_format_command(c) for c in bot.tree.get_commands()]

        if not lines:
            lines = ["No commands available."]

        # Split into small fields to avoid overly long embed values.
        per_field = 10
        for i in range(0, len(lines), per_field):
            chunk = "\n".join(lines[i: i + per_field])
            idx = (i // per_field) + 1
            total = (len(lines) + per_field - 1) // per_field
            title = "Commands" if total == 1 else f"Commands ({idx}/{total})"
            embed.add_field(name=title, value=chunk, inline=False)
        embed.add_field(
            name="Repository",
            value="https://github.com/WxboySuper/Esports-Pickem-Discord-Bot",
            inline=False,
        )
        embed.set_footer(
            text="Configured to use slash commands (app_commands)."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

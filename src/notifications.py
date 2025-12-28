import logging
import discord
from datetime import datetime, timezone
from sqlmodel import select
from src.db import get_async_session
from src.models import Match, Result, Pick
from src.announcements import send_announcement
from src.bot_instance import get_bot_instance
from src.match_result_utils import fetch_teams

logger = logging.getLogger(__name__)


async def send_result_notification(match_id: int, result_id: int):
    """
    Load fresh `Match` and `Result` objects in a new session and broadcast
    the result notification to all guilds. Accepting IDs ensures the
    notification code always works with session-bound instances and avoids
    detached-instance pitfalls.

    Parameters:
        match_id (int): Database ID of the match.
        result_id (int): Database ID of the result.
    """
    logger.info(
        "Broadcasting result notification for match %s to all guilds.",
        match_id,
    )
    bot = get_bot_instance()

    async with get_async_session() as session:
        match = await session.get(Match, match_id)
        result = await session.get(Result, result_id)

        if not match or not result:
            logger.error(
                "Could not load match/result for notification: %s / %s",
                match_id,
                result_id,
            )
            return

        logger.debug("Fetching teams and picks for match %s", match.id)
        team1, team2 = await fetch_teams(session, match)

        winner_team_obj = team1 if result.winner == match.team1 else team2

        statement = select(Pick).where(Pick.match_id == match.id)
        picks = (await session.exec(statement)).all()
        total_picks = len(picks)
        correct_picks = len(
            [p for p in picks if p.chosen_team == result.winner]
        )
        correct_percentage = (
            (correct_picks / total_picks) * 100 if total_picks > 0 else 0
        )

        opponent = match.team2 if result.winner == match.team1 else match.team1
        title = f"🏆 Match Results: {match.team1} vs {match.team2}"
        description = (
            f"**{result.winner}** emerges victorious over **{opponent}** "
            f"with a final score of **{result.score}**."
        )
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.gold(),
        )

        if winner_team_obj and winner_team_obj.image_url:
            embed.set_thumbnail(url=winner_team_obj.image_url)

        if total_picks > 0:
            picks_value = (
                "**{cp}** of **{tp}** users "
                "({pc:.2f}%) correctly picked the winner."
            ).format(cp=correct_picks, tp=total_picks, pc=correct_percentage)
        else:
            picks_value = "No picks were made for this match."

        embed.add_field(
            name="📊 Pick'em Stats", value=picks_value, inline=False
        )
        embed.set_footer(text=f"Leaguepedia Match ID: {match.leaguepedia_id}")
        embed.timestamp = datetime.now(timezone.utc)

        await _broadcast_embed_to_guilds(
            bot, embed, f"result notification for match {match.id}"
        )


async def send_mid_series_update(match: Match, score: str):
    """
    Builds and broadcasts a Discord embed announcing a live
    mid-series score update to all guilds.

    Parameters:
        match (Match): Match object containing teams, id, and best_of
            used in the embed.
        score (str): Current series score string (for example, "2-1")
            displayed in the embed.
    """
    logger.info(
        "Broadcasting mid-series update for match %s "
        "(score: %s) to all guilds.",
        match.id,
        score,
    )
    bot = get_bot_instance()

    title = f"Live Update: {match.team1} vs {match.team2}"
    description = (
        f"The score is now **{score}** in this best of {match.best_of} series."
    )
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.orange(),
    )
    embed.set_footer(text=f"Match ID: {match.id}")
    embed.timestamp = datetime.now(timezone.utc)

    await _broadcast_embed_to_guilds(
        bot, embed, f"mid-series update for match {match.id} (score: {score})"
    )


async def _broadcast_embed_to_guilds(
    bot: discord.Client, embed: discord.Embed, context: str
):
    """
    Broadcast an embed to every guild the bot is a member of and
    record success or failure for each delivery.

    Parameters:
        context (str): Short description included in log messages to
            identify this broadcast.
    """
    for guild in bot.guilds:
        try:
            await send_announcement(guild, embed)
            logger.info("Sent %s to guild %s.", context, guild.id)
        except Exception as e:
            logger.error(
                "Failed to send %s to guild %s: %s", context, guild.id, e
            )

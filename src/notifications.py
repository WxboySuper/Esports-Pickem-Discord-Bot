import logging
import discord
from datetime import datetime, timezone
from typing import Any
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
    if not bot:
        logger.error(
            "Bot instance not available for result notification: "
            "match %s, result %s",
            match_id,
            result_id,
        )
        return

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

        stats = await _get_pick_stats(session, match.id, result.winner)

        embed = _build_result_embed(match, result, (team1, team2), stats)

        await broadcast_embed_to_guilds(
            bot, embed, f"result notification for match {match.id}"
        )


async def _get_pick_stats(session, match_id: int, winner: str):
    """
    Calculate pick statistics for a given match.

    Parameters:
        session: Database session.
        match_id (int): ID of the match.
        winner (str): Name of the winning team.

    Returns:
        tuple: (total_picks, correct_picks, correct_percentage)
    """
    statement = select(Pick).where(Pick.match_id == match_id)
    picks = (await session.exec(statement)).all()
    total = len(picks)
    correct = len([p for p in picks if p.chosen_team == winner])
    percentage = (correct / total * 100) if total > 0 else 0
    return total, correct, percentage


def _build_result_embed(
    match: Match,
    result: Result,
    teams: tuple[Any, Any],
    stats: tuple[int, int, float],
) -> discord.Embed:
    """
    Build the result notification embed.
    """
    team1, team2 = teams
    total_picks, correct_picks, correct_percentage = stats

    winner_team_obj = team1 if result.winner == match.team1 else team2
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
            f"**{correct_picks}** of **{total_picks}** users "
            f"({correct_percentage:.2f}%) correctly picked the winner."
        )
    else:
        picks_value = "No picks were made for this match."

    embed.add_field(name="📊 Pick'em Stats", value=picks_value, inline=False)
    embed.set_footer(text=f"Leaguepedia Match ID: {match.leaguepedia_id}")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


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
    if not bot:
        logger.error(
            "Bot instance not available for mid-series update: "
            "match %s, score %s",
            match.id,
            score,
        )
        return

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

    await broadcast_embed_to_guilds(
        bot, embed, f"mid-series update for match {match.id} (score: {score})"
    )


async def broadcast_embed_to_guilds(
    bot: discord.Client, embed: discord.Embed, context: str
):
    """
    Broadcast an embed to every guild the bot is a member of and
    record success or failure for each delivery.

    Parameters:
        bot (discord.Client): The bot instance used to access guilds.
        embed (discord.Embed): The embed to broadcast.
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

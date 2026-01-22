import logging
import asyncio
import discord
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlmodel import select
from src.db import get_async_session
from src.models import Match, Result, Pick, Team
from src.announcements import send_announcement
from src.bot_instance import get_bot_instance
from src.match_result_utils import fetch_teams

logger = logging.getLogger(__name__)


async def send_result_notification(match_id: int, result_id: int):
    """
    Load fresh `Match` and `Result` objects in a new session and broadcast
    the result notification to all guilds.
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
        from src import crud

        match = await crud.get_match_with_result_by_id(session, match_id)
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

        context = f"result notification for match {match.id}"
        await broadcast_embed_to_guilds(bot, embed, context)


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


def _fmt_team_name(name: str, obj: Optional[Team]) -> str:
    if obj and getattr(obj, "acronym", None):
        return f"{name} ({obj.acronym})"
    return name


def _get_contest_name(match: Match) -> str:
    contest = getattr(match, "contest", None)
    return (
        getattr(contest, "name", "Unknown Contest")
        if contest
        else "Unknown Contest"
    )


def _score_value(match: Match, result: Result) -> str:
    score_val = f"**{result.score}**"
    if getattr(match, "best_of", None):
        score_val += f" (Best of {match.best_of})"
    return f"||{score_val}||"


def _stats_value(stats: Tuple[int, int, float]) -> str:
    total_picks, correct_picks, correct_percentage = stats
    if total_picks > 0:
        return (
            f"✅ **{correct_picks}** correct\n"
            f"👥 **{total_picks}** total picks\n"
            f"📈 **{correct_percentage:.1f}%** accuracy"
        )
    return "No picks were made."


def _build_result_embed(
    match: Match,
    result: Result,
    teams: Tuple[Optional[Team], Optional[Team]],
    stats: Tuple[int, int, float],
) -> discord.Embed:
    """
    Build the revamped result notification embed.
    """
    team1_obj, team2_obj = teams
    _, _, _ = stats

    # Determine winner and loser info
    if result.winner == match.team1:
        winner_obj, loser_obj = team1_obj, team2_obj
        winner_name, loser_name = match.team1, match.team2
    else:
        winner_obj, loser_obj = team2_obj, team1_obj
        winner_name, loser_name = match.team2, match.team1

    winner_display = _fmt_team_name(winner_name, winner_obj)
    loser_display = _fmt_team_name(loser_name, loser_obj)

    contest_name = _get_contest_name(match)

    embed = discord.Embed(
        title=f"🏆 {contest_name} - Match Result",
        description=f"||**{winner_display}** has defeated **{loser_display}**!||",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="Final Score", value=_score_value(match, result), inline=True
    )
    embed.add_field(
        name="Pick'em Stats", value=_stats_value(stats), inline=True
    )

    thumbnail_url = None
    if getattr(match, "contest", None) and getattr(
        match.contest, "image_url", None
    ):
        thumbnail_url = match.contest.image_url
    elif winner_obj and getattr(winner_obj, "image_url", None):
        thumbnail_url = winner_obj.image_url

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    footer = f"Match ID: {match.id}"
    if getattr(match, "pandascore_id", None):
        footer += f" | PandaScore: {match.pandascore_id}"
    embed.set_footer(text=footer)

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
        "Broadcasting mid-series update for match %s (score %s).",
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

    context = f"mid-series update for match {match.id} (score: {score})"
    await broadcast_embed_to_guilds(bot, embed, context)


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
    for i, guild in enumerate(bot.guilds):
        try:
            await send_announcement(guild, embed)
            logger.info("Sent %s to guild %s.", context, guild.id)
        except Exception as e:
            msg = "Failed to send %s to guild %s: %s"
            logger.error(msg, context, guild.id, e)

        # Yield to event loop every 3 guilds to avoid heartbeat blocking.
        # Use (i+1) % 3 == 0 to process the first guild before yielding.
        if (i + 1) % 3 == 0:
            await asyncio.sleep(0)

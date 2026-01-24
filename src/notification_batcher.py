import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Any

import discord
from sqlmodel import select
from sqlalchemy.orm import selectinload

from src.db import get_async_session
from src.models import Match, Result, Pick, Team
from src.announcements import broadcast_embed_to_guilds
from src.bot_instance import get_bot_instance
from src.match_result_utils import fetch_teams

logger = logging.getLogger(__name__)


class NotificationBatcher:
    def __init__(self):
        self._pending = defaultdict(list)
        self._timers = {}
        self._lock = asyncio.Lock()

    async def add_reminder(self, match_id: int, minutes: int):
        key = f"reminder_{minutes}"
        async with self._lock:
            self._pending[key].append(match_id)
            self._ensure_timer(key)

    async def add_result(self, match_id: int, result_id: int):
        key = "result"
        async with self._lock:
            self._pending[key].append((match_id, result_id))
            self._ensure_timer(key)

    async def add_time_change(
        self, match_id: int, old_time: Any, new_time: Any
    ):
        key = "time_change"
        async with self._lock:
            self._pending[key].append((match_id, old_time, new_time))
            self._ensure_timer(key)

    async def add_mid_series_update(self, match_id: int, score: str):
        key = "mid_series"
        async with self._lock:
            self._pending[key].append((match_id, score))
            self._ensure_timer(key)

    def _ensure_timer(self, key: str):
        if key not in self._timers:
            # Schedule flush after 1 second (debounce)
            self._timers[key] = asyncio.create_task(self._flush_later(key))

    async def _flush_later(self, key: str):
        await asyncio.sleep(1.0)
        async with self._lock:
            items = self._pending.pop(key, [])
            self._timers.pop(key, None)

        if items:
            try:
                await self._process_batch(key, items)
            except Exception:
                logger.exception("Failed to process batch for key %s", key)

    async def _process_batch(self, key: str, items: List[Any]):
        logger.info("Processing batch %s with %d items", key, len(items))
        if key.startswith("reminder_"):
            minutes = int(key.split("_")[1])
            await self._process_reminders(minutes, items)
        elif key == "result":
            await self._process_results(items)
        elif key == "time_change":
            await self._process_time_changes(items)
        elif key == "mid_series":
            await self._process_mid_series(items)

    async def _get_match_with_contest(
        self, session, match_id: int
    ) -> Optional[Match]:
        """Fetch match with contest eager-loaded."""
        stmt = (
            select(Match)
            .options(selectinload(Match.contest))
            .where(Match.id == match_id)
        )
        return (await session.exec(stmt)).first()

    async def _process_reminders(self, minutes: int, match_ids: List[int]):
        bot = get_bot_instance()
        if not bot:
            return

        async with get_async_session() as session:
            matches_data = []
            for match_id in match_ids:
                match = await self._get_match_with_contest(session, match_id)
                if match:
                    team1, team2 = await fetch_teams(session, match)
                    matches_data.append((match, team1, team2))

            if not matches_data:
                return

            embed = self._build_reminder_embed(minutes, matches_data)
            context = (
                f"{minutes}-minute reminder for {len(matches_data)} matches"
            )
            await broadcast_embed_to_guilds(bot, embed, context)

    async def _process_results(self, items: List[Tuple[int, int]]):
        bot = get_bot_instance()
        if not bot:
            return

        async with get_async_session() as session:
            results_data = []
            from src import crud

            for match_id, result_id in items:
                match = await crud.get_match_with_result_by_id(
                    session, match_id
                )
                result = await session.get(Result, result_id)
                if match and result:
                    team1, team2 = await fetch_teams(session, match)
                    stats = await self._get_pick_stats(
                        session, match.id, result.winner
                    )
                    results_data.append((match, result, team1, team2, stats))

            if not results_data:
                return

            embed = self._build_result_embed(results_data)
            context = f"result notification for {len(results_data)} matches"
            await broadcast_embed_to_guilds(bot, embed, context)

    async def _process_time_changes(self, items: List[Tuple[int, Any, Any]]):
        bot = get_bot_instance()
        if not bot:
            return

        async with get_async_session() as session:
            changes_data = []
            for match_id, old, new in items:
                match = await self._get_match_with_contest(session, match_id)
                if match:
                    changes_data.append((match, old, new))

            if not changes_data:
                return

            embed = self._build_time_change_embed(changes_data)
            context = (
                f"time change notification for {len(changes_data)} matches"
            )
            await broadcast_embed_to_guilds(bot, embed, context)

    async def _process_mid_series(self, items: List[Tuple[int, str]]):
        bot = get_bot_instance()
        if not bot:
            return

        async with get_async_session() as session:
            updates_data = []
            for match_id, score in items:
                match = await self._get_match_with_contest(session, match_id)
                if match:
                    updates_data.append((match, score))

            if not updates_data:
                return

            embed = self._build_mid_series_embed(updates_data)
            context = f"mid-series update for {len(updates_data)} matches"
            await broadcast_embed_to_guilds(bot, embed, context)

    # --- Embed Builders ---

    def _build_reminder_embed(
        self, minutes: int, matches_data: List[Tuple[Match, Any, Any]]
    ) -> discord.Embed:
        # Sort by scheduled time, then ID
        matches_data.sort(key=lambda x: (x[0].scheduled_time, x[0].id))

        if minutes == 5:
            title = "🔴 Matches Starting Soon!"
            color = discord.Color.red()
            desc_prefix = (
                "The following matches are starting soon! "
                "Last chance to lock in picks."
            )
        else:
            title = "⚔️ Upcoming Match Reminders"
            color = discord.Color.blue()
            desc_prefix = (
                "Get your picks in! The following matches are starting soon."
            )

        description_lines = [desc_prefix, ""]

        for match, _, _ in matches_data:
            ts = int(match.scheduled_time.timestamp())
            line = f"**{match.team1}** vs **{match.team2}** <t:{ts}:R>"
            description_lines.append(line)

        embed = discord.Embed(
            title=title,
            description="\n".join(description_lines),
            color=color,
        )

        # Use contest icon from the first match
        if matches_data:
            first_match = matches_data[0][0]
            first_team1 = matches_data[0][1]
            first_team2 = matches_data[0][2]
            self._set_thumbnail(embed, first_match, first_team1, first_team2)

        embed.set_footer(
            text="Use the /picks command to make your predictions!"
        )
        return embed

    def _build_result_embed(
        self, results_data: List[Tuple[Match, Result, Any, Any, Tuple]]
    ) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Match Results",
            description="The following matches have concluded:",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc),
        )

        # Sort by match ID
        results_data.sort(key=lambda x: x[0].id)

        for match, result, team1, team2, stats in results_data:
            _, correct, _ = stats
            # Determine winner display
            if result.winner == match.team1:
                display = f"||**{match.team1}** def **{match.team2}**||"
            else:
                display = f"||**{match.team2}** def **{match.team1}**||"

            score_text = f"||{result.score}||"
            stats_text = f"✅ {correct} correct"

            field_name = f"{match.team1} vs {match.team2}"
            field_value = f"{display} ({score_text})\n{stats_text}"
            embed.add_field(name=field_name, value=field_value, inline=False)

        # Thumbnail from first match
        if results_data:
            first = results_data[0]
            self._set_thumbnail(embed, first[0], first[2], first[3])

        return embed

    def _build_time_change_embed(
        self, changes_data: List[Tuple[Match, Any, Any]]
    ) -> discord.Embed:
        embed = discord.Embed(
            title="📅 Match Schedule Updates",
            description="The following matches have been rescheduled:",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )

        changes_data.sort(key=lambda x: x[0].id)

        for match, _, new_time in changes_data:
            ts = int(new_time.timestamp())
            line = (
                f"**{match.team1}** vs **{match.team2}**\n"
                f"New Time: <t:{ts}:F> (<t:{ts}:R>)"
            )
            embed.add_field(name=f"Match {match.id}", value=line, inline=False)

        if changes_data:
            self._set_thumbnail(embed, changes_data[0][0], None, None)

        return embed

    def _build_mid_series_embed(
        self, updates_data: List[Tuple[Match, str]]
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Live Match Updates",
            description="Latest scores:",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc),
        )

        updates_data.sort(key=lambda x: x[0].id)

        for match, score in updates_data:
            line = (
                f"**{match.team1}** vs **{match.team2}**: "
                f"**{score}** (Best of {match.best_of})"
            )
            embed.add_field(name=f"Match {match.id}", value=line, inline=False)

        if updates_data:
            self._set_thumbnail(embed, updates_data[0][0], None, None)

        return embed

    def _set_thumbnail(
        self,
        embed: discord.Embed,
        match: Match,
        team1: Optional[Team],
        team2: Optional[Team],
    ):
        """
        Sets the thumbnail of the embed using the contest image if available,
        otherwise falls back to team images.
        """
        contest = getattr(match, "contest", None)
        if contest and getattr(contest, "image_url", None):
            embed.set_thumbnail(url=contest.image_url)
            return

        # Fallback to team images if provided
        if team1 and getattr(team1, "image_url", None):
            embed.set_thumbnail(url=team1.image_url)
        elif team2 and getattr(team2, "image_url", None):
            embed.set_thumbnail(url=team2.image_url)

    async def _get_pick_stats(self, session, match_id: int, winner: str):
        # Duplicated from notifications.py to avoid circular import issues
        # or we could move this to a util. For now, duplication is safe.
        statement = select(Pick).where(Pick.match_id == match_id)
        picks = (await session.exec(statement)).all()
        total = len(picks)
        correct = len([p for p in picks if p.chosen_team == winner])
        percentage = (correct / total * 100) if total > 0 else 0
        return total, correct, percentage


# Global instance
batcher = NotificationBatcher()

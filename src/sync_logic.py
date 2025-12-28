import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Any

from src.config import DATA_PATH
from src.leaguepedia_client import leaguepedia_client
from src.db import get_async_session
from src.crud import upsert_contest, upsert_match, upsert_team
from src.scheduler import schedule_reminders, send_result_notification
from src.match_result_utils import (
    filter_relevant_games_from_scoreboard,
    calculate_team_scores,
    determine_winner,
    save_result_and_update_picks,
)
from src import crud

logger = logging.getLogger(__name__)
CONFIG_PATH = DATA_PATH / "tournaments.json"


def _parse_date(date_str: str | None) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


async def _process_teams_for_match(
    match_data: dict, db_session, summary: dict
) -> None:
    """
    Process and upsert teams for a single match.
    """
    for team_key in ["Team1", "Team2"]:
        team_name = match_data.get(team_key)
        if not team_name:
            logger.warning("Missing '%s' in match data.", team_key)
            continue
        await upsert_team(
            db_session,
            {"leaguepedia_id": team_name, "name": team_name},
        )
        summary["teams"] += 1


@dataclass
class SyncContext:
    contest: Any
    db_session: Any
    summary: dict
    scoreboard: Optional[List] = None
    notifications: List = field(default_factory=list)


async def _process_match(
    match_data: dict,
    ctx: SyncContext,
) -> Optional[Tuple[Any, bool]]:
    """
    Process and upsert a single match.
    Returns (match, time_changed) tuple or None if match cannot be processed.
    """
    match_id = match_data.get("MatchId")
    if not match_id:
        logger.warning("Missing MatchId in data: %s", match_data)
        return None

    scheduled_time = _parse_date(match_data.get("DateTime UTC"))
    if not scheduled_time:
        logger.warning("Match %s has no scheduled time. Skipping.", match_id)
        return None
    match, time_changed = await upsert_match(
        ctx.db_session,
        {
            "leaguepedia_id": match_id,
            "contest_id": ctx.contest.id,
            "team1": match_data.get("Team1"),
            "team2": match_data.get("Team2"),
            "best_of": (
                int(match_data["BestOf"]) if match_data.get("BestOf") else None
            ),
            "scheduled_time": scheduled_time,
        },
    )
    ctx.summary["matches"] += 1

    await _detect_and_handle_result(match, ctx, match_id)

    return (match, time_changed)


async def _upsert_contest_data(overview_page, contest_matches, db_session):
    valid_times = [
        t for m in contest_matches
        if (t := _parse_date(m.get("DateTime UTC"))) is not None
    ]

    if not valid_times:
        logger.warning(
            "No valid match times for contest '%s'. Skipping.",
            overview_page,
        )
        return None

    tournament_name = contest_matches[0].get("Name")
    return await upsert_contest(
        db_session,
        {
            "leaguepedia_id": overview_page,
            "name": tournament_name,
            "start_date": min(valid_times),
            "end_date": max(valid_times),
        },
    )


async def _fetch_contest_scoreboard(overview_page):
    try:
        return await leaguepedia_client.get_scoreboard_data(overview_page)
    except Exception:
        logger.exception(
            "Failed to fetch scoreboard for contest %s; continuing without",
            overview_page,
        )
        return None


async def _process_contest(
    overview_page: str, contest_matches: list, db_session, summary: dict
) -> Tuple[List, List]:
    """
    Process a single contest and its matches.
    Returns a tuple `(matches_to_schedule, notifications)` where
    `matches_to_schedule` is a list of matches that need reminders
    scheduled and `notifications` is a list of result notifications to
    send after the outer transaction commits.
    """
    matches_to_schedule = []

    contest = await _upsert_contest_data(
        overview_page, contest_matches, db_session
    )
    if not contest:
        return [], []

    summary["contests"] += 1
    await db_session.flush()

    ctx = SyncContext(
        contest=contest,
        db_session=db_session,
        summary=summary,
        scoreboard=await _fetch_contest_scoreboard(overview_page),
    )

    for match_data in contest_matches:
        await _process_teams_for_match(match_data, db_session, summary)

        if result := await _process_match(match_data, ctx):
            match, time_changed = result
            if time_changed:
                matches_to_schedule.append(match)

    return matches_to_schedule, ctx.notifications


def _calculate_match_outcome(scoreboard, match):
    """
    Analyzes scoreboard to determine if there is a winner.
    Returns (winner, score_str) or (None, None).
    """
    relevant_games = filter_relevant_games_from_scoreboard(scoreboard, match)
    if not relevant_games:
        return None, None

    team1_score, team2_score = calculate_team_scores(relevant_games, match)

    if getattr(match, "best_of", None) is None:
        logger.warning(
            "Skipping result detection for match %s: missing best_of",
            match.id,
        )
        return None, None

    winner = determine_winner(team1_score, team2_score, match)
    if not winner:
        return None, None

    return winner, f"{team1_score}-{team2_score}"


async def _detect_and_handle_result(match, ctx: SyncContext, match_id: str):
    """
    Inspect `ctx.scoreboard` for `match`. If the series is complete and no
    local `Result` exists, persist the Result.
    """
    scoreboard = ctx.scoreboard
    if not scoreboard:
        return None

    # Check if result already exists to avoid unnecessary calculation
    try:
        match_with_result = await crud.get_match_with_result_by_id(
            ctx.db_session, match.id
        )
        if not match_with_result or match_with_result.result:
            return None
    except Exception:
        logger.exception("Failed to fetch match with result for %s", match.id)
        return None

    winner, score_str = _calculate_match_outcome(scoreboard, match)
    if not winner:
        return None

    logger.info(
        "Detected result for match %s: winner=%s score=%s",
        match_id, winner, score_str
    )

    try:
        result = await save_result_and_update_picks(
            ctx.db_session, match, winner, score_str
        )
        await ctx.db_session.flush()
        ctx.notifications.append((match.id, result.id))
        return result
    except Exception:
        logger.exception("Failed to save result for match %s", match.id)
        return None


async def _sync_single_tournament(
    tournament_name_like: str, db_session, summary: dict
) -> Tuple[List, List]:
    """
    Helper to sync data for a single tournament.
    """
    logger.info("Fetching matches for pattern: '%s'", tournament_name_like)
    matches_data = await leaguepedia_client.fetch_upcoming_matches(
        tournament_name_like
    )

    if not matches_data:
        logger.warning("No matches found for '%s'.", tournament_name_like)
        return [], []

    logger.info(
        "Found %d matches for '%s'", len(matches_data), tournament_name_like
    )

    contests = defaultdict(list)
    for match_data in matches_data:
        if overview_page := match_data.get("OverviewPage"):
            contests[overview_page].append(match_data)
        else:
            logger.warning("Match data missing OverviewPage: %s", match_data)

    matches_to_schedule = []
    notifications = []
    for overview_page, contest_matches in contests.items():
        sched, notifs = await _process_contest(
            overview_page, contest_matches, db_session, summary
        )
        matches_to_schedule.extend(sched)
        notifications.extend(notifs)

    return matches_to_schedule, notifications


async def _run_post_sync_actions(
    matches_to_schedule: List, notifications: List
):
    """
    Schedules reminders and sends result notifications.
    """
    for match in matches_to_schedule:
        await schedule_reminders(match)

    logger.info("Sending result notifications...")
    for match_id, result_id in notifications:
        try:
            await send_result_notification(match_id, result_id)
        except Exception:
            logger.exception(
                "Failed to notify for match %s (result %s)",
                match_id, result_id
            )


async def perform_leaguepedia_sync() -> Optional[dict]:
    """
    Performs a full sync of tournaments, matches, and teams from
    Leaguepedia based on the configured tournament slugs.
    Returns a summary of the sync operation, or None if it fails.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            tournament_slugs = json.load(f)
        logger.info("Loaded %d slugs for sync.", len(tournament_slugs))
    except FileNotFoundError:
        logger.warning("tournaments.json not found. Skipping sync.")
        return None

    if not tournament_slugs:
        logger.info("No tournaments configured. Skipping sync.")
        return None

    summary = {"contests": 0, "matches": 0, "teams": 0}
    all_matches_to_schedule = []
    all_notifications = []

    async with get_async_session() as db_session:
        for slug in tournament_slugs:
            sched, notifs = await _sync_single_tournament(
                slug, db_session, summary
            )
            all_matches_to_schedule.extend(sched)
            all_notifications.extend(notifs)
        await db_session.commit()

    await _run_post_sync_actions(all_matches_to_schedule, all_notifications)

    logger.info(
        "Sync complete: %d contests, %d matches, %d teams upserted.",
        summary["contests"],
        summary["matches"],
        summary["teams"],
    )
    return summary

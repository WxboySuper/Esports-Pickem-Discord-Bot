"""
Public utilities for match result computation adapted from
`src.scheduler`. The intent is to provide a stable, non-underscore
API for other modules (e.g., `src.commands.sync_leaguepedia`) while
keeping the implementation colocated in `src.scheduler`.

These wrappers delegate to the existing (underscore-prefixed)
implementations in `src.scheduler`.
"""
from typing import Any, Iterable, List, Tuple, Optional

from src import scheduler


def filter_relevant_games_from_scoreboard(scoreboard_data: Iterable[dict] | None, match: Any) -> List[dict]:
    return scheduler._filter_relevant_games_from_scoreboard(scoreboard_data, match)


def calculate_team_scores(relevant_games: Iterable[dict], match: Any) -> Tuple[int, int]:
    return scheduler._calculate_team_scores(relevant_games, match)


def determine_winner(team1_score: int, team2_score: int, match: Any) -> Optional[str]:
    """
    Public wrapper for `_determine_winner`.

    Parameters:
        team1_score (int): Number of games won by `match.team1`.
        team2_score (int): Number of games won by `match.team2`.
        match (Any): Match-like object containing at least `best_of`,
            `team1`, and `team2` attributes.

    Returns:
        Optional[str]: The winning team name if a winner is determined,
            otherwise `None` when the series is not yet decided.
    """
    return scheduler._determine_winner(team1_score, team2_score, match)


async def save_result_and_update_picks(session, match, winner, score_str):
    return await scheduler._save_result_and_update_picks(session, match, winner, score_str)

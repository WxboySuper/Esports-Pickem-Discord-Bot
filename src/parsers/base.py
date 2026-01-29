"""
Base PandaScore Parser.

Contains generic parsing helpers and defines the interface for game-specific
parsers.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class PandaScoreParser:
    """Base parser interface for PandaScore API responses."""

    @staticmethod
    def parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse PandaScore ISO 8601 date string."""
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            logger.warning("Failed to parse date: %s", date_str)
            return None

    def extract_team_data(
        self, opponent: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract team data from opponent object."""
        raise NotImplementedError(
            "Subclasses must implement extract_team_data"
        )

    def extract_contest_data(
        self, match_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract contest (league/series) data from match object."""
        raise NotImplementedError(
            "Subclasses must implement extract_contest_data"
        )

    def extract_match_data(
        self, match_data: Dict[str, Any], contest_id: int
    ) -> Optional[Dict[str, Any]]:
        """Extract match data from PandaScore match object."""
        raise NotImplementedError(
            "Subclasses must implement extract_match_data"
        )

    def extract_winner_and_scores(
        self, match_data: Dict[str, Any], match: Any, winner_id: Any
    ) -> Tuple[Optional[str], int, int]:
        """Extract winner name and scores from match result."""
        raise NotImplementedError(
            "Subclasses must implement extract_winner_and_scores"
        )

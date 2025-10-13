import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import quote

logger = logging.getLogger(__name__)


class LeaguepediaClient:
    """
    An asynchronous client for interacting with the Leaguepedia (Fandom) API.
    """

    BASE_URL = "https://lol.fandom.com/api.php"

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _make_request(self, params: dict) -> dict:
        """Makes a request to the Leaguepedia API with retry logic."""
        # Default parameters for all requests
        default_params = {
            "action": "query",
            "format": "json",
            "origin": "*",  # Required for unauthenticated requests
        }
        all_params = {**default_params, **params}

        logger.debug(
            "Making Leaguepedia API request with params: %s", all_params
        )

        async with self.session.get(
            self.BASE_URL, params=all_params
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_tournament_by_slug(self, slug: str) -> dict:
        """Fetches a single tournament's data by its page name."""
        params = {
            "action": "cargoquery",
            "tables": "Tournaments",
            "fields": "Name, DateStart, DateEnd, TournamentLevel, IsOfficial",
            "where": f"Tournaments.OverviewPage = '{quote(slug)}'",
            "limit": 1,
        }
        response = await self._make_request(params)
        items = response.get("cargoquery", [])
        return items[0]["title"] if items else {}

    async def get_matches_for_tournament(
        self, tournament_slug: str
    ) -> list[dict]:
        """Fetches all matches for a given tournament slug."""
        params = {
            "action": "cargoquery",
            "tables": "ScoreboardGames=SG, Tournaments=T",
            "join_on": "SG.OverviewPage=T.OverviewPage",
            "fields": (
                "SG.MatchId, SG.Team1, SG.Team2, SG.Winner, SG.DateTime_UTC, "
                "SG.Team1Score, SG.Team2Score, SG.Tournament"
            ),
            "where": f"T.OverviewPage = '{quote(tournament_slug)}'",
            "limit": 500,  # Max limit
            "order_by": "SG.DateTime_UTC",
        }
        response = await self._make_request(params)
        return [item["title"] for item in response.get("cargoquery", [])]

    async def get_match_by_id(self, match_id: str) -> dict:
        """Fetches a single match's data by its Leaguepedia MatchId."""
        params = {
            "action": "cargoquery",
            "tables": "ScoreboardGames=SG",
            "fields": "SG.Winner, SG.Team1Score, SG.Team2Score",
            "where": f"SG.MatchId = '{quote(match_id)}'",
            "limit": 1,
        }
        response = await self._make_request(params)
        items = response.get("cargoquery", [])
        return items[0]["title"] if items else {}

    async def get_team(self, team_name: str) -> dict:
        """Fetches data for a single team by its name."""
        params = {
            "action": "cargoquery",
            "tables": "Teams",
            "fields": "Name, Image, Roster",
            "where": f"Teams.Name = '{quote(team_name)}'",
            "limit": 1,
        }
        response = await self._make_request(params)
        items = response.get("cargoquery", [])
        return items[0]["title"] if items else {}

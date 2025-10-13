import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import quote

from src.config import LEAGUEPEDIA_USER, LEAGUEPEDIA_PASS

logger = logging.getLogger(__name__)


class LeaguepediaClient:
    """
    An asynchronous client for interacting with the Leaguepedia (Fandom) API.
    Handles authentication and session management.
    """

    BASE_URL = "https://lol.fandom.com/api.php"

    def __init__(self):
        self.session = aiohttp.ClientSession()
        self._is_logged_in = False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _make_request(self, params: dict) -> dict:
        """
        Makes a request to the Leaguepedia API, handling login and retries.
        """
        if not self._is_logged_in:
            await self._login()

        # Default parameters for all requests
        default_params = {
            "action": "query",
            "format": "json",
        }
        all_params = {**default_params, **params}

        logger.debug(
            "Making Leaguepedia API request with params: %s", all_params
        )
        response = await self.session.post(self.BASE_URL, data=all_params)
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

    async def _login(self):
        """Logs the client in to the wiki to allow authenticated queries."""
        if not LEAGUEPEDIA_USER or not LEAGUEPEDIA_PASS:
            logger.warning(
                "Leaguepedia credentials not set. Proceeding anonymously. "
                "API calls may fail."
            )
            return

        # Step 1: Get login token
        token_response = await self.session.post(
            self.BASE_URL,
            params={
                "action": "query",
                "meta": "tokens",
                "type": "login",
                "format": "json",
            },
        ).json()

        login_token = (
            token_response.get("query", {}).get("tokens", {}).get("logintoken")
        )
        if not login_token:
            logger.error("Failed to retrieve Leaguepedia login token.")
            return

        # Step 2: Log in with username, password, and token
        login_response = await self.session.post(
            self.BASE_URL,
            data={
                "action": "login",
                "lgname": LEAGUEPEDIA_USER,
                "lgpassword": LEAGUEPEDIA_PASS,
                "lgtoken": login_token,
                "format": "json",
            },
        ).json()

        result = login_response.get("login", {}).get("result")
        if result == "Success":
            logger.info(
                "Successfully logged in to Leaguepedia as %s.",
                LEAGUEPEDIA_USER,
            )
            self._is_logged_in = True
        else:
            logger.error(
                "Failed to log in to Leaguepedia. Reason: %s",
                result,
            )

    async def close(self):
        """Closes the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def search_tournaments_by_name(
        self, name_query: str, limit: int = 10
    ) -> list[dict]:
        """
        Searches for tournaments using a name query (case-insensitive LIKE).
        """
        params = {
            "action": "cargoquery",
            "tables": "Tournaments",
            "fields": "Name, OverviewPage, DateStart",
            "where": f"Tournaments.Name LIKE '%{name_query}%'",
            "limit": limit,
            "order_by": "DateStart DESC",
        }
        response = await self._make_request(params)
        return [item["title"] for item in response.get("cargoquery", [])]

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

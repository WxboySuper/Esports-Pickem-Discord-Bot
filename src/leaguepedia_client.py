import logging
import os

from dotenv import load_dotenv
from mwrogue.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient

load_dotenv()

logger = logging.getLogger(__name__)


class LeaguepediaClient:
    def __init__(self):
        self.client: EsportsClient | None = None

    async def login(self):
        """Logs in to the Leaguepedia API and sets the client."""
        if self.client:
            return

        username = os.getenv("LEAGUEPEDIA_USER")
        password = os.getenv("LEAGUEPEDIA_PASS")

        if not username or not password:
            logger.warning(
                "LEAGUEPEDIA_USER or LEAGUEPEDIA_PASS not set. "
                "Proceeding with unauthenticated client."
            )
            self.client = EsportsClient(wiki="lol")
            return

        try:
            logger.info("Attempting to log in to Leaguepedia...")
            credentials = AuthCredentials(username=username, password=password)

            # Add the required user_agent attribute
            credentials.user_agent = "EsportsPickemBot/1.0"

            self.client = EsportsClient(
                wiki="lol",
                credentials=credentials,
            )

            # Verify authentication with a meta=userinfo query
            user_info_response = self.client.client.api('query', meta='userinfo')
            user_data = user_info_response.get('query', {}).get('userinfo', {})
            user_id = user_data.get('id')

            if user_id is None or user_id == 0:
                logger.error("Leaguepedia authentication failed. Check credentials.")
                # Fallback to an unauthenticated client
                self.client = EsportsClient(wiki="lol")
                return

            username = user_data.get('name')
            logger.info(f"Successfully logged in to Leaguepedia as '{username}'.")
        except Exception as e:
            logger.error(f"Failed to log in to Leaguepedia: {e}")
            logger.warning("Falling back to unauthenticated client.")
            # Fallback to an unauthenticated client
            self.client = EsportsClient(wiki="lol")

    async def fetch_upcoming_matches(self, tournament_name_like: str):
        """
        Fetches upcoming matches for a given tournament using a Cargo query.
        """
        if not self.client:
            await self.login()

        try:
            response = self.client.cargo_client.query(
                tables="MatchSchedule=MS, Tournaments=T",
                fields=(
                    "T.Name, MS.DateTime_UTC, MS.Team1, MS.Team2, "
                    "MS.OverviewPage, MS.MatchId"
                ),
                where=f'T.Name LIKE "{tournament_name_like}%"',
                join_on="MS.OverviewPage=T.OverviewPage",
                order_by="MS.DateTime_UTC ASC",
                limit="100",
            )
            return response
        except Exception as e:
            logger.error(
                f"Error fetching upcoming matches from Leaguepedia: {e}"
            )
            return []

    async def get_match_result(self, match_id: str):
        """
        Fetches the result of a specific match by its MatchId.
        """
        if not self.client:
            await self.login()

        try:
            # The cargo_client returns a list of dicts, even for one result.
            response = self.client.cargo_client.query(
                tables="MatchSchedule",
                fields="Winner, Team1Score, Team2Score",
                where=f"MatchId='{match_id}'",
                limit="1",
            )
            if response:
                return response[0]  # Return the first (and only) result
            return None
        except Exception as e:
            logger.error(f"Error fetching match result for {match_id}: {e}")
            return None


# Create a single instance of the client to be used across the application
leaguepedia_client = LeaguepediaClient()

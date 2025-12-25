import logging
import os
import asyncio
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from mwrogue.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient
from typing import Optional

load_dotenv()

logger = logging.getLogger(__name__)


class LeaguepediaClient:
    def __init__(self):
        self.client: EsportsClient | None = None
        # cooldowns per overview_page (UTC datetime until which we should not retry)
        self._cooldowns: dict[str, datetime] = {}
        # per-overview_page backoff minutes (int), doubles on each ratelimit
        self._backoff_minutes: dict[str, int] = {}
        # initial backoff in minutes when ratelimited
        # start small since documentation doesn't specify a hard limit
        self._initial_backoff = 1
        # maximum backoff cap (in minutes)
        self._max_backoff = 24 * 60

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
            user_info_response = self.client.client.api(
                "query", meta="userinfo"
            )
            user_data = user_info_response.get("query", {}).get("userinfo", {})
            user_id = user_data.get("id")

            if user_id is None or user_id == 0:
                logger.error(
                    "Leaguepedia authentication failed. Check credentials."
                )
                # Fallback to an unauthenticated client
                self.client = EsportsClient(wiki="lol")
                return

            username = user_data.get("name")
            logger.info(
                f"Successfully logged in to Leaguepedia as '{username}'."
            )
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
                    "MS.OverviewPage, MS.MatchId, MS.BestOf"
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

    async def get_scoreboard_data(self, overview_page: str) -> Optional[list]:
        """
        Fetches scoreboard data for a given tournament overview page.

        Implements a simple per-overview_page cooldown/exponential backoff when
        the API reports rate limiting, to avoid repeatedly hammering the API.
        Returns None when data couldn't be retrieved (including cooldown).
        """
        if not self.client:
            await self.login()

        now = datetime.utcnow()
        cooldown_until = self._cooldowns.get(overview_page)
        if cooldown_until and now < cooldown_until:
            wait = (cooldown_until - now).total_seconds() / 60.0
            logger.warning(
                "Skipping Leaguepedia query for %s due to cooldown (%.1f minutes remaining).",
                overview_page,
                wait,
            )
            return None

        try:
            response = self.client.cargo_client.query(
                tables="ScoreboardGames=SG, Tournaments=T",
                fields=(
                    "T.Name, SG.DateTime_UTC, SG.Team1, SG.Team2, SG.Winner, "
                    "SG.Team1Score, SG.Team2Score"
                ),
                where=f'T.OverviewPage="{overview_page}"',
                join_on="SG.OverviewPage=T.OverviewPage",
                order_by="SG.DateTime_UTC DESC",
                limit="100",  # Get all games for the series
            )
            # On success, clear any backoff state
            if overview_page in self._backoff_minutes:
                del self._backoff_minutes[overview_page]
            if overview_page in self._cooldowns:
                del self._cooldowns[overview_page]
            return response
        except Exception as e:
            # Some mwrogue / mediawiki clients sometimes raise structured tuples
            # or messages that include 'ratelimit'/'ratelimited'. Detect that and
            # apply an exponential backoff per overview_page.
            s = repr(e).lower()
            if "ratelimit" in s or "ratelimited" in s:
                # brief pause to avoid immediate retry storms from concurrent tasks
                try:
                    await asyncio.sleep(5)
                except Exception:
                    # Ignore sleep cancellation issues and continue to set backoff
                    pass

                prev = self._backoff_minutes.get(overview_page, self._initial_backoff)
                # double the backoff (but at least initial)
                next_backoff = min(max(prev, self._initial_backoff) * 2, self._max_backoff)
                self._backoff_minutes[overview_page] = next_backoff

                # add a small random jitter (0-20%) to the cooldown to reduce thundering herd
                jitter = next_backoff * random.uniform(0, 0.2)
                cooldown_minutes = next_backoff + jitter
                cooldown_until = now + timedelta(minutes=cooldown_minutes)
                self._cooldowns[overview_page] = cooldown_until
                logger.error(
                    "Rate limited by Leaguepedia for %s. Backing off for %.1f minutes (base=%d, jitter=%.1f).",
                    overview_page,
                    cooldown_minutes,
                    next_backoff,
                    jitter,
                )

                # Notify developer guild/admin channel about the rate limit
                try:
                    from src.bot_instance import get_bot_instance
                    from src.announcements import send_admin_update

                    bot = get_bot_instance()
                    dev_user = os.getenv("DEVELOPER_USER_ID")
                    mention_id = int(dev_user) if dev_user and dev_user.isdigit() else None
                    if bot and mention_id:
                        # fire-and-forget notification
                        try:
                            asyncio.create_task(
                                send_admin_update(
                                    f"Leaguepedia rate limit hit for {overview_page}. Backing off for {cooldown_minutes:.1f} minutes.",
                                    mention_user_id=mention_id,
                                )
                            )
                        except Exception:
                            # Last resort: synchronous attempt (best-effort)
                            await send_admin_update(
                                f"Leaguepedia rate limit hit for {overview_page}. Backing off for {cooldown_minutes:.1f} minutes.",
                                mention_user_id=mention_id,
                            )
                    else:
                        # Try to send without mention if user id missing
                        if bot:
                            try:
                                asyncio.create_task(
                                    send_admin_update(
                                        f"Leaguepedia rate limit hit for {overview_page}. Backing off for {cooldown_minutes:.1f} minutes.",
                                    )
                                )
                            except Exception:
                                pass
                except Exception:
                    logger.debug("Could not notify developer guild about rate limit.")

                return None

            logger.error(
                f"Error fetching scoreboard data for {overview_page}: {e}"
            )
            return None


# Create a single instance of the client to be used across the application
leaguepedia_client = LeaguepediaClient()

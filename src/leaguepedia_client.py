import logging
import os
import asyncio
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from mwrogue.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient
from typing import Optional

load_dotenv()

logger = logging.getLogger(__name__)


class LeaguepediaClient:
    def __init__(self):
        self.client: EsportsClient | None = None
        # cooldowns per overview_page (UTC datetime until which we should
        # not retry)
        self._cooldowns: dict[str, datetime] = {}
        # per-overview_page backoff minutes (float), doubles on each ratelimit
        self._backoff_minutes: dict[str, float] = {}
        # initial backoff in minutes when ratelimited
        # start small since documentation doesn't specify a hard limit
        self._initial_backoff = 1
        # maximum backoff cap (in minutes)
        self._max_backoff = 24 * 60
        # Background tasks set to prevent garbage collection
        self._background_tasks = set()

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

    def _detect_rate_limit(self, exc: Exception) -> tuple[bool, float | None]:
        """
        Detect rate limit errors and extract wait time if available.
        Returns (is_rate_limit, retry_after_seconds).
        """
        # 1. Check for HTTP response status and headers
        resp = getattr(exc, "response", None)
        if resp:
            status = getattr(
                resp, "status", getattr(resp, "status_code", None)
            )
            if status == 429:
                retry_after = None
                headers = getattr(resp, "headers", {})
                if "Retry-After" in headers:
                    try:
                        retry_after = float(headers["Retry-After"])
                    except (ValueError, TypeError):
                        pass
                return True, retry_after

            # Check JSON body for MediaWiki throttling codes
            try:
                # Ensure resp has .json() method
                if hasattr(resp, "json") and callable(resp.json):
                    data = resp.json()
                    if isinstance(data, dict):
                        code = data.get("error", {}).get("code")
                        if code in (
                            "ratelimited",
                            "maxlag",
                            "actionthrottledtext",
                        ):
                            retry_after = None
                            if "Retry-After" in getattr(resp, "headers", {}):
                                try:
                                    retry_after = float(
                                        resp.headers["Retry-After"]
                                    )
                                except (ValueError, TypeError):
                                    pass
                            return True, retry_after
            except Exception:
                pass

        # 2. Check for mwclient APIError code or args
        code = getattr(exc, "code", None)
        if isinstance(code, str) and code.lower() in (
            "ratelimit",
            "ratelimited",
            "maxlag",
        ):
            return True, None

        # Check args for tuple structure ('ratelimited', ...)
        args = getattr(exc, "args", [])
        if args and isinstance(args, tuple) and len(args) > 0:
            first_arg = args[0]
            if isinstance(first_arg, str) and first_arg.lower() in (
                "ratelimited",
                "maxlag",
            ):
                return True, None

        return False, None

    def _apply_rate_limit_backoff(
        self, overview_page: str, retry_seconds: float | None
    ) -> float:
        """
        Calculates and applies the backoff cooldown for a rate-limited page.
        Returns the cooldown duration in minutes.
        """
        # Determine base backoff
        if retry_seconds is not None:
            # Use provided retry-after, converted to minutes and capped
            next_backoff = min(retry_seconds / 60.0, self._max_backoff)
        else:
            # Exponential backoff (restore previous logic: prev or
            # initial, then double)
            prev = self._backoff_minutes.get(
                overview_page, self._initial_backoff
            )
            next_backoff = min(
                max(prev, self._initial_backoff) * 2,
                self._max_backoff,
            )

        self._backoff_minutes[overview_page] = next_backoff

        # add a small random jitter (0-20%) to the cooldown
        jitter = next_backoff * random.uniform(0, 0.2)
        cooldown_minutes = next_backoff + jitter
        now = datetime.now(timezone.utc)
        cooldown_until = now + timedelta(minutes=cooldown_minutes)
        self._cooldowns[overview_page] = cooldown_until
        logger.error(
            "Rate limited by Leaguepedia for %s. Backing off for %.1f "
            "minutes (base=%.1f, jitter=%.1f).",
            overview_page,
            cooldown_minutes,
            next_backoff,
            jitter,
        )
        return cooldown_minutes
    def _notify_admin_rate_limit(
        self, overview_page: str, cooldown_minutes: float
    ):
        """
        Schedules a background task to notify admins about the rate limit.
        """
        try:
            from src.bot_instance import get_bot_instance
            from src.announcements import send_admin_update

            bot = get_bot_instance()
            dev_user = os.getenv("DEVELOPER_USER_ID")
            mention_id = (
                int(dev_user) if dev_user and dev_user.isdigit() else None
            )
            if bot:
                try:
                    msg = (
                        f"Leaguepedia rate limit hit for "
                        f"{overview_page}. Backing off for "
                        f"{cooldown_minutes:.1f} minutes."
                    )
                    task = asyncio.create_task(
                        send_admin_update(msg, mention_user_id=mention_id)
                    )
                    self._background_tasks.add(task)

                    def _on_task_done(t):
                        self._background_tasks.discard(t)
                        try:
                            exc = t.exception()
                            if exc:
                                logger.error(
                                    "Background admin update task "
                                    "failed: %s",
                                    exc,
                                )
                        except asyncio.CancelledError:
                            pass

                    task.add_done_callback(_on_task_done)
                except Exception as task_err:
                    # If we cannot schedule the task,
                    # log the error instead of blocking.
                    logger.error(
                        "Failed to schedule admin update task for "
                        "rate limit notification: %s",
                        task_err,
                    )
        except Exception:
            logger.debug("Could not notify developer guild about rate limit.")

    async def get_scoreboard_data(self, overview_page: str) -> Optional[list]:
        """
        Fetches scoreboard data for a given tournament overview page.

        Implements a simple per-overview_page cooldown/exponential backoff when
        the API reports rate limiting, to avoid repeatedly hammering the API.
        Returns None when data couldn't be retrieved (including cooldown).
        """
        if not self.client:
            await self.login()

        now = datetime.now(timezone.utc)
        cooldown_until = self._cooldowns.get(overview_page)
        if cooldown_until and now < cooldown_until:
            wait = (cooldown_until - now).total_seconds() / 60.0
            logger.warning(
                "Skipping Leaguepedia query for %s due to cooldown (%.1f "
                "minutes remaining).",
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
            is_limit, retry_seconds = self._detect_rate_limit(e)

            if is_limit:
                # brief pause to avoid immediate retry storms
                # from concurrent tasks
                try:
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

                cooldown_minutes = self._apply_rate_limit_backoff(
                    overview_page, retry_seconds
                )
                self._notify_admin_rate_limit(overview_page, cooldown_minutes)
                return None

            logger.error(
                f"Error fetching scoreboard data for {overview_page}: {e}"
            )
            return None


# Create a single instance of the client to be used across the application
leaguepedia_client = LeaguepediaClient()

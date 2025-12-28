import logging
import os
import asyncio
import random
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
from mwrogue.auth_credentials import AuthCredentials
from mwrogue.esports_client import EsportsClient
from typing import Optional

load_dotenv()

logger = logging.getLogger(__name__)
# Expose send_admin_update symbol at module level so tests can patch it.
# Importing at module level may create a circular import in some runtime
# scenarios, so this is a best-effort import that falls back to `None`.
try:
    from src.announcements import send_admin_update  # type: ignore
except Exception:
    send_admin_update = None  # type: ignore


class LeaguepediaClient:
    def __init__(self):
        """
        Initialize internal state for a LeaguepediaClient instance.

        Sets up:
        - client: authenticated or unauthenticated EsportsClient
          placeholder (None until login).
        - _cooldowns: mapping from overview_page to UTC datetime until
          which requests should be skipped.
        - _backoff_minutes: per-overview_page exponential backoff value
          in minutes (doubles on rate limits).
        - _initial_backoff: base backoff in minutes to use when first
          rate-limited (1 minute).
        - _max_backoff: maximum backoff cap in minutes (1440 minutes).
        """
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
        """
        Ensure self.client is an authenticated Leaguepedia EsportsClient
        when valid credentials are available.

        Reads LEAGUEPEDIA_USER and LEAGUEPEDIA_PASS from the environment
        to create authenticated credentials and verifies them with a
        meta=userinfo query. If credentials are missing or authentication
        fails, falls back to creating an unauthenticated
        EsportsClient(wiki="lol"). If self.client is already set, does
        nothing. Logs authentication attempts, failures, and fallbacks.
        """
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
                "Successfully logged in to Leaguepedia as '%s'.", username
            )
        except Exception as e:
            logger.error("Failed to log in to Leaguepedia: %s", e)
            self.client = None

    async def fetch_upcoming_matches(self, tournament_name_like: str):
        """
        Retrieve upcoming matches for tournaments whose name starts with
        the provided pattern.

        Performs a Cargo query against Leaguepedia's MatchSchedule and
        Tournaments tables and returns the raw query result. If the fetch
        fails, an empty list is returned.

        Parameters:
            tournament_name_like (str): Prefix used to match tournament
                names; the function performs a SQL `LIKE` match as
                `"{tournament_name_like}%"`.

        Returns:
            list: The raw list of match records returned by the Cargo
                client, or an empty list if an error occurred.
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
                "Error fetching upcoming matches from Leaguepedia: %s", e
            )
            return []

    def _extract_retry_after(self, resp) -> float | None:
        """
        Safely extract Retry-After header from response.
        Returns retry_after in seconds as float, or None if not
        present/invalid.

        Per RFC 7231, Retry-After can be either:
        - delay-seconds (numeric)
        - HTTP-date (e.g., "Wed, 21 Oct 2015 07:28:00 GMT")
        """
        headers = getattr(resp, "headers", {})
        if "Retry-After" not in headers:
            return None

        retry_value = headers["Retry-After"]

        # Try parsing as numeric delay-seconds
        try:
            return float(retry_value)
        except (ValueError, TypeError):
            pass

        # Try parsing as HTTP-date
        try:
            retry_date = parsedate_to_datetime(retry_value)
            now = datetime.now(timezone.utc)
            delta = (retry_date - now).total_seconds()
            # Return positive delay or 0 if date is in the past
            return max(0.0, delta)
        except (ValueError, TypeError, OverflowError):
            pass

        return None

    def _check_http_status_for_rate_limit(
        self, exc: Exception
    ) -> tuple[bool, float | None]:
        """
        Check HTTP status code and MediaWiki error codes in response body.
        Returns (is_rate_limit, retry_after_seconds).
        """
        resp = getattr(exc, "response", None)
        if not resp:
            return False, None

        # Check HTTP 429 status
        status = getattr(resp, "status", getattr(resp, "status_code", None))
        if status == 429:
            retry_after = self._extract_retry_after(resp)
            return True, retry_after

        # Check JSON body for MediaWiki throttling codes
        try:
            if hasattr(resp, "json") and callable(resp.json):
                data = resp.json()
                if isinstance(data, dict):
                    code = data.get("error", {}).get("code")
                    if code in (
                        "ratelimited",
                        "maxlag",
                        "actionthrottledtext",
                    ):
                        retry_after = self._extract_retry_after(resp)
                        return True, retry_after
        except Exception:
            pass

        return False, None

    def _check_api_error_for_rate_limit(
        self, exc: Exception
    ) -> tuple[bool, float | None]:
        """
        Check exception code attribute for rate limit indicators.
        Returns (is_rate_limit, retry_after_seconds).
        """
        code = getattr(exc, "code", None)
        if isinstance(code, str) and code.lower() in (
            "ratelimit",
            "ratelimited",
            "maxlag",
        ):
            return True, None
        return False, None

    def _check_exception_attributes_for_rate_limit(
        self, exc: Exception
    ) -> tuple[bool, float | None]:
        """
        Check exception args for rate limit indicators.
        Returns (is_rate_limit, retry_after_seconds).
        """
        args = getattr(exc, "args", [])
        if args and isinstance(args, tuple) and len(args) > 0:
            first_arg = args[0]
            if isinstance(first_arg, str) and first_arg.lower() in (
                "ratelimited",
                "maxlag",
            ):
                return True, None
        return False, None

    def _detect_rate_limit(self, exc: Exception) -> tuple[bool, float | None]:
        """
        Detect rate limit errors and extract wait time if available.
        Returns (is_rate_limit, retry_after_seconds).
        """
        # Check HTTP status and JSON body
        is_limited, retry_after = self._check_http_status_for_rate_limit(exc)
        if is_limited:
            return True, retry_after

        # Check API error code attribute
        is_limited, retry_after = self._check_api_error_for_rate_limit(exc)
        if is_limited:
            return True, retry_after

        # Check exception args
        is_limited, retry_after = (
            self._check_exception_attributes_for_rate_limit(exc)
        )
        if is_limited:
            return True, retry_after

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

    def _should_skip_due_to_cooldown(
        self, overview_page: str
    ) -> tuple[bool, float]:
        """
        Check if a request should be skipped due to active cooldown.

        Returns (should_skip, wait_minutes) where wait_minutes is the
        number of minutes remaining until cooldown expires (or 0 if no
        cooldown is active).
        """
        now = datetime.now(timezone.utc)
        cooldown_until = self._cooldowns.get(overview_page)
        if cooldown_until and now < cooldown_until:
            wait = (cooldown_until - now).total_seconds() / 60.0
            return True, wait
        return False, 0.0

    def _query_scoreboard_games(self, overview_page: str) -> Optional[list]:
        """
        Execute Cargo query to fetch scoreboard games for an overview page.

        Returns the raw query result, or raises an exception on failure.
        """
        return self.client.cargo_client.query(
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

    def _clear_backoff_state(self, overview_page: str) -> None:
        """Clear cached backoff and cooldown state after successful query."""
        if overview_page in self._backoff_minutes:
            del self._backoff_minutes[overview_page]
        if overview_page in self._cooldowns:
            del self._cooldowns[overview_page]

    async def _handle_rate_limit_error(
        self, overview_page: str, retry_seconds: float | None
    ) -> None:
        """
        Handle a rate-limit exception by applying backoff and notifying.

        Pauses briefly to avoid retry storms, applies exponential backoff,
        and schedules an admin notification.
        """
        # Brief pause to avoid immediate retry storms from concurrent tasks
        await asyncio.sleep(5)

        cooldown_minutes = self._apply_rate_limit_backoff(
            overview_page, retry_seconds
        )
        self._notify_admin_rate_limit(overview_page, cooldown_minutes)

    async def get_scoreboard_data(self, overview_page: str) -> Optional[list]:
        """
        Fetch scoreboard entries for the tournament identified by
        overview_page.

        Parameters:
            overview_page (str): The tournament OverviewPage identifier used
                to query scoreboard games.

        Returns:
            Optional[list]: A list of scoreboard records for the overview
                page, or `None` if data could not be retrieved (including
                when a cooldown/backoff is active or a fetch error occurs).
        """
        if not self.client:
            await self.login()

        # Check if cooldown is active
        should_skip, wait = self._should_skip_due_to_cooldown(overview_page)
        if should_skip:
            logger.warning(
                "Skipping Leaguepedia query for %s due to cooldown (%.1f "
                "minutes remaining).",
                overview_page,
                wait,
            )
            return None

        try:
            response = self._query_scoreboard_games(overview_page)
            # On success, clear any backoff state
            self._clear_backoff_state(overview_page)
            return response
        except Exception as e:
            is_limit, retry_seconds = self._detect_rate_limit(e)

            if is_limit:
                await self._handle_rate_limit_error(
                    overview_page, retry_seconds
                )
                return None

            logger.error(
                "Error fetching scoreboard data for %s: %s", overview_page, e
            )
            return None


# Create a single instance of the client to be used across the application
leaguepedia_client = LeaguepediaClient()
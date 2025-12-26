import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from src.leaguepedia_client import LeaguepediaClient


# Mock Exception for HTTP 429
class MockHTTPError(Exception):
    def __init__(self, status, retry_after=None, json_data=None):
        self.response = MagicMock()
        self.response.status_code = status
        # Explicitly set status to None so getattr(resp, "status", ...)
        # falls back to status_code or mock it to match status if we want
        # to support both.
        # But for the test to pass the 'getattr' chain check where status is
        # checked first: if status exists (MagicMock), it is used.
        # So we must set it to the status value or ensure it doesn't exist.
        # MagicMock creates attributes on access, so we should set it.
        self.response.status = status
        self.response.headers = {}
        if retry_after:
            self.response.headers["Retry-After"] = retry_after
        self.json_data = json_data

        # Mock .json() method
        self.response.json = MagicMock(return_value=json_data or {})


# Mock API Error with code attribute
class MockAPIError(Exception):
    def __init__(self, code):
        self.code = code


@pytest.mark.asyncio
async def test_rate_limit_http_429_with_retry_after():
    client = LeaguepediaClient()
    client.client = MagicMock()
    # Mock cargo_client.query to raise HTTP 429
    client.client.cargo_client.query.side_effect = MockHTTPError(
        429, retry_after="120"
    )

    with patch("asyncio.sleep", new_callable=MagicMock), patch(
        "src.announcements.send_admin_update", new_callable=MagicMock
    ):

        await client.get_scoreboard_data("TestPage")

        # Verify cooldown is set to approx 2 minutes (Retry-After)
        # We allow some delta because the code might add jitter or
        # processing time
        assert "TestPage" in client._cooldowns
        cooldown = client._cooldowns["TestPage"]
        now = datetime.now(timezone.utc)

        # 120 seconds = 2 minutes.
        # The logic should use 120 seconds.
        # Ensure it's roughly 2 mins from now + jitter (up to 20% = 24s).
        diff = (cooldown - now).total_seconds()
        # Allowing some buffer for jitter
        assert 110 < diff < 150


@pytest.mark.asyncio
async def test_rate_limit_tuple_args():
    client = LeaguepediaClient()
    client.client = MagicMock()
    # Mock Exception like the one in user log: ('ratelimited', 'msg', 'info')
    client.client.cargo_client.query.side_effect = Exception(
        "ratelimited", "You've exceeded...", "See https://..."
    )

    with patch("asyncio.sleep", new_callable=MagicMock), patch(
        "src.announcements.send_admin_update", new_callable=MagicMock
    ):

        await client.get_scoreboard_data("TestPageTuple")

        assert "TestPageTuple" in client._cooldowns
        # Should use backoff logic
        # (default 1 min * 2 = 2 mins for first hit + jitter)
        assert client._backoff_minutes["TestPageTuple"] == 2


@pytest.mark.asyncio
async def test_rate_limit_json_code():
    client = LeaguepediaClient()
    client.client = MagicMock()
    # Mock HTTP 200 but with error in JSON (MediaWiki sometimes does this)
    # Or HTTP 500 etc.
    # The instruction says "check response.json().get('error', {}).get('code')"
    client.client.cargo_client.query.side_effect = MockHTTPError(
        200, json_data={"error": {"code": "maxlag"}}
    )

    with patch("asyncio.sleep", new_callable=MagicMock), patch(
        "src.announcements.send_admin_update", new_callable=MagicMock
    ):

        await client.get_scoreboard_data("TestPageJSON")

        assert "TestPageJSON" in client._cooldowns
        # Backoff logic
        assert client._backoff_minutes["TestPageJSON"] == 2


@pytest.mark.asyncio
async def test_rate_limit_attribute_code():
    """Test detection via the .code attribute on the exception."""
    client = LeaguepediaClient()
    client.client = MagicMock()
    # Mock an error with a .code attribute (common in mwclient)
    client.client.cargo_client.query.side_effect = MockAPIError("ratelimited")

    with patch("asyncio.sleep", new_callable=MagicMock), patch(
        "src.announcements.send_admin_update", new_callable=MagicMock
    ):

        await client.get_scoreboard_data("TestPageCode")

        assert "TestPageCode" in client._cooldowns
        # Backoff logic
        assert client._backoff_minutes["TestPageCode"] == 2


@pytest.mark.asyncio
async def test_rate_limit_avoid_false_positive():
    """
    Ensure that we do NOT detect rate limits based on loose string matching
    in the exception message/repr.
    """
    client = LeaguepediaClient()
    client.client = MagicMock()
    # Exception with string message containing "ratelimited"
    # This should now be treated as a regular error, not a rate limit.
    client.client.cargo_client.query.side_effect = Exception(
        "Some unknown error: ratelimited by upstream"
    )

    with patch("asyncio.sleep", new_callable=MagicMock), patch(
        "src.announcements.send_admin_update", new_callable=MagicMock
    ), patch("src.leaguepedia_client.logger") as mock_logger:

        await client.get_scoreboard_data("TestPageString")

        # Should NOT be in cooldowns
        assert "TestPageString" not in client._cooldowns

        # Should have logged a regular error
        mock_logger.error.assert_called()
        assert (
            "Error fetching scoreboard data"
            in mock_logger.error.call_args[0][0]
        )


@pytest.mark.asyncio
async def test_not_rate_limit():
    client = LeaguepediaClient()
    client.client = MagicMock()
    client.client.cargo_client.query.side_effect = Exception(
        "Some other error"
    )

    with patch("src.leaguepedia_client.logger") as mock_logger:
        await client.get_scoreboard_data("TestPageOther")

        assert "TestPageOther" not in client._cooldowns
        assert mock_logger.error.call_count == 1
        assert (
            "Error fetching scoreboard data"
            in mock_logger.error.call_args[0][0]
        )

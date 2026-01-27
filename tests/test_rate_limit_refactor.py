import pytest
from unittest.mock import AsyncMock, MagicMock
from src.pandascore_client import PandaScoreClient, RateLimitError
import asyncio
from datetime import datetime, timezone, timedelta


@pytest.mark.asyncio
async def test_update_rate_limits():
    client = PandaScoreClient(api_key="test")
    headers = {
        "X-Rate-Limit-Limit": "1000",
        "X-Rate-Limit-Remaining": "500",
        "X-Rate-Limit-Reset": "1234567890",
    }
    client._update_rate_limits(headers)

    assert client._rate_limit_limit == 1000
    assert client._rate_limit_remaining == 500
    assert client._rate_limit_reset == 1234567890
    assert client._request_count == 500  # Syncs: 1000 - 500


@pytest.mark.asyncio
async def test_update_rate_limits_alt_headers():
    client = PandaScoreClient(api_key="test")
    headers = {
        "RateLimit-Limit": "2000",
        "RateLimit-Remaining": "100",
        "RateLimit-Reset": "9999",
    }
    client._update_rate_limits(headers)

    assert client._rate_limit_limit == 2000
    assert client._rate_limit_remaining == 100
    assert client._request_count == 1900


@pytest.mark.asyncio
async def test_do_request_once_updates_limits():
    client = PandaScoreClient(api_key="test")

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {
        "X-Rate-Limit-Remaining": "900",
        "X-Rate-Limit-Limit": "1000",
    }
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {}
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    await client._do_request_once(mock_session, "http://test.com")

    assert client._rate_limit_remaining == 900
    assert client._request_count == 100


@pytest.mark.asyncio
async def test_warning_callback_triggered():
    client = PandaScoreClient(api_key="test")
    callback = AsyncMock()
    client.add_rate_limit_warning_callback(callback)

    # Threshold is 200. Set remaining to 100.
    headers = {"X-Rate-Limit-Remaining": "100", "X-Rate-Limit-Limit": "1000"}

    client._update_rate_limits(headers)

    # Allow async task to run
    await asyncio.sleep(0)

    callback.assert_called_once()
    status = callback.call_args[0][0]
    assert status["remaining"] == 100
    assert status["limit"] == 1000


@pytest.mark.asyncio
async def test_warning_callback_throttled():
    client = PandaScoreClient(api_key="test")
    callback = AsyncMock()
    client.add_rate_limit_warning_callback(callback)

    headers = {"X-Rate-Limit-Remaining": "100", "X-Rate-Limit-Limit": "1000"}

    # First trigger
    client._update_rate_limits(headers)
    await asyncio.sleep(0)
    assert callback.call_count == 1

    # Second trigger immediately
    client._update_rate_limits(headers)
    await asyncio.sleep(0)
    assert callback.call_count == 1  # Should not be called again

    # Advance time (hacky, modify _last_warning_time)
    client._last_warning_time = datetime.now(timezone.utc) - timedelta(hours=2)

    client._update_rate_limits(headers)
    await asyncio.sleep(0)
    assert callback.call_count == 2


@pytest.mark.asyncio
async def test_check_rate_limit_blocks():
    client = PandaScoreClient(api_key="test")
    client._rate_limit_remaining = 0
    client._rate_limit_reset = 60

    with pytest.raises(RateLimitError):
        client._check_rate_limit()

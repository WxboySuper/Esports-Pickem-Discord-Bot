import pytest
import asyncio
from unittest.mock import patch, MagicMock
from src.pandascore_client import PandaScoreClient, PandaScoreError


@pytest.mark.asyncio
async def test_pandascore_client_timeout_init():
    """Verify PandaScoreClient initializes ClientSession with a timeout."""
    client = PandaScoreClient(api_key="test_key")

    # Reset session if it exists (though it shouldn't for a new instance)
    if client._session:
        await client.close()

    with patch(
        "src.pandascore_client.aiohttp.ClientSession"
    ) as mock_session_cls:
        mock_session_cls.return_value = MagicMock()

        await client._get_session()

        # Check if timeout was passed
        kwargs = mock_session_cls.call_args.kwargs
        assert "timeout" in kwargs, "ClientSession initialized without timeout"
        assert kwargs["timeout"].total == 30, "Timeout should be 30 seconds"


@pytest.mark.asyncio
async def test_pandascore_client_handle_timeout_error():
    """Verify that asyncio.TimeoutError is caught and retried."""
    client = PandaScoreClient(api_key="test_key")

    # Mock _do_request_once to raise asyncio.TimeoutError
    with patch.object(
        client, "_do_request_once", side_effect=asyncio.TimeoutError("Timeout")
    ) as mock_request, patch.object(
        client, "_get_session", return_value=MagicMock()
    ), patch(
        "asyncio.sleep", return_value=None
    ):
        with pytest.raises(PandaScoreError, match="Request timeout after"):
            await client._make_request("/test", max_retries=2)

    # Should have tried 2 times
    assert mock_request.call_count == 2

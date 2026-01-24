import pytest
from unittest.mock import patch, MagicMock
from src.pandascore_client import PandaScoreClient


@pytest.mark.asyncio
async def test_pandascore_client_timeout():
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

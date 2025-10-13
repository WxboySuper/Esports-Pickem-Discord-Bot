import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from src.scheduler import (
    schedule_reminders,
    schedule_live_polling,
    poll_live_match_job,
)
from src.announcements import get_announcement_channel, send_announcement
from src.leaguepedia import get_tournaments, get_matches, get_match_results


@pytest.fixture
def mock_guild():
    guild = MagicMock()
    guild.id = 123
    guild.name = "Test Guild"
    return guild


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.session = AsyncMock()
    return bot


@pytest.mark.asyncio
async def test_get_announcement_channel(mock_guild):
    mock_guild.text_channels = []
    mock_guild.create_text_channel = AsyncMock()
    await get_announcement_channel(mock_guild)
    mock_guild.create_text_channel.assert_called_once()


@pytest.mark.asyncio
async def test_send_announcement(mock_guild):
    with patch(
        "src.announcements.get_announcement_channel", new_callable=AsyncMock
    ) as mock_get_channel:
        mock_channel = AsyncMock()
        mock_get_channel.return_value = mock_channel
        embed = MagicMock()
        await send_announcement(mock_guild, embed)
        mock_channel.send.assert_called_once_with(embed=embed)


@pytest.mark.asyncio
async def test_schedule_reminders(mock_guild):
    with patch("src.scheduler.get_async_session") as mock_get_session, patch(
        "src.scheduler.scheduler.add_job"
    ) as mock_add_job, patch(
        "src.scheduler.scheduler.get_job"
    ) as mock_get_job:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        mock_match = MagicMock()
        mock_match.id = 1
        mock_match.scheduled_time = datetime.now(timezone.utc) + timedelta(
            hours=1
        )
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_match])
        mock_session.exec.return_value = mock_result
        mock_get_job.return_value = None
        await schedule_reminders(mock_guild.id)
        assert mock_add_job.call_count == 2


@pytest.mark.asyncio
@patch("src.scheduler.scheduler")
@patch("src.scheduler.get_async_session")
async def test_schedule_live_polling_schedules_job(
    mock_get_session, mock_scheduler, mock_guild
):
    """
    Tests that the orchestrator job correctly finds matches starting soon
    and schedules a new polling job for them.
    """
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session

    mock_match = MagicMock()
    mock_match.id = 1
    mock_match.result = None
    mock_result = MagicMock()
    mock_result.all.return_value = [mock_match]
    mock_session.exec.return_value = mock_result

    mock_scheduler.get_job.return_value = None  # Simulate job does not exist

    await schedule_live_polling(mock_guild.id)

    mock_scheduler.add_job.assert_called_once()
    call_args = mock_scheduler.add_job.call_args
    assert call_args[0][0] == poll_live_match_job
    assert call_args.kwargs["id"] == "poll_match_1"
    assert call_args.kwargs["args"] == [1, mock_guild.id]


@pytest.mark.asyncio
@patch("src.scheduler.scheduler")
@patch("src.scheduler.send_result_notification", new_callable=AsyncMock)
@patch("src.scheduler.aiohttp.ClientSession")
@patch("src.scheduler.get_async_session")
async def test_poll_live_match_job_finds_result(
    mock_get_session,
    mock_http_session,
    mock_send_notification,
    mock_scheduler,
    mock_guild,
):
    """
    Tests that the polling job correctly identifies a winner, saves the result,
    sends a notification, and removes itself.
    """
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session

    mock_match = AsyncMock()
    mock_match.id = 1
    mock_match.leaguepedia_id = "LP-123"
    mock_match.result = None
    mock_session.get.return_value = mock_match

    # Ensure the mock client's async method returns an awaitable
    mock_api_client = AsyncMock()
    mock_api_client.get_match_by_id.return_value = {"Winner": "C9"}
    with patch(
        "src.scheduler.LeaguepediaClient", return_value=mock_api_client
    ):
        await poll_live_match_job(mock_match.id, mock_guild.id)

    mock_session.add.assert_called_once()
    mock_send_notification.assert_awaited_once()
    mock_scheduler.remove_job.assert_called_once_with("poll_match_1")


@pytest.mark.asyncio
async def test_get_tournaments(mock_bot):
    with patch(
        "src.leaguepedia.make_request", new_callable=AsyncMock
    ) as mock_request:
        await get_tournaments(mock_bot.session, "LCS 2024")
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_get_matches(mock_bot):
    with patch(
        "src.leaguepedia.make_request", new_callable=AsyncMock
    ) as mock_request:
        await get_matches(mock_bot.session, "LCS 2024")
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_get_match_results(mock_bot):
    with patch(
        "src.leaguepedia.make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_response = {
            "query": {
                "matchschedule": [
                    {"team1": "C9", "team2": "TL", "winner": "C9"}
                ]
            }
        }
        mock_request.return_value = mock_response

        results = await get_match_results(mock_bot.session, "LCS", "C9", "TL")

        assert results == mock_response["query"]["matchschedule"]
        mock_request.assert_called_once()

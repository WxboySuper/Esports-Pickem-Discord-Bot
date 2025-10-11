import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from src.scheduler import (
    schedule_reminders,
    poll_for_results,
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


from datetime import timezone

@pytest.mark.asyncio
async def test_schedule_reminders(mock_bot, mock_guild):
    with patch("src.scheduler.get_session") as mock_get_session, patch(
        "src.scheduler.scheduler.add_job"
    ) as mock_add_job, patch(
        "src.scheduler.scheduler.get_job"
    ) as mock_get_job:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        mock_match = MagicMock()
        mock_match.id = 1
        mock_match.scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_match])
        mock_session.exec.return_value = mock_result
        mock_get_job.return_value = None
        await schedule_reminders(mock_bot, mock_guild)
        assert mock_add_job.call_count == 2


@pytest.mark.asyncio
async def test_poll_for_results(mock_bot, mock_guild):
    with patch("src.scheduler.get_session") as mock_get_session, patch(
        "src.scheduler.get_match_results"
    ) as mock_get_results, patch(
        "src.scheduler.send_result_notification"
    ) as mock_send_notification:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        mock_match = MagicMock()
        mock_match.id = 1
        mock_match.result = None
        mock_match.contest.name = "LCS"
        mock_match.team1 = "C9"
        mock_match.team2 = "TL"
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_match])
        mock_session.exec.return_value = mock_result
        mock_get_results.return_value = [{"winner": "C9"}]
        await poll_for_results(mock_bot, mock_guild)
        mock_send_notification.assert_called_once()


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
        await get_match_results(mock_bot.session, "LCS", "C9", "TL")
        mock_request.assert_called_once()

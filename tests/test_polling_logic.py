import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

from src.models import Match, Contest, Result
from src.scheduler import poll_live_match_job


@pytest.mark.asyncio
async def test_poll_live_match_job_mid_series_update():
    """
    Tests that a mid-series update is correctly announced when the score changes.
    """
    # Arrange
    mock_match = Match(
        id=1,
        team1="Team A",
        team2="Team B",
        best_of=5,
        scheduled_time=datetime.now(timezone.utc) - timedelta(hours=1),
        last_announced_score="0-0",
        contest=Contest(leaguepedia_id="LPL/2025_Season/Spring_Season"),
    )
    mock_scoreboard_data = [{"Winner": "1"}]
    mock_session = AsyncMock()

    with patch("src.scheduler.get_async_session") as mock_get_async_session, \
         patch("src.scheduler.crud.get_match_with_result_by_id", new_callable=AsyncMock, return_value=mock_match) as mock_get_match, \
         patch("src.scheduler.leaguepedia_client.get_scoreboard_data", new_callable=AsyncMock, return_value=mock_scoreboard_data) as mock_get_scoreboard, \
         patch("src.scheduler.send_mid_series_update", new_callable=AsyncMock) as mock_send_update, \
         patch("src.scheduler.send_result_notification", new_callable=AsyncMock) as mock_send_result, \
         patch("src.scheduler.scheduler.remove_job") as mock_remove_job:

        mock_get_async_session.return_value.__aenter__.return_value = mock_session

        # Act
        await poll_live_match_job(match_db_id=1, guild_id=123)

        # Assert
        mock_get_match.assert_awaited_once_with(mock_session, 1)
        mock_get_scoreboard.assert_awaited_once_with("LPL/2025_Season/Spring_Season")
        mock_send_update.assert_awaited_once()
        mock_send_result.assert_not_called()
        mock_remove_job.assert_not_called()
        assert mock_match.last_announced_score == "1-0"
        mock_session.add.assert_called_once_with(mock_match)
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_live_match_job_final_result():
    """
    Tests that a final result is correctly announced when a series concludes.
    """
    # Arrange
    mock_match = Match(
        id=2,
        team1="Team A",
        team2="Team B",
        best_of=3,
        scheduled_time=datetime.now(timezone.utc) - timedelta(hours=1),
        last_announced_score="1-0",
        contest=Contest(leaguepedia_id="LPL/2025_Season/Spring_Season"),
    )
    mock_scoreboard_data = [{"Winner": "1"}, {"Winner": "1"}]
    mock_session = AsyncMock()

    with patch("src.scheduler.get_async_session") as mock_get_async_session, \
         patch("src.scheduler.crud.get_match_with_result_by_id", new_callable=AsyncMock, return_value=mock_match) as mock_get_match, \
         patch("src.scheduler.leaguepedia_client.get_scoreboard_data", new_callable=AsyncMock, return_value=mock_scoreboard_data) as mock_get_scoreboard, \
         patch("src.scheduler.send_mid_series_update", new_callable=AsyncMock) as mock_send_update, \
         patch("src.scheduler.send_result_notification", new_callable=AsyncMock) as mock_send_result, \
         patch("src.scheduler.scheduler.remove_job") as mock_remove_job:

        mock_get_async_session.return_value.__aenter__.return_value = mock_session

        # Act
        await poll_live_match_job(match_db_id=2, guild_id=123)

        # Assert
        mock_get_match.assert_awaited_once_with(mock_session, 2)
        mock_get_scoreboard.assert_awaited_once_with("LPL/2025_Season/Spring_Season")
        mock_send_update.assert_not_called()
        mock_send_result.assert_awaited_once()
        mock_remove_job.assert_called_once()
        # Assert that a Result object was created and saved
        mock_session.add.assert_called_once()
        assert isinstance(mock_session.add.call_args[0][0], Result)
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_live_match_job_no_score_change():
    """
    Tests that no announcement is made if the score has not changed.
    """
    # Arrange
    mock_match = Match(
        id=3,
        team1="Team A",
        team2="Team B",
        best_of=5,
        scheduled_time=datetime.now(timezone.utc) - timedelta(hours=1),
        last_announced_score="1-0",
        contest=Contest(leaguepedia_id="LPL/2025_Season/Spring_Season"),
    )
    mock_scoreboard_data = [{"Winner": "1"}]
    mock_session = AsyncMock()

    with patch("src.scheduler.get_async_session") as mock_get_async_session, \
         patch("src.scheduler.crud.get_match_with_result_by_id", new_callable=AsyncMock, return_value=mock_match) as mock_get_match, \
         patch("src.scheduler.leaguepedia_client.get_scoreboard_data", new_callable=AsyncMock, return_value=mock_scoreboard_data) as mock_get_scoreboard, \
         patch("src.scheduler.send_mid_series_update", new_callable=AsyncMock) as mock_send_update, \
         patch("src.scheduler.send_result_notification", new_callable=AsyncMock) as mock_send_result, \
         patch("src.scheduler.scheduler.remove_job") as mock_remove_job:

        mock_get_async_session.return_value.__aenter__.return_value = mock_session

        # Act
        await poll_live_match_job(match_db_id=3, guild_id=123)

        # Assert
        mock_get_match.assert_awaited_once_with(mock_session, 3)
        mock_get_scoreboard.assert_awaited_once_with("LPL/2025_Season/Spring_Season")
        mock_send_update.assert_not_called()
        mock_send_result.assert_not_called()
        mock_remove_job.assert_not_called()
        mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_poll_live_match_job_already_has_result():
    """
    Tests that the job unschedules itself if the match already has a result.
    """
    # Arrange
    mock_match = Match(
        id=4,
        team1="Team A",
        team2="Team B",
        best_of=3,
        scheduled_time=datetime.now(timezone.utc) - timedelta(hours=1),
        result=Result(winner="Team A", score="2-0"),
        contest=Contest(leaguepedia_id="LPL/2025_Season/Spring_Season"),
    )
    mock_session = AsyncMock()

    with patch("src.scheduler.get_async_session") as mock_get_async_session, \
         patch("src.scheduler.crud.get_match_with_result_by_id", new_callable=AsyncMock, return_value=mock_match) as mock_get_match, \
         patch("src.scheduler.leaguepedia_client.get_scoreboard_data", new_callable=AsyncMock) as mock_get_scoreboard, \
         patch("src.scheduler.scheduler.remove_job") as mock_remove_job:

        mock_get_async_session.return_value.__aenter__.return_value = mock_session

        # Act
        await poll_live_match_job(match_db_id=4, guild_id=123)

        # Assert
        mock_get_match.assert_awaited_once_with(mock_session, 4)
        mock_get_scoreboard.assert_not_called()
        mock_remove_job.assert_called_once()
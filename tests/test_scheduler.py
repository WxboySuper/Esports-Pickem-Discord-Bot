import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
from src.scheduler import schedule_match_reminders, send_reminder
from src.models import Match, Team
from contextlib import asynccontextmanager


@pytest.mark.asyncio
async def test_schedule_far_future_match():
    """
    Tests scheduling for a new match that is far in the future.
    Expects both 30-min and 5-min reminders to be scheduled.
    """
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.remove_job = MagicMock()

    with patch("src.scheduler.scheduler", mock_scheduler), patch(
        "src.scheduler.ANNOUNCEMENT_GUILD_ID", 12345
    ):

        now = datetime.now(timezone.utc)
        match_time = now + timedelta(days=1)
        match = Match(
            id=1,
            scheduled_time=match_time,
            team1="A",
            team2="B",
            leaguepedia_id="123",
            contest_id=1,
        )

        await schedule_match_reminders(match)

        # Check that remove_job was called for both potential old jobs
        mock_scheduler.remove_job.assert_has_calls(
            [
                call("reminder_30_1"),
                call("reminder_5_1"),
            ],
            any_order=True,
        )

        # Check that add_job was called correctly for both reminders
        mock_scheduler.add_job.assert_has_calls(
            [
                call(
                    send_reminder,
                    "date",
                    id="reminder_30_1",
                    run_date=match_time - timedelta(minutes=30),
                    args=[12345, 1, 30],
                ),
                call(
                    send_reminder,
                    "date",
                    id="reminder_5_1",
                    run_date=match_time - timedelta(minutes=5),
                    args=[12345, 1, 5],
                ),
            ],
            any_order=True,
        )
        assert mock_scheduler.add_job.call_count == 2


@pytest.mark.asyncio
async def test_schedule_late_30_min_reminder():
    """
    Tests scheduling for a match where the 30-min reminder time has passed,
    but the 5-min reminder is still in the future.
    Expects the 30-min reminder to be scheduled immediately and the 5-min
    reminder to be scheduled for its normal time.
    """
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.remove_job = MagicMock()

    with patch("src.scheduler.scheduler", mock_scheduler), patch(
        "src.scheduler.ANNOUNCEMENT_GUILD_ID", 12345
    ), patch("src.scheduler.datetime") as mock_dt:

        now = datetime.now(timezone.utc)
        mock_dt.now.return_value = now
        match_time = now + timedelta(
            minutes=20
        )  # 30-min reminder is 10 mins ago
        match = Match(
            id=2,
            scheduled_time=match_time,
            team1="C",
            team2="D",
            leaguepedia_id="456",
            contest_id=1,
        )

        await schedule_match_reminders(match)

        # Check that add_job was called correctly
        mock_scheduler.add_job.assert_has_calls(
            [
                call(
                    send_reminder,
                    "date",
                    id="reminder_30_2",
                    run_date=now,  # Should run immediately
                    args=[12345, 2, 30],
                ),
                call(
                    send_reminder,
                    "date",
                    id="reminder_5_2",
                    run_date=match_time
                    - timedelta(minutes=5),  # Should run at normal time
                    args=[12345, 2, 5],
                ),
            ],
            any_order=True,
        )
        assert mock_scheduler.add_job.call_count == 2


@pytest.mark.asyncio
async def test_schedule_late_5_min_reminder():
    """
    Tests scheduling for a match where both reminder times have passed.
    Expects only the 5-min reminder to be scheduled immediately.
    """
    mock_scheduler = MagicMock()
    mock_scheduler.add_job = MagicMock()
    mock_scheduler.remove_job = MagicMock()

    with patch("src.scheduler.scheduler", mock_scheduler), patch(
        "src.scheduler.ANNOUNCEMENT_GUILD_ID", 12345
    ), patch("src.scheduler.datetime") as mock_dt:

        now = datetime.now(timezone.utc)
        mock_dt.now.return_value = now
        match_time = now + timedelta(
            minutes=3
        )  # Both reminders are in the past
        match = Match(
            id=3,
            scheduled_time=match_time,
            team1="E",
            team2="F",
            leaguepedia_id="789",
            contest_id=1,
        )

        await schedule_match_reminders(match)

        # Check that only the 5-minute reminder is scheduled immediately
        mock_scheduler.add_job.assert_called_once_with(
            send_reminder,
            "date",
            id="reminder_5_3",
            run_date=now,
            args=[12345, 3, 5],
        )


@pytest.mark.asyncio
@patch("src.scheduler.get_bot_instance")
@patch("src.scheduler.get_async_session")
@patch("src.scheduler.send_announcement")
async def test_send_reminder_embed_content(
    mock_send_announcement, mock_get_session, mock_get_bot
):
    """
    Tests that send_reminder generates the correct embed content for both
    30-min and 5-min reminders.
    """
    # Mock bot and guild
    mock_bot = MagicMock()
    mock_guild = MagicMock()
    mock_bot.get_guild.return_value = mock_guild
    mock_get_bot.return_value = mock_bot

    # Mock session and DB objects
    now = datetime.now(timezone.utc)
    match_time = now + timedelta(hours=1)
    match = Match(
        id=1,
        scheduled_time=match_time,
        team1="Team Liquid",
        team2="100 Thieves",
        leaguepedia_id="1",
        contest_id=1,
    )
    team1 = MagicMock(spec=Team)
    team1.name = "Team Liquid"
    team1.image_url = "http://team_liquid.png"
    team2 = MagicMock(spec=Team)
    team2.name = "100 Thieves"
    team2.image_url = "http://100_thieves.png"

    mock_session = AsyncMock()
    # This setup mocks the behavior of `(await session.exec(stmt)).first()`
    mock_session.exec.side_effect = [
        MagicMock(first=lambda: team1),
        MagicMock(first=lambda: team2),
        MagicMock(first=lambda: team1),
        MagicMock(first=lambda: team2),
    ]
    mock_session.get.return_value = match

    @asynccontextmanager
    async def async_context_manager(*args, **kwargs):
        yield mock_session

    mock_get_session.return_value = async_context_manager()

    # Test 30-minute reminder
    await send_reminder(guild_id=123, match_id=1, minutes=30)

    # Check that send_announcement was called
    mock_send_announcement.assert_called_once()
    sent_embed = mock_send_announcement.call_args[0][1]

    assert "Upcoming Match Reminder" in sent_embed.title
    assert "Team Liquid" in sent_embed.description
    assert "100 Thieves" in sent_embed.description
    assert sent_embed.thumbnail.url == "http://team_liquid.png"

    # Reset mock for next call
    mock_send_announcement.reset_mock()
    mock_get_session.return_value = async_context_manager()

    # Test 5-minute reminder
    await send_reminder(guild_id=123, match_id=1, minutes=5)

    mock_send_announcement.assert_called_once()
    sent_embed = mock_send_announcement.call_args[0][1]

    assert "Match Starting Soon" in sent_embed.title
    assert "Last chance" in sent_embed.description

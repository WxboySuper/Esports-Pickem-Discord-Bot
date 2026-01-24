import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from src.reminders import schedule_reminders, send_reminder
from src.models import Match, Team
from contextlib import asynccontextmanager


@pytest.fixture(name="mock_scheduler")
def _scheduler_fixture_impl():
    m = MagicMock()
    m.add_job = MagicMock()
    m.remove_job = MagicMock()
    return m


async def _run_schedule(scheduler, now, match):
    """Helper to patch scheduler and datetime and run schedule_reminders."""
    with patch("src.reminders.scheduler", scheduler), patch(
        "src.reminders.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = now
        await schedule_reminders(match)


@pytest.mark.asyncio
async def test_schedule_far_future_match(mock_scheduler):
    """
    Tests scheduling for a new match that is far in the future.
    Expects both 30-min and 5-min reminders to be scheduled.
    """
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

    await _run_schedule(mock_scheduler, now, match)

    # Check that add_job was called correctly for all configured reminders
    actual = set()
    for call_obj in mock_scheduler.add_job.call_args_list:
        # call_obj can be a tuple (args, kwargs) or a mock call object
        if hasattr(call_obj, "kwargs"):
            kwargs = call_obj.kwargs
        else:
            kwargs = call_obj[1]
        id_ = kwargs.get("id")
        run_date = kwargs.get("run_date")
        args_t = tuple(kwargs.get("args", []))
        actual.add((id_, run_date, args_t))
    expected = {
        (
            "reminder_30_1",
            match_time - timedelta(minutes=30),
            (1, 30),
        ),
        (
            "reminder_5_1",
            match_time - timedelta(minutes=5),
            (1, 5),
        ),
        (
            "reminder_1440_1",
            now,
            (1, 1440),
        ),
    }
    missing = expected - actual
    if missing:
        raise AssertionError(f"missing expected add_job calls: {missing}")


@pytest.mark.asyncio
async def test_schedule_late_30_min_reminder(mock_scheduler):
    """
    Tests scheduling for a match where the 30-min reminder time has passed,
    but the 5-min reminder is still in the future.
    Expects the 30-min reminder to be scheduled immediately and the 5-min
    reminder to be scheduled for its normal time.
    """
    now = datetime.now(timezone.utc)
    match_time = now + timedelta(minutes=20)  # 30-min reminder is 10 mins ago
    match = Match(
        id=2,
        scheduled_time=match_time,
        team1="C",
        team2="D",
        leaguepedia_id="456",
        contest_id=1,
    )

    await _run_schedule(mock_scheduler, now, match)

    # Check that add_job was called correctly for expected reminders
    actual = set()
    for call_obj in mock_scheduler.add_job.call_args_list:
        if hasattr(call_obj, "kwargs"):
            kwargs = call_obj.kwargs
        else:
            kwargs = call_obj[1]
        id_ = kwargs.get("id")
        run_date = kwargs.get("run_date")
        args_t = tuple(kwargs.get("args", []))
        actual.add((id_, run_date, args_t))
    expected = {
        (
            "reminder_30_2",
            now,
            (2, 30),
        ),
        (
            "reminder_5_2",
            match_time - timedelta(minutes=5),
            (2, 5),
        ),
    }
    missing = expected - actual
    if missing:
        raise AssertionError(f"missing expected add_job calls: {missing}")


@pytest.mark.asyncio
async def test_schedule_late_5_min_reminder(mock_scheduler):
    """
    Tests scheduling for a match where both reminder times have passed.
    Expects only the 5-min reminder to be scheduled immediately.
    """
    now = datetime.now(timezone.utc)
    match_time = now + timedelta(minutes=3)  # Both reminders are in the past
    match = Match(
        id=3,
        scheduled_time=match_time,
        team1="E",
        team2="F",
        leaguepedia_id="789",
        contest_id=1,
    )

    await _run_schedule(mock_scheduler, now, match)

    # Check that only the 5-minute reminder is scheduled immediately
    call_count = mock_scheduler.add_job.call_count
    if call_count != 1:
        raise AssertionError(
            f"expected exactly 1 add_job call, got {call_count}"
        )

    call_obj = mock_scheduler.add_job.call_args_list[0]
    if hasattr(call_obj, "kwargs"):
        called_kwargs = call_obj.kwargs
    else:
        called_kwargs = call_obj[1]

    # Validate the call signature and ensure args are a tuple like other tests
    if (
        called_kwargs.get("id"),
        called_kwargs.get("run_date"),
        tuple(called_kwargs.get("args", [])),
    ) != ("reminder_5_3", now, (3, 5)):
        raise AssertionError(f"unexpected add_job call args: {call_obj}")


@pytest.mark.asyncio
@patch("src.reminders.batcher.add_reminder")
async def test_send_reminder_delegates_to_batcher(mock_batcher_add):
    """
    Verify that send_reminder delegates to batcher.add_reminder instead of
    broadcasting immediately.
    """
    match_id = 123
    minutes = 30

    await send_reminder(match_id, minutes)

    mock_batcher_add.assert_called_once_with(match_id, minutes)

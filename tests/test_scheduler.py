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


def _collect_title_desc_errors(
    obj, title_sub: str, desc_list: list[str]
) -> list[str]:
    errs: list[str] = []
    title = getattr(obj, "title", "") or ""
    if title_sub not in title:
        errs.append(f"embed title missing '{title_sub}'")
    description = getattr(obj, "description", "") or ""
    missing = [s for s in desc_list if s not in description]
    if missing:
        errs.append(f"embed description missing: {', '.join(missing)}")
    return errs


def _collect_thumbnail_error(obj, expected_url: str) -> list[str]:
    thumb = getattr(obj, "thumbnail", None)
    url = getattr(thumb, "url", None) if thumb is not None else None
    return ["unexpected thumbnail URL"] if url != expected_url else []


def _validate_embed(
    sent_embed,
    title_contains: str,
    desc_contains_list: list[str],
    thumbnail_url: str | None = None,
):
    errors = _collect_title_desc_errors(
        sent_embed, title_contains, desc_contains_list
    )
    if thumbnail_url is not None:
        errors += _collect_thumbnail_error(sent_embed, thumbnail_url)
    if errors:
        raise AssertionError("; ".join(errors))


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


def _prepare_send_reminder_mocks(mock_get_bot, mock_get_session, match):
    mock_bot = MagicMock()
    mock_guild = MagicMock()
    mock_bot.guilds = [mock_guild]
    mock_get_bot.return_value = mock_bot

    team1 = MagicMock(spec=Team)
    team1.name = "Team Liquid"
    team1.image_url = "http://team_liquid.png"
    team2 = MagicMock(spec=Team)
    team2.name = "100 Thieves"
    team2.image_url = "http://100_thieves.png"

    mock_session = AsyncMock()
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        (
            30,
            "Upcoming Match Reminder",
            ["Team Liquid", "100 Thieves"],
            "http://team_liquid.png",
        ),
        (
            5,
            "Match Starting Soon",
            ["Last chance"],
            None,
        ),
    ],
)
@patch("src.reminders.get_bot_instance")
@patch("src.reminders.get_async_session")
@patch("src.reminders.broadcast_embed_to_guilds")
async def test_send_reminder_embed_content(
    mock_broadcast, mock_get_session, mock_get_bot, case
):
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

    _prepare_send_reminder_mocks(mock_get_bot, mock_get_session, match)

    minutes, title, expected_desc, thumbnail = case

    await send_reminder(match_id=1, minutes=minutes)

    call_count = len(mock_broadcast.call_args_list)
    if call_count != 1:
        raise AssertionError(f"expected 1 broadcast call, got {call_count}")
    sent_embed = mock_broadcast.call_args[0][1]
    _validate_embed(sent_embed, title, expected_desc, thumbnail)

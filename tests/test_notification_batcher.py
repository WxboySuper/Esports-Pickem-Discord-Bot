import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from src.notification_batcher import NotificationBatcher
from src.models import Match, Contest


@pytest.mark.asyncio
async def test_batch_reminders():
    # Setup
    batcher = NotificationBatcher()

    # Mocks
    mock_bot = MagicMock()

    with patch(
        "src.notification_batcher.get_bot_instance", return_value=mock_bot
    ), patch(
        "src.notification_batcher.get_async_session"
    ) as mock_session_cls, patch(
        "src.notification_batcher.broadcast_embed_to_guilds",
        new_callable=AsyncMock,
    ) as mock_broadcast, patch(
        "src.notification_batcher.fetch_teams", new_callable=AsyncMock
    ) as mock_fetch_teams:

        # Setup session mock
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        # Mock data
        now = datetime.now(timezone.utc)
        contest = Contest(
            name="C1",
            image_url="http://example.com/icon.png",
            start_date=now,
            end_date=now,
        )
        match1 = Match(
            id=1,
            team1="Team A",
            team2="Team B",
            scheduled_time=now,
            contest_id=1,
        )
        match1.contest = contest
        match2 = Match(
            id=2,
            team1="Team C",
            team2="Team D",
            scheduled_time=now,
            contest_id=1,
        )
        match2.contest = contest

        # Mock _get_match_with_contest to avoid complex SQLModel mocking
        # We patch the method on the instance
        batcher._get_match_with_contest = AsyncMock(
            side_effect=[match1, match2]
        )
        mock_fetch_teams.return_value = (None, None)

        # Action: Add reminders
        await batcher.add_reminder(1, 5)
        await batcher.add_reminder(2, 5)

        # Verify pending list has items
        assert len(batcher._pending["reminder_5"]) == 2

        # Wait for debounce (flush is scheduled for 1.0s)
        await asyncio.sleep(1.1)

        # Verify
        # Should have called broadcast once
        assert mock_broadcast.call_count == 1

        args, kwargs = mock_broadcast.call_args
        embed = args[1]

        # Check embed content
        assert "Team A" in embed.description
        assert "Team C" in embed.description
        assert embed.thumbnail.url == "http://example.com/icon.png"
        assert "5-minute reminder" in args[2]


@pytest.mark.asyncio
async def test_batch_results():
    batcher = NotificationBatcher()
    mock_bot = MagicMock()

    with patch(
        "src.notification_batcher.get_bot_instance", return_value=mock_bot
    ), patch(
        "src.notification_batcher.get_async_session"
    ) as mock_session_cls, patch(
        "src.notification_batcher.broadcast_embed_to_guilds",
        new_callable=AsyncMock,
    ) as mock_broadcast, patch(
        "src.notification_batcher.fetch_teams", new_callable=AsyncMock
    ) as mock_fetch_teams, patch(
        "src.crud.get_match_with_result_by_id", new_callable=AsyncMock
    ) as mock_get_match:

        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        now = datetime.now(timezone.utc)
        contest = Contest(
            name="C1",
            image_url="http://example.com/icon.png",
            start_date=now,
            end_date=now,
        )
        match1 = Match(
            id=1, team1="A", team2="B", scheduled_time=now, contest_id=1
        )
        match1.contest = contest
        res1 = MagicMock(winner="A", score="2-0")

        match2 = Match(
            id=2, team1="C", team2="D", scheduled_time=now, contest_id=1
        )
        match2.contest = contest
        res2 = MagicMock(winner="D", score="1-2")

        mock_get_match.side_effect = [match1, match2]
        # mock session.get for Result
        mock_session.get.side_effect = [res1, res2]

        # Mock _get_pick_stats
        batcher._get_pick_stats = AsyncMock(return_value=(10, 5, 50.0))
        mock_fetch_teams.return_value = (None, None)

        await batcher.add_result(1, 101)
        await batcher.add_result(2, 102)

        await asyncio.sleep(1.1)

        assert mock_broadcast.call_count == 1
        args, _ = mock_broadcast.call_args
        embed = args[1]

        assert "A" in embed.fields[0].value
        assert "D" in embed.fields[1].value
        assert "🏆 Match Results" in embed.title

import pytest
from datetime import datetime, timezone, timedelta
from src.commands import sync_leaguepedia
from src.models import Match, Contest, Result
from src.commands.sync_leaguepedia import SyncContext
from tests.testing_utils import get_test_async_session, setup_test_db, teardown_test_db


@pytest.mark.asyncio
async def test_calculate_match_outcome_basic():
    # Simple scoreboard where TeamA wins 2-0 in a best_of=3
    match = type("M", (), {})()
    match.team1 = "TeamA"
    match.team2 = "TeamB"
    match.best_of = 3
    # Two games, both won by TeamA (Winner 1)
    scoreboard = [
        {"Team1": "TeamA", "Team2": "TeamB", "Winner": 1},
        {"Team1": "TeamA", "Team2": "TeamB", "Winner": 1},
    ]

    winner, score = sync_leaguepedia._calculate_match_outcome(scoreboard, match)
    assert winner == "TeamA"
    assert score == "2-0"


@pytest.mark.asyncio
async def test_persist_match_outcome_and_notifications():
    await setup_test_db()
    async with get_test_async_session() as session:
        # Create contest and match in DB
        contest = Contest(leaguepedia_id="c1", name="C", start_date=datetime.now(timezone.utc), end_date=(datetime.now(timezone.utc) + timedelta(days=1)))
        session.add(contest)
        await session.flush()
        await session.refresh(contest)

        match = Match(
            leaguepedia_id="m1",
            contest_id=contest.id,
            team1="TeamA",
            team2="TeamB",
            best_of=3,
            scheduled_time=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(match)
        await session.flush()
        await session.refresh(match)

        ctx = SyncContext(contest=contest, db_session=session, summary={"contests":0, "matches":0, "teams":0}, scoreboard=None)

        # Persist a result for the match
        result = await sync_leaguepedia._persist_match_outcome(ctx, match, "TeamA", "2-0")

        # Result should be created and queued in notifications
        assert result is not None
        assert len(ctx.notifications) == 1
        queued_match_id, queued_result_id = ctx.notifications[0]
        assert queued_match_id == match.id
        # Verify result exists in DB
        db_result = await session.get(Result, queued_result_id)
        assert db_result is not None
        assert db_result.winner == "TeamA"

    await teardown_test_db()


@pytest.mark.asyncio
async def test_detect_and_handle_result_errors_and_noop():
    await setup_test_db()
    async with get_test_async_session() as session:
        # Create contest and match
        contest = Contest(leaguepedia_id="c2", name="C2", start_date=datetime.now(timezone.utc), end_date=(datetime.now(timezone.utc) + timedelta(days=1)))
        session.add(contest)
        await session.flush()
        await session.refresh(contest)

        match = Match(
            leaguepedia_id="m2",
            contest_id=contest.id,
            team1="TeamX",
            team2="TeamY",
            best_of=3,
            scheduled_time=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(match)
        await session.flush()
        await session.refresh(match)

        # Case: empty scoreboard -> no action
        ctx = SyncContext(contest=contest, db_session=session, summary={}, scoreboard=[])
        res = await sync_leaguepedia._detect_and_handle_result(match, ctx, str(match.leaguepedia_id))
        assert res is None
        assert ctx.notifications == []

        # Case: scoreboard with no definitive winner -> no action
        scoreboard = [{"Team1": "TeamX", "Team2": "TeamY", "Winner": None}]
        ctx.scoreboard = scoreboard
        res = await sync_leaguepedia._detect_and_handle_result(match, ctx, str(match.leaguepedia_id))
        assert res is None
        assert ctx.notifications == []

        # Case: match disappears before persistence -> deletion simulates missing match
        # Prepare a scoreboard that would produce a winner
        scoreboard = [
            {"Team1": "TeamX", "Team2": "TeamY", "Winner": 1},
            {"Team1": "TeamX", "Team2": "TeamY", "Winner": 1},
        ]
        ctx.scoreboard = scoreboard

        # Delete the match before calling detection to simulate disappearance
        await session.delete(match)
        await session.flush()

        res = await sync_leaguepedia._detect_and_handle_result(match, ctx, str(match.leaguepedia_id))
        assert res is None
        assert ctx.notifications == []

    await teardown_test_db()

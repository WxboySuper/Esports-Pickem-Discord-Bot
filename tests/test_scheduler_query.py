import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models import Match, Result, Contest
from src.scheduler import _get_matches_starting_soon

# Use an in-memory SQLite database for testing
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_matches_starting_soon_query_no_result(session):
    """
    Verifies that _get_matches_starting_soon correctly retrieves matches
    that are starting soon and have NO result.
    This specifically tests the fix for the 'Match.result.is_(None)' issue
    by ensuring the query executes without error on a real (in-memory) DB.
    """
    # Create a dummy contest
    contest = Contest(
        leaguepedia_id="Test Contest",
        name="Test Contest",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.add(contest)
    await session.commit()
    await session.refresh(contest)

    # Create a match starting in 2 minutes (within the 5-minute window)
    now = datetime.now(timezone.utc)
    match_time = now + timedelta(minutes=2)

    match = Match(
        leaguepedia_id="Test Match 1",
        contest_id=contest.id,
        team1="Team A",
        team2="Team B",
        scheduled_time=match_time,
    )
    session.add(match)
    await session.commit()

    # Execute the function under test
    # This should NOT raise NotImplementedError or any other exception
    fetched_now, matches = await _get_matches_starting_soon(session)

    assert len(matches) == 1
    assert matches[0].id == match.id


@pytest.mark.asyncio
async def test_get_matches_starting_soon_query_with_result(session):
    """
    Verifies that matches WITH a result are NOT returned.
    """
    # Create a dummy contest
    contest = Contest(
        leaguepedia_id="Test Contest 2",
        name="Test Contest 2",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session.add(contest)
    await session.commit()
    await session.refresh(contest)

    # Create a match starting in 2 minutes
    now = datetime.now(timezone.utc)
    match_time = now + timedelta(minutes=2)

    match = Match(
        leaguepedia_id="Test Match 2",
        contest_id=contest.id,
        team1="Team C",
        team2="Team D",
        scheduled_time=match_time,
    )
    session.add(match)
    await session.commit()
    await session.refresh(match)

    # Add a result for this match
    result = Result(match_id=match.id, winner="Team C", score="2-0")
    session.add(result)
    await session.commit()

    # Execute the function under test
    fetched_now, matches = await _get_matches_starting_soon(session)

    # Should be empty because the match has a result
    assert len(matches) == 0

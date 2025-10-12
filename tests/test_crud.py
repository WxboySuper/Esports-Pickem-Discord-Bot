import pytest
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine
from src.models import User, Contest, Match, Pick, Result
from src import crud
from src.db import async_engine, get_async_session


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="async_session")
async def async_session_fixture():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with get_async_session() as session:
        yield session


# Helper to create a contest for tests that need one
async def _mk_contest(session: Session) -> Contest:
    return await crud.create_contest(
        session,
        name="Test Contest",
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 2, 1),
    )


# Helper to create a user, contest, and match
async def _mk_user_contest_match(session: Session) -> (User, Contest, Match):
    user = await crud.create_user(session, discord_id="u1", username="u1")
    contest = await _mk_contest(session)
    match = await crud.create_match(
        session,
        contest.id,
        "A",
        "B",
        scheduled_time=datetime(2025, 5, 12, 12, 0, 0),
    )
    return user, contest, match


@pytest.mark.asyncio
async def test_user_crud_happy_path(async_session: Session):
    # create
    user = await crud.create_user(
        async_session, discord_id="123", username="alice"
    )
    assert isinstance(user, User)
    assert user.discord_id == "123"
    assert user.username == "alice"

    # get
    got_user = await crud.get_user_by_discord_id(async_session, "123")
    assert got_user.id == user.id

    # update
    updated_user = await crud.update_user(
        async_session, user.id, username="alicia"
    )
    assert updated_user.username == "alicia"

    # delete
    assert await crud.delete_user(async_session, user.id)
    assert not await crud.get_user_by_discord_id(async_session, "123")


@pytest.mark.asyncio
async def test_user_update_delete_missing(async_session: Session):
    assert await crud.update_user(async_session, 9999, username="x") is None
    assert not await crud.delete_user(async_session, 9999)


@pytest.mark.asyncio
async def test_contest_crud_and_listing(async_session: Session):
    start = datetime(2025, 1, 1, 10, 0, 0)
    end = datetime(2025, 1, 10, 20, 0, 0)

    c1 = await crud.create_contest(
        async_session,
        name="Spring Split",
        start_date=start,
        end_date=end,
    )
    c2 = await crud.create_contest(
        async_session,
        name="Summer Split",
        start_date=start,
        end_date=end,
    )

    # get
    got = await crud.get_contest_by_id(async_session, c1.id)
    assert got.name == "Spring Split"

    # list
    contests = await crud.list_contests(async_session)
    assert len(contests) == 2

    # update
    updated = await crud.update_contest(
        async_session, c2.id, name="Summer Smash"
    )
    assert updated.name == "Summer Smash"

    # delete
    assert await crud.delete_contest(async_session, c1.id)
    assert len(await crud.list_contests(async_session)) == 1


@pytest.mark.asyncio
async def test_contest_update_delete_missing(async_session: Session):
    assert await crud.update_contest(async_session, 4242, name="X") is None
    assert not await crud.delete_contest(async_session, 4242)


@pytest.mark.asyncio
async def test_match_crud_and_queries(async_session: Session):
    contest = await _mk_contest(async_session)

    # Create matches across different times
    day = datetime(2025, 5, 10, tzinfo=timezone.utc)
    m1 = await crud.create_match(
        async_session, contest.id, "A", "B", scheduled_time=day
    )
    m2 = await crud.create_match(
        async_session,
        contest.id,
        "C",
        "D",
        scheduled_time=day + timezone.timedelta(hours=2),
    )
    await crud.create_match(
        async_session,
        contest.id,
        "E",
        "F",
        scheduled_time=day + timezone.timedelta(days=1),
    )

    # get by id
    assert (await crud.get_match_by_id(async_session, m1.id)).team1 == "A"

    # get by date
    matches_on_day = await crud.get_matches_by_date(async_session, day)
    assert len(matches_on_day) == 2
    assert {m.team1 for m in matches_on_day} == {"A", "C"}

    # list for contest
    all_for_contest = await crud.list_matches_for_contest(
        async_session, contest.id
    )
    assert len(all_for_contest) == 3

    # list all (sorted)
    all_matches = await crud.list_all_matches(async_session)
    assert len(all_matches) == 3
    assert all_matches[0].team1 == "E"  # Most recent first

    # update
    updated = await crud.update_match(async_session, m2.id, team1="Team C")
    assert updated.team1 == "Team C"

    # delete
    assert await crud.delete_match(async_session, m1.id)
    assert len(await crud.list_all_matches(async_session)) == 2


@pytest.mark.asyncio
async def test_match_update_delete_missing(async_session: Session):
    assert await crud.update_match(async_session, 5555, team1="GG") is None
    assert not await crud.delete_match(async_session, 5555)


@pytest.mark.asyncio
async def test_bulk_create_matches(async_session: Session):
    contest = await _mk_contest(async_session)
    matches_data = [
        {
            "contest_id": contest.id,
            "team1": "T1",
            "team2": "T2",
            "scheduled_time": datetime(2025, 5, 15, 12, 0, 0),
        },
        {
            "contest_id": contest.id,
            "team1": "T3",
            "team2": "T4",
            "scheduled_time": datetime(2025, 5, 16, 12, 0, 0),
        },
    ]
    created_matches = await crud.bulk_create_matches(
        async_session, matches_data
    )
    assert len(created_matches) == 2
    assert created_matches[0].team1 == "T1"

    all_matches = await crud.list_all_matches(async_session)
    assert len(all_matches) == 2


@pytest.mark.asyncio
async def test_pick_crud_and_queries_timestamp_default(async_session: Session):
    user, contest, match = await _mk_user_contest_match(async_session)

    # create
    pick = await crud.create_pick(
        async_session,
        user_id=user.id,
        contest_id=contest.id,
        match_id=match.id,
        chosen_team="A",
    )
    assert isinstance(pick, Pick)
    assert pick.chosen_team == "A"
    # Ensure timestamp is set automatically
    assert pick.timestamp is not None
    assert (
        datetime.now(timezone.utc) - pick.timestamp
    ).total_seconds() < 5  # recently created

    # get
    got_pick = await crud.get_pick_by_id(async_session, pick.id)
    assert got_pick.id == pick.id

    # list for user
    user_picks = await crud.list_picks_for_user(async_session, user.id)
    assert len(user_picks) == 1
    assert user_picks[0].id == pick.id

    # list for match
    match_picks = await crud.list_picks_for_match(async_session, match.id)
    assert len(match_picks) == 1

    # update
    updated = await crud.update_pick(async_session, pick.id, chosen_team="B")
    assert updated.chosen_team == "B"

    # delete
    assert await crud.delete_pick(async_session, pick.id)
    assert not await crud.get_pick_by_id(async_session, pick.id)


@pytest.mark.asyncio
async def test_pick_create_with_explicit_timestamp(async_session: Session):
    user, contest, match = await _mk_user_contest_match(async_session)
    ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    pick = await crud.create_pick(
        async_session,
        user_id=user.id,
        contest_id=contest.id,
        match_id=match.id,
        chosen_team="A",
        timestamp=ts,
    )
    assert pick.timestamp == ts


@pytest.mark.asyncio
async def test_pick_update_delete_missing(async_session: Session):
    assert await crud.update_pick(async_session, 7777, chosen_team="Z") is None
    assert not await crud.delete_pick(async_session, 7777)


@pytest.mark.asyncio
async def test_result_crud_and_queries(async_session: Session):
    contest = await _mk_contest(async_session)
    match = await crud.create_match(
        async_session,
        contest.id,
        "A",
        "B",
        scheduled_time=datetime(2025, 5, 20, 10, 0, 0),
    )

    # create
    result = await crud.create_result(
        async_session, match_id=match.id, winner="A"
    )
    assert isinstance(result, Result)
    assert result.winner == "A"

    # get by id
    got_result = await crud.get_result_by_id(async_session, result.id)
    assert got_result.id == result.id

    # get for match
    match_result = await crud.get_result_for_match(async_session, match.id)
    assert match_result.id == result.id

    # update
    updated = await crud.update_result(async_session, result.id, score="2-1")
    assert updated.score == "2-1"

    # delete
    assert await crud.delete_result(async_session, result.id)
    assert not await crud.get_result_for_match(async_session, match.id)


@pytest.mark.asyncio
async def test_result_update_delete_missing(async_session: Session):
    assert await crud.update_result(async_session, 8888, score="1-0") is None
    assert not await crud.delete_result(async_session, 8888)

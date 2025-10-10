import pytest
from datetime import datetime, timedelta, timezone

from sqlmodel import SQLModel, Session, create_engine

from src.models import User, Contest, Pick, Result
from src import crud


@pytest.fixture()
def session(tmp_path):
    """Provide a fresh SQLite database session for each test."""
    # Use a file-based SQLite DB under tmp_path so schema persists
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        try:
            yield s
        finally:
            engine.dispose()


# ---- USER ----
def test_user_crud_happy_path(session: Session):
    # create
    user = crud.create_user(session, discord_id="123", username="alice")
    assert isinstance(user, User)
    assert user.id is not None
    assert user.discord_id == "123"
    assert user.username == "alice"

    # get by discord id
    got = crud.get_user_by_discord_id(session, "123")
    assert got is not None and got.id == user.id

    # update
    updated = crud.update_user(session, user.id, username="alice_2")
    assert updated is not None and updated.username == "alice_2"

    # delete
    ok = crud.delete_user(session, user.id)
    assert ok is True
    assert crud.get_user_by_discord_id(session, "123") is None


def test_user_update_delete_missing(session: Session):
    assert crud.update_user(session, 9999, username="x") is None
    assert crud.delete_user(session, 9999) is False


# ---- CONTEST ----
def test_contest_crud_and_listing(session: Session):
    start = datetime(2025, 1, 1, 10, 0, 0)
    end = datetime(2025, 1, 10, 20, 0, 0)

    c1 = crud.create_contest(
        session,
        name="Spring Split",
        start_date=start,
        end_date=end,
    )
    c2 = crud.create_contest(
        session,
        name="Summer Split",
        start_date=start,
        end_date=end,
    )

    # get
    got = crud.get_contest_by_id(session, c1.id)
    assert got is not None and got.name == "Spring Split"

    # list
    contests = crud.list_contests(session)
    names = sorted(c.name for c in contests)
    assert names == ["Spring Split", "Summer Split"]

    # update
    upd = crud.update_contest(session, c2.id, name="Summer Finals")
    assert upd is not None and upd.name == "Summer Finals"

    # delete
    assert crud.delete_contest(session, c1.id) is True
    assert crud.get_contest_by_id(session, c1.id) is None


def test_contest_update_delete_missing(session: Session):
    assert crud.update_contest(session, 4242, name="X") is None
    assert crud.delete_contest(session, 4242) is False


# ---- MATCH ----
def _mk_contest(session: Session) -> Contest:
    return crud.create_contest(
        session,
        name="Main",
        start_date=datetime(2025, 5, 1, 0, 0, 0),
        end_date=datetime(2025, 5, 31, 23, 59, 59),
    )


def test_match_crud_and_queries(session: Session):
    contest = _mk_contest(session)

    # Create matches across different times
    day = datetime(2025, 5, 10, tzinfo=timezone.utc)
    m1 = crud.create_match(session, contest.id, "A", "B", scheduled_time=day)
    m2 = crud.create_match(
        session,
        contest.id,
        "C",
        "D",
        scheduled_time=day.replace(hour=23, minute=59, second=59),
    )
    m3 = crud.create_match(
        session,
        contest.id,
        "E",
        "F",
        scheduled_time=day + timedelta(days=1),
    )

    # get by id
    got = crud.get_match_by_id(session, m1.id)
    assert got is not None and got.team1 == "A"

    # list by contest
    in_contest = crud.list_matches_for_contest(session, contest.id)
    assert {m.id for m in in_contest} == {m1.id, m2.id, m3.id}

    # get by date
    on_day = crud.get_matches_by_date(session, day)
    assert {m.id for m in on_day} == {m1.id, m2.id}

    # update
    upd = crud.update_match(session, m1.id, team1="AA")
    assert upd is not None and upd.team1 == "AA"

    # delete
    assert crud.delete_match(session, m3.id) is True
    assert crud.get_match_by_id(session, m3.id) is None


def test_match_update_delete_missing(session: Session):
    assert crud.update_match(session, 5555, team1="GG") is None
    assert crud.delete_match(session, 5555) is False


def test_bulk_create_matches(session: Session):
    contest = _mk_contest(session)
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

    created_matches = crud.bulk_create_matches(session, matches_data)
    assert len(created_matches) == 2

    db_matches = crud.list_matches_for_contest(session, contest.id)
    assert len(db_matches) == 2
    assert {m.team1 for m in db_matches} == {"T1", "T3"}


# ---- PICK ----
def _mk_user_contest_match(session: Session):
    user = crud.create_user(session, discord_id="u1", username="u1")
    contest = _mk_contest(session)
    match = crud.create_match(
        session,
        contest.id,
        "A",
        "B",
        scheduled_time=datetime(2025, 5, 12, 12, 0, 0),
    )
    return user, contest, match


def test_pick_crud_and_queries_timestamp_default(session: Session):
    user, contest, match = _mk_user_contest_match(session)

    # create (no timestamp provided -> default_factory should set aware UTC)
    pick = crud.create_pick(
        session,
        user.id,
        contest.id,
        match.id,
        chosen_team="A",
    )
    assert isinstance(pick, Pick)
    assert pick.id is not None
    assert pick.timestamp.tzinfo is not None

    # get by id
    got = crud.get_pick_by_id(session, pick.id)
    assert got is not None and got.chosen_team == "A"

    # list for user/match
    assert [p.id for p in crud.list_picks_for_user(session, user.id)] == [
        pick.id
    ]
    assert [p.id for p in crud.list_picks_for_match(session, match.id)] == [
        pick.id
    ]

    # update
    upd = crud.update_pick(session, pick.id, chosen_team="B")
    assert upd is not None and upd.chosen_team == "B"

    # delete
    assert crud.delete_pick(session, pick.id) is True
    assert crud.get_pick_by_id(session, pick.id) is None


def test_pick_create_with_explicit_timestamp(session: Session):
    user, contest, match = _mk_user_contest_match(session)
    ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    pick = crud.create_pick(
        session,
        user.id,
        contest.id,
        match.id,
        chosen_team="A",
        timestamp=ts,
    )
    assert pick.timestamp == ts


def test_pick_update_delete_missing(session: Session):
    assert crud.update_pick(session, 7777, chosen_team="Z") is None
    assert crud.delete_pick(session, 7777) is False


# ---- RESULT ----
def test_result_crud_and_queries(session: Session):
    contest = _mk_contest(session)
    match = crud.create_match(
        session,
        contest.id,
        "A",
        "B",
        scheduled_time=datetime(2025, 5, 20, 10, 0, 0),
    )

    # create
    res = crud.create_result(session, match.id, winner="A", score="2-0")
    assert isinstance(res, Result)
    assert res.id is not None and res.winner == "A"

    # get by id
    got = crud.get_result_by_id(session, res.id)
    assert got is not None and got.score == "2-0"

    # get for match
    got_match = crud.get_result_for_match(session, match.id)
    assert got_match is not None and got_match.id == res.id

    # update
    upd = crud.update_result(session, res.id, score="2-1")
    assert upd is not None and upd.score == "2-1"

    # delete
    assert crud.delete_result(session, res.id) is True
    assert crud.get_result_by_id(session, res.id) is None


def test_result_update_delete_missing(session: Session):
    assert crud.update_result(session, 8888, score="1-0") is None
    assert crud.delete_result(session, 8888) is False

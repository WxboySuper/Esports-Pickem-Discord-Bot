from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from src.models import User, Contest, Match, Pick, Result
from datetime import datetime, timezone


# ---- USER ----
async def create_user(
    session: AsyncSession,
    discord_id: str,
    username: Optional[str] = None,
) -> User:
    user = User(discord_id=discord_id, username=username)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_discord_id(
    session: AsyncSession,
    discord_id: str,
) -> Optional[User]:
    statement = select(User).where(User.discord_id == discord_id)
    result = await session.exec(statement)
    return result.first()


async def update_user(
    session: AsyncSession, user_id: int, username: Optional[str] = None
) -> Optional[User]:
    user = await session.get(User, user_id)
    if not user:
        return None
    if username is not None:
        user.username = username
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False
    await session.delete(user)
    await session.commit()
    return True


# ---- CONTEST ----
async def create_contest(
    session: AsyncSession,
    name: str,
    start_date: datetime,
    end_date: datetime,
) -> Contest:
    contest = Contest(name=name, start_date=start_date, end_date=end_date)
    session.add(contest)
    await session.commit()
    await session.refresh(contest)
    return contest


async def get_contest_by_id(
    session: AsyncSession, contest_id: int
) -> Optional[Contest]:
    return await session.get(Contest, contest_id)


async def list_contests(session: AsyncSession) -> List[Contest]:
    result = await session.exec(select(Contest))
    return list(result.all())


async def update_contest(
    session: AsyncSession,
    contest_id: int,
    name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Optional[Contest]:
    contest = await session.get(Contest, contest_id)
    if not contest:
        return None
    if name is not None:
        contest.name = name
    if start_date is not None:
        contest.start_date = start_date
    if end_date is not None:
        contest.end_date = end_date
    session.add(contest)
    await session.commit()
    await session.refresh(contest)
    return contest


async def delete_contest(session: AsyncSession, contest_id: int) -> bool:
    contest = await session.get(Contest, contest_id)
    if not contest:
        return False
    await session.delete(contest)
    await session.commit()
    return True


# ---- MATCH ----
async def create_match(
    session: AsyncSession,
    contest_id: int,
    team1: str,
    team2: str,
    scheduled_time: datetime,
) -> Match:
    match = Match(
        contest_id=contest_id,
        team1=team1,
        team2=team2,
        scheduled_time=scheduled_time,
    )
    session.add(match)
    await session.commit()
    await session.refresh(match)
    return match


async def bulk_create_matches(
    session: AsyncSession, matches_data: List[dict]
) -> List[Match]:
    """Bulk creates matches from a list of dicts."""
    matches = [Match(**data) for data in matches_data]
    session.add_all(matches)
    await session.commit()
    for match in matches:
        await session.refresh(match)
    return matches


async def get_matches_by_date(
    session: AsyncSession, date: datetime
) -> List[Match]:
    start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
    end = datetime(
        date.year, date.month, date.day, 23, 59, 59, tzinfo=timezone.utc
    )
    result = await session.exec(
        select(Match).where(
            (Match.scheduled_time >= start) & (Match.scheduled_time <= end)
        )
    )
    return list(result.all())


async def list_matches_for_contest(
    session: AsyncSession, contest_id: int
) -> List[Match]:
    stmt = select(Match).where(Match.contest_id == contest_id)
    result = await session.exec(stmt)
    return list(result.all())


async def get_match_by_id(
    session: AsyncSession, match_id: int
) -> Optional[Match]:
    return await session.get(Match, match_id)


async def list_all_matches(session: AsyncSession) -> List[Match]:
    """Returns all matches, sorted by most recent first."""
    result = await session.exec(
        select(Match).order_by(Match.scheduled_time.desc())
    )
    return list(result.all())


async def update_match(
    session: AsyncSession,
    match_id: int,
    team1: Optional[str] = None,
    team2: Optional[str] = None,
    scheduled_time: Optional[datetime] = None,
) -> Optional[Match]:
    match = await session.get(Match, match_id)
    if not match:
        return None
    if team1 is not None:
        match.team1 = team1
    if team2 is not None:
        match.team2 = team2
    if scheduled_time is not None:
        match.scheduled_time = scheduled_time
    session.add(match)
    await session.commit()
    await session.refresh(match)
    return match


async def delete_match(session: AsyncSession, match_id: int) -> bool:
    match = await session.get(Match, match_id)
    if not match:
        return False
    await session.delete(match)
    await session.commit()
    return True


# ---- PICK ----
async def create_pick(
    session: AsyncSession,
    user_id: int,
    contest_id: int,
    match_id: int,
    chosen_team: str,
    timestamp: Optional[datetime] = None,
) -> Pick:
    pick_args = dict(
        user_id=user_id,
        contest_id=contest_id,
        match_id=match_id,
        chosen_team=chosen_team,
    )
    if timestamp is not None:
        pick_args["timestamp"] = timestamp
    pick = Pick(**pick_args)
    session.add(pick)
    await session.commit()
    await session.refresh(pick)
    return pick


async def get_pick_by_id(
    session: AsyncSession, pick_id: int
) -> Optional[Pick]:
    return await session.get(Pick, pick_id)


async def list_picks_for_user(
    session: AsyncSession, user_id: int
) -> List[Pick]:
    statement = select(Pick).where(Pick.user_id == user_id)
    result = await session.exec(statement)
    return list(result.all())


async def list_picks_for_match(
    session: AsyncSession, match_id: int
) -> List[Pick]:
    statement = select(Pick).where(Pick.match_id == match_id)
    result = await session.exec(statement)
    return list(result.all())


async def update_pick(
    session: AsyncSession, pick_id: int, chosen_team: Optional[str] = None
) -> Optional[Pick]:
    pick = await session.get(Pick, pick_id)
    if not pick:
        return None
    if chosen_team is not None:
        pick.chosen_team = chosen_team
    session.add(pick)
    await session.commit()
    await session.refresh(pick)
    return pick


async def delete_pick(session: AsyncSession, pick_id: int) -> bool:
    pick = await session.get(Pick, pick_id)
    if not pick:
        return False
    await session.delete(pick)
    await session.commit()
    return True


# ---- RESULT ----
async def create_result(
    session: AsyncSession,
    match_id: int,
    winner: str,
    score: Optional[str] = None,
) -> Result:
    result = Result(match_id=match_id, winner=winner, score=score)
    session.add(result)
    await session.commit()
    await session.refresh(result)
    return result


async def get_result_by_id(
    session: AsyncSession, result_id: int
) -> Optional[Result]:
    return await session.get(Result, result_id)


async def get_result_for_match(
    session: AsyncSession, match_id: int
) -> Optional[Result]:
    stmt = select(Result).where(Result.match_id == match_id)
    result = await session.exec(stmt)
    return result.first()


async def update_result(
    session: AsyncSession,
    result_id: int,
    winner: Optional[str] = None,
    score: Optional[str] = None,
) -> Optional[Result]:
    result = await session.get(Result, result_id)
    if not result:
        return None
    if winner is not None:
        result.winner = winner
    if score is not None:
        result.score = score
    session.add(result)
    await session.commit()
    await session.refresh(result)
    return result


async def delete_result(session: AsyncSession, result_id: int) -> bool:
    result = await session.get(Result, result_id)
    if not result:
        return False
    await session.delete(result)
    await session.commit()
    return True

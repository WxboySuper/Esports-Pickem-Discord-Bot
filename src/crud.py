import logging
from typing import List, Optional
from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models import User, Contest, Match, Pick, Result, Team
from datetime import datetime, timezone


async def upsert_team(
    session: AsyncSession, team_data: dict
) -> Optional[Team]:
    """Creates or updates a team based on leaguepedia_id."""
    try:
        existing_team = await session.exec(
            select(Team).where(
                Team.leaguepedia_id == team_data["leaguepedia_id"]
            )
        )
        team = existing_team.first()

        if team:
            team.name = team_data["name"]
            team.image_url = team_data.get("image_url")
            team.roster = team_data.get("roster")
        else:
            team = Team(**team_data)

        session.add(team)
        return team
    except KeyError as e:
        logging.error(f"Missing key in team_data: {e}")
        return None


async def upsert_contest(
    session: AsyncSession, contest_data: dict
) -> Optional[Contest]:
    """Creates or updates a contest based on leaguepedia_id."""
    try:
        existing_contest = await session.exec(
            select(Contest).where(
                Contest.leaguepedia_id == contest_data["leaguepedia_id"]
            )
        )
        contest = existing_contest.first()

        if contest:
            contest.name = contest_data["name"]
            contest.start_date = contest_data["start_date"]
            contest.end_date = contest_data["end_date"]
        else:
            contest = Contest(**contest_data)

        session.add(contest)
        return contest
    except KeyError as e:
        logging.error(f"Missing key in contest_data: {e}")
        return None


async def upsert_match(
    session: AsyncSession, match_data: dict
) -> tuple[Optional[Match], bool]:
    """
    Creates or updates a match based on leaguepedia_id.

    Returns the match object and a boolean indicating if the time changed.
    """
    try:
        existing_match = await session.exec(
            select(Match).where(
                Match.leaguepedia_id == match_data["leaguepedia_id"]
            )
        )
        match = existing_match.first()

        if match:
            # Update existing match
            match.team1 = match_data["team1"]
            match.team2 = match_data["team2"]
            match.best_of = match_data.get("best_of")
            original_time = match.scheduled_time
            new_time = match_data["scheduled_time"]
            match.scheduled_time = new_time
            time_changed = original_time != new_time
        else:
            # Create new match
            match = Match(**match_data)
            time_changed = True  # It's a new match, so schedule it

        session.add(match)
        await session.flush()  # Flush to get the match.id if it's new
        await session.refresh(match)

        return match, time_changed
    except KeyError as e:
        logging.error(f"Missing key in match_data: {e}")
        return None, False


# ---- USER ----
def create_user(
    session: Session,
    discord_id: str,
    username: Optional[str] = None,
) -> User:
    user = User(discord_id=discord_id, username=username)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_discord_id(
    session: Session,
    discord_id: str,
) -> Optional[User]:
    statement = select(User).where(User.discord_id == discord_id)
    return session.exec(statement).first()


def update_user(
    session: Session, user_id: int, username: Optional[str] = None
) -> Optional[User]:
    user = session.get(User, user_id)
    if not user:
        return None
    if username is not None:
        user.username = username
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, user_id: int) -> bool:
    user = session.get(User, user_id)
    if not user:
        return False
    session.delete(user)
    session.commit()
    return True


# ---- CONTEST ----
def create_contest(
    session: Session,
    name: str,
    start_date: datetime,
    end_date: datetime,
    leaguepedia_id: str,
) -> Contest:
    contest = Contest(
        name=name,
        start_date=start_date,
        end_date=end_date,
        leaguepedia_id=leaguepedia_id,
    )
    session.add(contest)
    session.commit()
    session.refresh(contest)
    return contest


def get_contest_by_id(session: Session, contest_id: int) -> Optional[Contest]:
    return session.get(Contest, contest_id)


def list_contests(session: Session) -> List[Contest]:
    return list(session.exec(select(Contest)))


def update_contest(
    session: Session,
    contest_id: int,
    name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Optional[Contest]:
    contest = session.get(Contest, contest_id)
    if not contest:
        return None
    if name is not None:
        contest.name = name
    if start_date is not None:
        contest.start_date = start_date
    if end_date is not None:
        contest.end_date = end_date
    session.add(contest)
    session.commit()
    session.refresh(contest)
    return contest


def delete_contest(session: Session, contest_id: int) -> bool:
    contest = session.get(Contest, contest_id)
    if not contest:
        return False
    session.delete(contest)
    session.commit()
    return True


# ---- MATCH ----
def create_match(
    session: Session,
    contest_id: int,
    team1: str,
    team2: str,
    scheduled_time: datetime,
    leaguepedia_id: str,
) -> Match:
    match = Match(
        contest_id=contest_id,
        team1=team1,
        team2=team2,
        scheduled_time=scheduled_time,
        leaguepedia_id=leaguepedia_id,
    )
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def bulk_create_matches(
    session: Session, matches_data: List[dict]
) -> List[Match]:
    """Bulk creates matches from a list of dicts."""
    matches = [Match(**data) for data in matches_data]
    session.add_all(matches)
    session.commit()
    for match in matches:
        session.refresh(match)
    return matches


def get_matches_by_date(session: Session, date: datetime) -> List[Match]:
    # Assumes 'date' is the day, returns matches scheduled on that date
    start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
    end = datetime(
        date.year, date.month, date.day, 23, 59, 59, tzinfo=timezone.utc
    )
    statement = (
        select(Match)
        .where(Match.scheduled_time >= start)
        .where(Match.scheduled_time <= end)
        .where(Match.team1 != "TBD")
        .where(Match.team2 != "TBD")
    )
    return list(session.exec(statement))


def list_matches_for_contest(session: Session, contest_id: int) -> List[Match]:
    # split into two statements
    # to keep line length < 79 chars
    stmt = (
        select(Match)
        .where(Match.contest_id == contest_id)
        .where(Match.team1 != "TBD")
        .where(Match.team2 != "TBD")
    )
    return list(session.exec(stmt))


from sqlalchemy.orm import selectinload


async def get_match_with_result_by_id(
    session: AsyncSession, match_id: int
) -> Optional[Match]:
    """
    Fetches a match by its ID, eagerly loading the related result.
    """
    result = await session.exec(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.result))
    )
    return result.first()


def get_match_by_id(session: Session, match_id: int) -> Optional[Match]:
    return session.get(Match, match_id)


def list_all_matches(session: Session) -> List[Match]:
    """Returns all matches, sorted by most recent first."""
    return list(
        session.exec(select(Match).order_by(Match.scheduled_time.desc()))
    )


def update_match(
    session: Session,
    match_id: int,
    team1: Optional[str] = None,
    team2: Optional[str] = None,
    scheduled_time: Optional[datetime] = None,
) -> Optional[Match]:
    match = session.get(Match, match_id)
    if not match:
        return None
    if team1 is not None:
        match.team1 = team1
    if team2 is not None:
        match.team2 = team2
    if scheduled_time is not None:
        match.scheduled_time = scheduled_time
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def delete_match(session: Session, match_id: int) -> bool:
    match = session.get(Match, match_id)
    if not match:
        return False
    session.delete(match)
    session.commit()
    return True


# ---- PICK ----
def create_pick(
    session: Session,
    user_id: int,
    contest_id: int,
    match_id: int,
    chosen_team: str,
    timestamp: Optional[datetime] = None,
) -> Pick:
    # Only pass timestamp if provided; otherwise allow default_factory
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
    session.commit()
    session.refresh(pick)
    return pick


def get_pick_by_id(session: Session, pick_id: int) -> Optional[Pick]:
    return session.get(Pick, pick_id)


def list_picks_for_user(session: Session, user_id: int) -> List[Pick]:
    statement = select(Pick).where(Pick.user_id == user_id)
    return list(session.exec(statement))


def list_picks_for_match(session: Session, match_id: int) -> List[Pick]:
    statement = select(Pick).where(Pick.match_id == match_id)
    return list(session.exec(statement))


def update_pick(
    session: Session, pick_id: int, chosen_team: Optional[str] = None
) -> Optional[Pick]:
    pick = session.get(Pick, pick_id)
    if not pick:
        return None
    if chosen_team is not None:
        pick.chosen_team = chosen_team
    session.add(pick)
    session.commit()
    session.refresh(pick)
    return pick


def delete_pick(session: Session, pick_id: int) -> bool:
    pick = session.get(Pick, pick_id)
    if not pick:
        return False
    session.delete(pick)
    session.commit()
    return True


# ---- RESULT ----
def create_result(
    session: Session,
    match_id: int,
    winner: str,
    score: Optional[str] = None,
) -> Result:
    result = Result(match_id=match_id, winner=winner, score=score)
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def get_result_by_id(session: Session, result_id: int) -> Optional[Result]:
    return session.get(Result, result_id)


def get_result_for_match(session: Session, match_id: int) -> Optional[Result]:
    # split into two statements to keep line length < 79 chars
    stmt = select(Result).where(Result.match_id == match_id)
    return session.exec(stmt).first()


def update_result(
    session: Session,
    result_id: int,
    winner: Optional[str] = None,
    score: Optional[str] = None,
) -> Optional[Result]:
    result = session.get(Result, result_id)
    if not result:
        return None
    if winner is not None:
        result.winner = winner
    if score is not None:
        result.score = score
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def delete_result(session: Session, result_id: int) -> bool:
    result = session.get(Result, result_id)
    if not result:
        return False
    session.delete(result)
    session.commit()
    return True

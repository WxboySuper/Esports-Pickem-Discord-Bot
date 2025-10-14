import logging
from typing import List, Optional
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models import User, Contest, Match, Pick, Result, Team
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def upsert_team(
    session: AsyncSession, team_data: dict
) -> Optional[Team]:
    """Creates or updates a team based on leaguepedia_id."""
    leaguepedia_id = team_data.get("leaguepedia_id")
    if not leaguepedia_id:
        logger.error("Missing leaguepedia_id in team_data")
        return None

    try:
        existing_team = await session.exec(
            select(Team).where(Team.leaguepedia_id == leaguepedia_id)
        )
        team = existing_team.first()

        if team:
            logger.info(f"Updating existing team: {team.name}")
            team.name = team_data["name"]
            team.image_url = team_data.get("image_url")
            team.roster = team_data.get("roster")
        else:
            logger.info(f"Creating new team: {team_data.get('name')}")
            team = Team(**team_data)

        session.add(team)
        await session.flush()
        logger.info(f"Upserted team: {team.name} (ID: {team.id})")
        return team
    except KeyError as e:
        logger.error(f"Missing key in team_data: {e}")
        return None
    except Exception:
        logger.exception(f"Error upserting team with data: {team_data}")
        return None


async def upsert_contest(
    session: AsyncSession, contest_data: dict
) -> Optional[Contest]:
    """Creates or updates a contest based on leaguepedia_id."""
    leaguepedia_id = contest_data.get("leaguepedia_id")
    if not leaguepedia_id:
        logger.error("Missing leaguepedia_id in contest_data")
        return None

    try:
        existing_contest = await session.exec(
            select(Contest).where(Contest.leaguepedia_id == leaguepedia_id)
        )
        contest = existing_contest.first()

        if contest:
            logger.info(f"Updating existing contest: {contest.name}")
            contest.name = contest_data["name"]
            contest.start_date = contest_data["start_date"]
            contest.end_date = contest_data["end_date"]
        else:
            logger.info(f"Creating new contest: {contest_data.get('name')}")
            contest = Contest(**contest_data)

        session.add(contest)
        await session.flush()
        logger.info(f"Upserted contest: {contest.name} (ID: {contest.id})")
        return contest
    except KeyError as e:
        logger.error(f"Missing key in contest_data: {e}")
        return None
    except Exception:
        logger.exception(f"Error upserting contest with data: {contest_data}")
        return None


async def upsert_match(
    session: AsyncSession, match_data: dict
) -> tuple[Optional[Match], bool]:
    """
    Creates or updates a match based on leaguepedia_id.

    Returns the match object and a boolean indicating if the time changed.
    """
    leaguepedia_id = match_data.get("leaguepedia_id")
    if not leaguepedia_id:
        logger.error("Missing leaguepedia_id in match_data")
        return None, False

    try:
        existing_match = await session.exec(
            select(Match).where(Match.leaguepedia_id == leaguepedia_id)
        )
        match = existing_match.first()
        time_changed = False

        if match:
            # Update existing match
            logger.info(f"Updating existing match ID: {match.id}")
            match.team1 = match_data["team1"]
            match.team2 = match_data["team2"]
            match.best_of = match_data.get("best_of")
            original_time = match.scheduled_time
            new_time = match_data["scheduled_time"]
            if original_time != new_time:
                logger.info(
                    f"Match {match.id} time changed from {original_time} "
                    f"to {new_time}"
                )
                time_changed = True
            match.scheduled_time = new_time
        else:
            # Create new match
            logger.info(f"Creating new match: {match_data}")
            match = Match(**match_data)
            time_changed = True  # It's a new match, so schedule it

        session.add(match)
        await session.flush()  # Flush to get the match.id if it's new
        await session.refresh(match)
        logger.info(f"Upserted match ID: {match.id}")

        return match, time_changed
    except KeyError as e:
        logger.error(f"Missing key in match_data: {e}")
        return None, False
    except Exception:
        logger.exception(f"Error upserting match with data: {match_data}")
        return None, False


# ---- USER ----
def create_user(
    session: Session,
    discord_id: str,
    username: Optional[str] = None,
) -> User:
    logger.info(f"Creating user: {username} ({discord_id})")
    user = User(discord_id=discord_id, username=username)
    session.add(user)
    session.commit()
    session.refresh(user)
    logger.info(f"Created user with ID: {user.id}")
    return user


def get_user_by_discord_id(
    session: Session,
    discord_id: str,
) -> Optional[User]:
    logger.debug(f"Fetching user by discord_id: {discord_id}")
    statement = select(User).where(User.discord_id == discord_id)
    return session.exec(statement).first()


def update_user(
    session: Session, user_id: int, username: Optional[str] = None
) -> Optional[User]:
    logger.info(f"Updating user ID: {user_id}")
    user = session.get(User, user_id)
    if not user:
        logger.warning(f"User with ID {user_id} not found for update.")
        return None
    if username is not None:
        user.username = username
    session.add(user)
    session.commit()
    session.refresh(user)
    logger.info(f"Updated user ID: {user_id}")
    return user


def delete_user(session: Session, user_id: int) -> bool:
    logger.info(f"Deleting user ID: {user_id}")
    user = session.get(User, user_id)
    if not user:
        logger.warning(f"User with ID {user_id} not found for deletion.")
        return False
    session.delete(user)
    session.commit()
    logger.info(f"Deleted user ID: {user_id}")
    return True


# ---- CONTEST ----
def create_contest(
    session: Session,
    name: str,
    start_date: datetime,
    end_date: datetime,
    leaguepedia_id: str,
) -> Contest:
    logger.info(f"Creating contest: {name}")
    contest = Contest(
        name=name,
        start_date=start_date,
        end_date=end_date,
        leaguepedia_id=leaguepedia_id,
    )
    session.add(contest)
    session.commit()
    session.refresh(contest)
    logger.info(f"Created contest with ID: {contest.id}")
    return contest


def get_contest_by_id(session: Session, contest_id: int) -> Optional[Contest]:
    logger.debug(f"Fetching contest by ID: {contest_id}")
    return session.get(Contest, contest_id)


def list_contests(session: Session) -> List[Contest]:
    logger.debug("Listing all contests")
    return list(session.exec(select(Contest)))


def update_contest(
    session: Session,
    contest_id: int,
    name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Optional[Contest]:
    logger.info(f"Updating contest ID: {contest_id}")
    contest = session.get(Contest, contest_id)
    if not contest:
        logger.warning(f"Contest with ID {contest_id} not found for update.")
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
    logger.info(f"Updated contest ID: {contest_id}")
    return contest


def delete_contest(session: Session, contest_id: int) -> bool:
    logger.info(f"Deleting contest ID: {contest_id}")
    contest = session.get(Contest, contest_id)
    if not contest:
        logger.warning(f"Contest with ID {contest_id} not found for deletion.")
        return False
    session.delete(contest)
    session.commit()
    logger.info(f"Deleted contest ID: {contest_id}")
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
    logger.info(f"Creating match: {team1} vs {team2} for contest {contest_id}")
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
    logger.info(f"Created match with ID: {match.id}")
    return match


def bulk_create_matches(
    session: Session, matches_data: List[dict]
) -> List[Match]:
    """Bulk creates matches from a list of dicts."""
    logger.info(f"Bulk creating {len(matches_data)} matches")
    matches = [Match(**data) for data in matches_data]
    session.add_all(matches)
    session.commit()
    for match in matches:
        session.refresh(match)
    logger.info("Bulk created matches.")
    return matches


def get_matches_by_date(session: Session, date: datetime) -> List[Match]:
    logger.debug(f"Fetching matches for date: {date.strftime('%Y-%m-%d')}")
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
    logger.debug(f"Listing matches for contest ID: {contest_id}")
    stmt = (
        select(Match)
        .where(Match.contest_id == contest_id)
        .where(Match.team1 != "TBD")
        .where(Match.team2 != "TBD")
    )
    return list(session.exec(stmt))


async def get_match_with_result_by_id(
    session: AsyncSession, match_id: int
) -> Optional[Match]:
    """
    Fetches a match by its ID, eagerly loading the related result and contest.
    """
    logger.debug(f"Fetching match with result by ID: {match_id}")
    result = await session.exec(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.result), selectinload(Match.contest))
    )
    return result.first()


def get_match_by_id(session: Session, match_id: int) -> Optional[Match]:
    logger.debug(f"Fetching match by ID: {match_id}")
    return session.get(Match, match_id)


def list_all_matches(session: Session) -> List[Match]:
    """Returns all matches, sorted by most recent first."""
    logger.debug("Listing all matches")
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
    logger.info(f"Updating match ID: {match_id}")
    match = session.get(Match, match_id)
    if not match:
        logger.warning(f"Match with ID {match_id} not found for update.")
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
    logger.info(f"Updated match ID: {match_id}")
    return match


def delete_match(session: Session, match_id: int) -> bool:
    logger.info(f"Deleting match ID: {match_id}")
    match = session.get(Match, match_id)
    if not match:
        logger.warning(f"Match with ID {match_id} not found for deletion.")
        return False
    session.delete(match)
    session.commit()
    logger.info(f"Deleted match ID: {match_id}")
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
    logger.info(
        f"Creating pick for user {user_id}, match {match_id}, "
        f"team {chosen_team}"
    )
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
    logger.info(f"Created pick with ID: {pick.id}")
    return pick


def get_pick_by_id(session: Session, pick_id: int) -> Optional[Pick]:
    logger.debug(f"Fetching pick by ID: {pick_id}")
    return session.get(Pick, pick_id)


def list_picks_for_user(session: Session, user_id: int) -> List[Pick]:
    logger.debug(f"Listing picks for user ID: {user_id}")
    statement = select(Pick).where(Pick.user_id == user_id)
    return list(session.exec(statement))


def list_picks_for_match(session: Session, match_id: int) -> List[Pick]:
    logger.debug(f"Listing picks for match ID: {match_id}")
    statement = select(Pick).where(Pick.match_id == match_id)
    return list(session.exec(statement))


def update_pick(
    session: Session, pick_id: int, chosen_team: Optional[str] = None
) -> Optional[Pick]:
    logger.info(f"Updating pick ID: {pick_id}")
    pick = session.get(Pick, pick_id)
    if not pick:
        logger.warning(f"Pick with ID {pick_id} not found for update.")
        return None
    if chosen_team is not None:
        pick.chosen_team = chosen_team
    session.add(pick)
    session.commit()
    session.refresh(pick)
    logger.info(f"Updated pick ID: {pick_id}")
    return pick


def delete_pick(session: Session, pick_id: int) -> bool:
    logger.info(f"Deleting pick ID: {pick_id}")
    pick = session.get(Pick, pick_id)
    if not pick:
        logger.warning(f"Pick with ID {pick_id} not found for deletion.")
        return False
    session.delete(pick)
    session.commit()
    logger.info(f"Deleted pick ID: {pick_id}")
    return True


# ---- RESULT ----
def create_result(
    session: Session,
    match_id: int,
    winner: str,
    score: Optional[str] = None,
) -> Result:
    logger.info(f"Creating result for match ID: {match_id}")
    result = Result(match_id=match_id, winner=winner, score=score)
    session.add(result)
    session.commit()
    session.refresh(result)
    logger.info(f"Created result with ID: {result.id}")
    return result


def get_result_by_id(session: Session, result_id: int) -> Optional[Result]:
    logger.debug(f"Fetching result by ID: {result_id}")
    return session.get(Result, result_id)


def get_result_for_match(session: Session, match_id: int) -> Optional[Result]:
    logger.debug(f"Fetching result for match ID: {match_id}")
    stmt = select(Result).where(Result.match_id == match_id)
    return session.exec(stmt).first()


def update_result(
    session: Session,
    result_id: int,
    winner: Optional[str] = None,
    score: Optional[str] = None,
) -> Optional[Result]:
    logger.info(f"Updating result ID: {result_id}")
    result = session.get(Result, result_id)
    if not result:
        logger.warning(f"Result with ID {result_id} not found for update.")
        return None
    if winner is not None:
        result.winner = winner
    if score is not None:
        result.score = score
    session.add(result)
    session.commit()
    session.refresh(result)
    logger.info(f"Updated result ID: {result_id}")
    return result


def delete_result(session: Session, result_id: int) -> bool:
    logger.info(f"Deleting result ID: {result_id}")
    result = session.get(Result, result_id)
    if not result:
        logger.warning(f"Result with ID {result_id} not found for deletion.")
        return False
    session.delete(result)
    session.commit()
    logger.info(f"Deleted result ID: {result_id}")
    return True

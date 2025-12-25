import logging
from typing import List, Optional, Type, Any
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models import (
    User,
    Contest,
    Match,
    Pick,
    Result,
    Team,
)
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class MatchCreateParams:
    contest_id: int
    team1: str
    team2: str
    scheduled_time: datetime
    leaguepedia_id: str


@dataclass
class MatchUpdateParams:
    team1: Optional[str] = None
    team2: Optional[str] = None
    scheduled_time: Optional[datetime] = None


@dataclass
class PickCreateParams:
    user_id: int
    contest_id: int
    match_id: int
    chosen_team: str
    timestamp: Optional[datetime] = None


@dataclass
class ContestUpdateParams:
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

logger = logging.getLogger(__name__)
class _DBHelpers:
    """Grouped synchronous DB helper operations to improve cohesion.

    Module-level wrapper functions delegate to these methods so external
    callers keep the same API while internal functionality is grouped.
    """

    @staticmethod
    def save_and_refresh(session: Session, obj: Any) -> Any:
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj

    @staticmethod
    def save_all_and_refresh(session: Session, objs: List[Any]) -> List[Any]:
        session.add_all(objs)
        session.commit()
        for o in objs:
            session.refresh(o)
        return objs

    @staticmethod
    def delete_and_commit(session: Session, obj: Any) -> None:
        session.delete(obj)
        session.commit()

    @staticmethod
    def create_model(session: Session, model: Type[Any], **kwargs) -> Any:
        obj = model(**kwargs)
        _DBHelpers.save_and_refresh(session, obj)
        return obj

    @staticmethod
    def get_model_by_id(session: Session, model: Type[Any], obj_id: int) -> Optional[Any]:
        return session.get(model, obj_id)

    @staticmethod
    def update_model_fields(session: Session, model: Type[Any], obj_id: int, **fields) -> Optional[Any]:
        obj = session.get(model, obj_id)
        if not obj:
            return None
        for k, v in fields.items():
            if v is not None:
                setattr(obj, k, v)
        _DBHelpers.save_and_refresh(session, obj)
        return obj

    @staticmethod
    def delete_model_by_id(session: Session, model: Type[Any], obj_id: int) -> bool:
        obj = session.get(model, obj_id)
        if not obj:
            return False
        _DBHelpers.delete_and_commit(session, obj)
        return True


# Backwards-compatible thin wrappers (preserve module API)
def _save_and_refresh(session: Session, obj: Any) -> Any:
    return _DBHelpers.save_and_refresh(session, obj)


def _save_all_and_refresh(session: Session, objs: List[Any]) -> List[Any]:
    return _DBHelpers.save_all_and_refresh(session, objs)


def _delete_and_commit(session: Session, obj: Any) -> None:
    return _DBHelpers.delete_and_commit(session, obj)


def _create_model(session: Session, model: Type[Any], **kwargs) -> Any:
    return _DBHelpers.create_model(session, model, **kwargs)


def _get_model_by_id(
    session: Session,
    model: Type[Any],
    obj_id: int,
) -> Optional[Any]:
    return _DBHelpers.get_model_by_id(session, model, obj_id)


def _update_model_fields(
    session: Session,
    model: Type[Any],
    obj_id: int,
    **fields,
) -> Optional[Any]:
    return _DBHelpers.update_model_fields(session, model, obj_id, **fields)


def _delete_model_by_id(
    session: Session,
    model: Type[Any],
    obj_id: int,
) -> bool:
    return _DBHelpers.delete_model_by_id(session, model, obj_id)


async def upsert_team(
    session: AsyncSession, team_data: dict
) -> Optional[Team]:
    """Creates or updates a team based on leaguepedia_id."""
    return await _upsert_by_leaguepedia(
        session,
        Team,
        team_data,
        update_keys=["name", "image_url", "roster"],
    )


async def upsert_contest(
    session: AsyncSession, contest_data: dict
) -> Optional[Contest]:
    """Creates or updates a contest based on leaguepedia_id."""
    return await _upsert_by_leaguepedia(
        session,
        Contest,
        contest_data,
        update_keys=["name", "start_date", "end_date"],
    )


async def _upsert_by_leaguepedia(
    session: AsyncSession,
    model: Type[Any],
    data: dict,
    update_keys: Optional[List[str]] = None,
) -> Optional[Any]:
    """Generic upsert helper for models that have a leaguepedia_id field.

    The implementation delegates the actual DB work to small module-level
    async helpers to keep this function short and reduce cyclomatic
    complexity (CodeScene "Bumpy Road" / Complex Method).
    """
    leaguepedia_id = data.get("leaguepedia_id")
    if not leaguepedia_id:
        logger.error("Missing leaguepedia_id in data for %s", model.__name__)
        return None

    try:
        obj = await _find_existing_by_leaguepedia(session, model, leaguepedia_id)
        if obj is None:
            return await _create_new_by_leaguepedia(session, model, data)
        return await _update_existing_by_leaguepedia(
            session, obj, data, update_keys
        )
    except Exception:
        logger.exception(
            "Error upserting %s with data: %s",
            model.__name__,
            data,
        )
        return None


async def _find_existing_by_leaguepedia(
    session: AsyncSession, model: Type[Any], leaguepedia_id: str
) -> Optional[Any]:
    stmt = select(model).where(
        getattr(model, "leaguepedia_id") == leaguepedia_id
    )
    res = await session.exec(stmt)
    return res.first()


async def _create_new_by_leaguepedia(
    session: AsyncSession, model: Type[Any], data: dict
) -> Any:
    logger.info("Creating new %s: %s", model.__name__, data.get("name"))
    obj = model(**data)
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    logger.info(
        "Upserted %s: %s (ID: %s)",
        obj.__class__.__name__,
        getattr(obj, "name", None),
        getattr(obj, "id", None),
    )
    return obj


async def _update_existing_by_leaguepedia(
    session: AsyncSession,
    obj: Any,
    data: dict,
    update_keys: Optional[List[str]] = None,
) -> Any:
    logger.info(
        "Updating existing %s: %s",
        obj.__class__.__name__,
        getattr(obj, "name", None),
    )

    _apply_updates_to_obj(obj, data, update_keys)

    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    logger.info(
        "Upserted %s: %s (ID: %s)",
        obj.__class__.__name__,
        getattr(obj, "name", None),
        getattr(obj, "id", None),
    )
    return obj


def _apply_updates_to_obj(
    obj: Any, data: dict, update_keys: Optional[List[str]] = None
) -> None:
    """Dispatch to a focused updater helper.

    Split into two very small helpers to reduce cyclomatic complexity in
    the calling code and make each piece trivially testable.
    """
    if update_keys is None:
        _apply_all_updates(obj, data)
    else:
        _apply_selected_updates(obj, data, update_keys)


def _apply_all_updates(obj: Any, data: dict) -> None:
    """Apply all values from `data` onto `obj`, skipping the id field."""
    for k, v in data.items():
        if k == "leaguepedia_id":
            continue
        setattr(obj, k, v)


def _apply_selected_updates(
    obj: Any, data: dict, update_keys: Optional[List[str]]
) -> None:
    """Apply only keys listed in `update_keys` from `data` onto `obj`."""
    if not update_keys:
        return
    for k in update_keys:
        if k in data:
            setattr(obj, k, data[k])


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
    _save_and_refresh(session, user)
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
    _save_and_refresh(session, user)
    logger.info(f"Updated user ID: {user_id}")
    return user


def delete_user(session: Session, user_id: int) -> bool:
    logger.info(f"Deleting user ID: {user_id}")
    user = session.get(User, user_id)
    if not user:
        logger.warning(f"User with ID {user_id} not found for deletion.")
        return False
    _delete_and_commit(session, user)
    logger.info(f"Deleted user ID: {user_id}")
    return True


# ---- CONTEST ----
def create_contest(session: Session, contest_data: dict) -> Contest:
    """Creates a contest from a dict containing keys:
    name, start_date, end_date, leaguepedia_id.
    """
    name = contest_data.get("name")
    start_date = contest_data.get("start_date")
    end_date = contest_data.get("end_date")
    leaguepedia_id = contest_data.get("leaguepedia_id")

    logger.info(f"Creating contest: {name}")
    contest = Contest(
        name=name,
        start_date=start_date,
        end_date=end_date,
        leaguepedia_id=leaguepedia_id,
    )
    _save_and_refresh(session, contest)
    logger.info(f"Created contest with ID: {contest.id}")
    return contest


def get_contest_by_id(session: Session, contest_id: int) -> Optional[Contest]:
    logger.debug(f"Fetching contest by ID: {contest_id}")
    return session.get(Contest, contest_id)


def list_contests(session: Session) -> List[Contest]:
    logger.debug("Listing all contests")
    return list(session.exec(select(Contest)))


def update_contest(
    session: Session, contest_id: int, params: ContestUpdateParams
) -> Optional[Contest]:
    logger.info(f"Updating contest ID: {contest_id}")
    contest = session.get(Contest, contest_id)
    if not contest:
        logger.warning(f"Contest with ID {contest_id} not found for update.")
        return None
    if params.name is not None:
        contest.name = params.name
    if params.start_date is not None:
        contest.start_date = params.start_date
    if params.end_date is not None:
        contest.end_date = params.end_date
    _save_and_refresh(session, contest)
    logger.info(f"Updated contest ID: {contest_id}")
    return contest


def delete_contest(session: Session, contest_id: int) -> bool:
    logger.info(f"Deleting contest ID: {contest_id}")
    contest = session.get(Contest, contest_id)
    if not contest:
        logger.warning(f"Contest with ID {contest_id} not found for deletion.")
        return False
    _delete_and_commit(session, contest)
    logger.info(f"Deleted contest ID: {contest_id}")
    return True


# ---- MATCH ----
def create_match(session: Session, params: MatchCreateParams) -> Match:
    logger.info(
        "Creating match: %s vs %s for contest %s",
        params.team1,
        params.team2,
        params.contest_id,
    )
    match = Match(
        contest_id=params.contest_id,
        team1=params.team1,
        team2=params.team2,
        scheduled_time=params.scheduled_time,
        leaguepedia_id=params.leaguepedia_id,
    )
    _save_and_refresh(session, match)
    logger.info(f"Created match with ID: {match.id}")
    return match


def bulk_create_matches(
    session: Session, matches_data: List[dict]
) -> List[Match]:
    """Bulk creates matches from a list of dicts."""
    logger.info(f"Bulk creating {len(matches_data)} matches")
    matches = [Match(**data) for data in matches_data]
    _save_all_and_refresh(session, matches)
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
    session: Session, match_id: int, params: MatchUpdateParams
) -> Optional[Match]:
    logger.info(f"Updating match ID: {match_id}")
    match = session.get(Match, match_id)
    if not match:
        logger.warning(f"Match with ID {match_id} not found for update.")
        return None
    if params.team1 is not None:
        match.team1 = params.team1
    if params.team2 is not None:
        match.team2 = params.team2
    if params.scheduled_time is not None:
        match.scheduled_time = params.scheduled_time
    _save_and_refresh(session, match)
    logger.info(f"Updated match ID: {match_id}")
    return match


def delete_match(session: Session, match_id: int) -> bool:
    logger.info(f"Deleting match ID: {match_id}")
    match = session.get(Match, match_id)
    if not match:
        logger.warning(f"Match with ID {match_id} not found for deletion.")
        return False
    _delete_and_commit(session, match)
    logger.info(f"Deleted match ID: {match_id}")
    return True


# ---- PICK ----
# Allow this function to have multiple explicit args for clarity
# despite lint rules
# pylint: disable=too-many-arguments
def create_pick(session: Session, params: PickCreateParams) -> Pick:
    logger.info(
        "Creating pick for user %s, match %s, team %s",
        params.user_id,
        params.match_id,
        params.chosen_team,
    )
    pick_args = dict(
        user_id=params.user_id,
        contest_id=params.contest_id,
        match_id=params.match_id,
        chosen_team=params.chosen_team,
    )
    if params.timestamp is not None:
        pick_args["timestamp"] = params.timestamp
    pick = Pick(**pick_args)
    _save_and_refresh(session, pick)
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
    _save_and_refresh(session, pick)
    logger.info(f"Updated pick ID: {pick_id}")
    return pick


def delete_pick(session: Session, pick_id: int) -> bool:
    logger.info(f"Deleting pick ID: {pick_id}")
    pick = session.get(Pick, pick_id)
    if not pick:
        logger.warning(f"Pick with ID {pick_id} not found for deletion.")
        return False
    _delete_and_commit(session, pick)
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
    _save_and_refresh(session, result)
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
    _save_and_refresh(session, result)
    logger.info(f"Updated result ID: {result_id}")
    return result


def delete_result(session: Session, result_id: int) -> bool:
    logger.info(f"Deleting result ID: {result_id}")
    result = session.get(Result, result_id)
    if not result:
        logger.warning(f"Result with ID {result_id} not found for deletion.")
        return False
    _delete_and_commit(session, result)
    logger.info(f"Deleted result ID: {result_id}")
    return True

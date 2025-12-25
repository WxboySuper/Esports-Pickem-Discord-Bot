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
        """
        Persist an ORM object to the database and refresh its state
        from the session.
        
        Parameters:
            obj (Any): ORM model instance to add, commit, and refresh
                in the given session.
        
        Returns:
            Any: The same `obj` instance after commit and session
                refresh, reflecting persisted database state.
        """
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj

    @staticmethod
    def save_all_and_refresh(session: Session, objs: List[Any]) -> List[Any]:
        """
        Persist multiple ORM objects to the database and refresh them
        from the session.
        
        Parameters:
            objs (List[Any]): Iterable of mapped ORM instances to add
                and persist.
        
        Returns:
            List[Any]: The same list of instances after being
                refreshed with the database state.
        """
        session.add_all(objs)
        session.commit()
        for o in objs:
            session.refresh(o)
        return objs

    @staticmethod
    def delete_and_commit(session: Session, obj: Any) -> None:
        """
        Delete an ORM mapped instance from the provided session and
        commit the transaction.
        
        Parameters:
            session (Session): SQLAlchemy session used to perform the
                deletion and commit.
            obj (Any): ORM-mapped instance to be removed from the
                database.
        """
        session.delete(obj)
        session.commit()

    @staticmethod
    def create_model(session: Session, model: Type[Any], **kwargs) -> Any:
        """
        Create and persist a new instance of the given model using
        the provided field values.
        
        Parameters:
            model (Type[Any]): ORM model class to instantiate.
            **kwargs: Field values passed to the model constructor.
        
        Returns:
            Any: The newly created and refreshed model instance.
        """
        obj = model(**kwargs)
        _DBHelpers.save_and_refresh(session, obj)
        return obj

    @staticmethod
    def get_model_by_id(session: Session, model: Type[Any], obj_id: int) -> Optional[Any]:
        """
        Retrieve a mapped model instance by its primary key.
        
        Parameters:
            model (Type[Any]): ORM model class to query.
            obj_id (int): Primary key of the desired object.
        
        Returns:
            The model instance if found, `None` otherwise.
        """
        return session.get(model, obj_id)

    @staticmethod
    def update_model_fields(session: Session, model: Type[Any], obj_id: int, **fields) -> Optional[Any]:
        """
        Update specified attributes on a model instance identified by
        its primary key.
        
        Only attributes provided in `**fields` whose values are not
        `None` are applied. The instance is persisted and refreshed
        before being returned.
        
        Parameters:
            model (Type[Any]): ORM model class of the object to
                update.
            obj_id (int): Primary key of the object to update.
            **fields: Attribute names and their new values; attributes
                with value `None` are ignored.
        
        Returns:
            Optional[Any]: The updated and refreshed model instance,
                or `None` if no object with `obj_id` exists.
        """
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
        """
        Delete the database record of the given model with the
        specified primary key if it exists.
        
        Parameters:
            model (Type[Any]): ORM model class to delete from.
            obj_id (int): Primary key of the object to delete.
        
        Returns:
            bool: `True` if the object was found and deleted, `False`
                otherwise.
        """
        obj = session.get(model, obj_id)
        if not obj:
            return False
        _DBHelpers.delete_and_commit(session, obj)
        return True


# Backwards-compatible thin wrappers (preserve module API)
def _save_and_refresh(session: Session, obj: Any) -> Any:
    """
    Persist the given ORM object, commit the transaction, refresh its
    state from the database, and return it.
    
    Returns:
        The same object after being persisted and refreshed.
    """
    return _DBHelpers.save_and_refresh(session, obj)


def _save_all_and_refresh(session: Session, objs: List[Any]) -> List[Any]:
    """
    Persist multiple ORM objects in the database, commit the
    transaction, and refresh each instance.
    
    Parameters:
        objs (List[Any]): Iterable of ORM instances to be added and
            refreshed.
    
    Returns:
        List[Any]: The provided objects after being committed and
            refreshed.
    """
    return _DBHelpers.save_all_and_refresh(session, objs)


def _delete_and_commit(session: Session, obj: Any) -> None:
    """
    Delete a mapped ORM object from the given session and commit the
    transaction.
    
    Parameters:
        session (Session): Active SQLAlchemy session used for the
            operation.
        obj (Any): Mapped ORM instance to remove from the database.
    """
    return _DBHelpers.delete_and_commit(session, obj)


def _create_model(session: Session, model: Type[Any], **kwargs) -> Any:
    """
    Create and persist a new instance of the given model using the
    provided field values.
    
    Parameters:
        session (Session): Database session used to persist the
            instance.
        model (Type[Any]): ORM model class to instantiate.
        **kwargs: Field values passed to the model constructor.
    
    Returns:
        Any: The newly created and refreshed model instance.
    """
    return _DBHelpers.create_model(session, model, **kwargs)


def _get_model_by_id(
    session: Session,
    model: Type[Any],
    obj_id: int,
) -> Optional[Any]:
    """
    Retrieve a model instance by its primary key.
    
    Parameters:
        model (Type[Any]): ORM model class to query.
        obj_id (int): Primary key of the desired record.
    
    Returns:
        The model instance if found, otherwise None.
    """
    return _DBHelpers.get_model_by_id(session, model, obj_id)


def _update_model_fields(
    session: Session,
    model: Type[Any],
    obj_id: int,
    **fields,
) -> Optional[Any]:
    """
    Update the specified fields on a model instance identified by its
    primary key and persist the changes.
    
    Parameters:
        model (Type[Any]): ORM model class of the object to update.
        obj_id (int): Primary key of the object to update.
        **fields: Field names and their new values; only keys with
            non-None values are applied.
    
    Returns:
        Any | None: The updated model instance after persistence, or
            `None` if no object with `obj_id` was found.
    """
    return _DBHelpers.update_model_fields(session, model, obj_id, **fields)


def _delete_model_by_id(
    session: Session,
    model: Type[Any],
    obj_id: int,
) -> bool:
    """
    Remove a single database model instance identified by its primary key.
    
    Parameters:
        model (Type[Any]): ORM model class to delete from.
        obj_id (int): Primary key of the object to remove.
    
    Returns:
        bool: `True` if an object was deleted, `False` if no matching object was found.
    """
    return _DBHelpers.delete_model_by_id(session, model, obj_id)


async def upsert_team(
    session: AsyncSession, team_data: dict
) -> Optional[Team]:
    """
    Create or update a Team using its `leaguepedia_id`.
    
    Parameters:
        team_data (dict): Mapping containing team fields. Must include `leaguepedia_id`; other keys may include `name`, `image_url`, `roster`, and any other Team fields to set.
    
    Returns:
        team (Optional[Team]): The created or updated Team instance, or `None` if `leaguepedia_id` is missing or an error occurred during upsert.
    """
    return await _upsert_by_leaguepedia(
        session,
        Team,
        team_data,
        update_keys=["name", "image_url", "roster"],
    )


async def upsert_contest(
    session: AsyncSession, contest_data: dict
) -> Optional[Contest]:
    """
    Create or update a Contest using its Leaguepedia identifier.
    
    The function upserts a Contest by `leaguepedia_id`, creating a new record if none exists or updating the existing record. Only `name`, `start_date`, and `end_date` are considered for updates.
    
    Parameters:
        contest_data (dict): Mapping of contest fields. Must include `leaguepedia_id`. May include `name`, `start_date`, and `end_date`.
    
    Returns:
        Contest or None: The created or updated Contest, or `None` if the upsert failed or `leaguepedia_id` was missing.
    """
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
    """
    Upserts a model instance identified by its `leaguepedia_id` using the provided data.
    
    Parameters:
        session (AsyncSession): Database session used for querying and persistence.
        model (Type[Any]): ORM model class that contains a `leaguepedia_id` field.
        data (dict): Mapping of field names to values; must include a `leaguepedia_id` key.
        update_keys (Optional[List[str]]): If provided, only these keys from `data` will be applied when updating an existing object; otherwise all fields (except `leaguepedia_id`) are applied.
    
    Returns:
        Optional[Any]: The created or updated model instance, or `None` if `leaguepedia_id` is missing or an error occurred during upsert.
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
    """
    Retrieve the first instance of the given ORM model with the specified Leaguepedia identifier.
    
    Parameters:
        model (Type[Any]): ORM model class that defines a `leaguepedia_id` attribute.
        leaguepedia_id (str): Leaguepedia identifier to match.
    
    Returns:
        Optional[Any]: The first matching model instance if found, `None` otherwise.
    """
    stmt = select(model).where(
        getattr(model, "leaguepedia_id") == leaguepedia_id
    )
    res = await session.exec(stmt)
    return res.first()


async def _create_new_by_leaguepedia(
    session: AsyncSession, model: Type[Any], data: dict
) -> Any:
    """
    Create and persist a new model instance initialized from the provided Leaguepedia data.
    
    Parameters:
        session (AsyncSession): Async database session used to add and flush the new instance.
        model (Type[Any]): ORM model class to instantiate.
        data (dict): Mapping of attributes used to construct the model instance.
    
    Returns:
        Any: The newly created and refreshed model instance.
    """
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
    """
    Apply fields from `data` to an existing ORM model instance and persist the changes.
    
    Parameters:
        obj (Any): The existing model instance to update.
        data (dict): Mapping of field names to new values to apply to `obj`.
        update_keys (Optional[List[str]]): If provided, only keys in this list will be applied from `data`.
    
    Returns:
        Any: The refreshed model instance after updates have been flushed and reloaded from the database.
    """
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
    """
    Apply fields from `data` to `obj`, optionally restricting updates to the keys listed in `update_keys`.
    
    Parameters:
        obj: The target object to receive updates.
        data (dict): Mapping of field names to new values.
        update_keys (Optional[List[str]]): If provided, only fields
            whose names appear in this list are applied; if `None`,
            all fields in `data` are applied.
    """
    if update_keys is None:
        _apply_all_updates(obj, data)
    else:
        _apply_selected_updates(obj, data, update_keys)


def _apply_all_updates(obj: Any, data: dict) -> None:
    """
    Apply every key/value in `data` to `obj` as attributes,
    excluding the `leaguepedia_id` key.
    
    Parameters:
    	obj (Any): Target object whose attributes will be set.
    	data (dict): Mapping of attribute names to values to apply;
    	    any `leaguepedia_id` entry is ignored.
    """
    for k, v in data.items():
        if k == "leaguepedia_id":
            continue
        setattr(obj, k, v)


def _apply_selected_updates(
    obj: Any, data: dict, update_keys: Optional[List[str]]
) -> None:
    """
    Apply selected fields from a data mapping to an object's attributes.
    
    Parameters:
        obj (Any): Target object whose attributes will be updated.
        data (dict): Mapping of attribute names to values.
        update_keys (Optional[List[str]]): List of keys to apply
            from `data`. If empty or None, no changes are made.
    
    Notes:
        Only keys present in both `update_keys` and `data` are
        applied; keys absent from `data` are ignored.
    """
    if not update_keys:
        return
    for k in update_keys:
        if k in data:
            setattr(obj, k, data[k])


async def upsert_match(
    session: AsyncSession, match_data: dict
) -> tuple[Optional[Match], bool]:
    """
    Create or update a Match identified by its `leaguepedia_id`.
    
    Parameters:
        match_data (dict): Mapping with match fields. Must include
            `leaguepedia_id`, `team1`, `team2`, and `scheduled_time`.
            May include `best_of` and other Match fields.
    
    Returns:
        tuple[Optional[Match], bool]: A tuple containing the upserted
            Match (or `None` on failure) and a boolean that is `true`
            if the match's scheduled time changed or the match was
            newly created, `false` otherwise.
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
    """
    Create a new User record with the given Discord ID and optional username.
    
    Parameters:
        discord_id (str): Discord identifier for the user.
        username (Optional[str]): Display name to associate with
            the user; if omitted, the username will be unset.
    
    Returns:
        user (User): The persisted User instance with its
            database-assigned `id` populated.
    """
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
    """
    Update a user's username when a new value is provided.
    
    Fetches the User by id, sets the username if `username` is not
    None, persists the change, and returns the updated User.
    
    Parameters:
        user_id (int): Primary key of the User to update.
        username (Optional[str]): New username to apply; if None,
            the user's username is left unchanged.
    
    Returns:
        User | None: The updated User instance, or `None` if no user
            with the given id exists.
    """
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
    """
    Delete a user record by its primary key and persist the change.
    
    Deletes the user with the given ID from the database and commits
    the transaction.
    
    Returns:
        `true` if the user was found and deleted, `false` otherwise.
    """
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
    """
    Create a Contest record from a dictionary of contest fields.
    
    Parameters:
        contest_data (dict): Dictionary with contest attributes. Expected keys:
            - "name" (str): Contest name.
            - "start_date" (datetime): Contest start date/time.
            - "end_date" (datetime): Contest end date/time.
            - "leaguepedia_id" (str): External leaguepedia identifier.
    
    Returns:
        Contest: The persisted Contest instance with
            database-generated fields (e.g., `id`) populated.
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
    """
    Update fields of an existing Contest using values provided in `params`.
    
    Parameters:
        contest_id (int): Primary key of the Contest to update.
        params (ContestUpdateParams): Dataclass containing optional
            fields (`name`, `start_date`, `end_date`) to apply; only
            non-None fields are written.
    
    Returns:
        Contest | None: The updated Contest if found and modified,
            `None` if no Contest with the given `contest_id` exists.
    """
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
    """
    Delete the contest with the given ID from the database.
    
    Parameters:
        contest_id (int): Primary key of the contest to delete.
    
    Returns:
        bool: True if the contest was found and deleted, False otherwise.
    """
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
    """
    Create a Match from the given MatchCreateParams and persist it
    to the database.
    
    Parameters:
        params (MatchCreateParams): Parameter object containing
            contest_id, team1, team2, scheduled_time, and
            leaguepedia_id used to construct the Match.
    
    Returns:
        Match: The persisted Match instance with database-generated
            fields (e.g., `id`) populated.
    """
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
    """
    Create multiple Match records from a list of dictionaries and
    persist them.
    
    Parameters:
        session (Session): Database session used to persist matches.
        matches_data (List[dict]): List of dictionaries with keys
            required to initialize a `Match` (for example:
            `contest_id`, `team1`, `team2`, `scheduled_time`,
            `leaguepedia_id`).
    
    Returns:
        List[Match]: The created and refreshed `Match` instances.
    """
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
    """
    Apply provided match update fields to an existing Match and persist the changes.
    
    Parameters:
        params (MatchUpdateParams): Update container whose non-None fields (team1, team2, scheduled_time) will be applied to the match.
    
    Returns:
        Updated Match if a match with the given id was found and updated, `None` if no such match exists.
    """
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
    """
    Delete the Match with the given primary key and commit the change.
    
    Deletes the matching Match record from the database and commits the transaction.
    
    Parameters:
        match_id (int): Primary key of the Match to delete.
    
    Returns:
        bool: `True` if the match was deleted, `False` if no match with the given id was found.
    """
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
    """
    Create and persist a Pick for a user in a contest match.
    
    Parameters:
        params (PickCreateParams): Parameter object containing `user_id`, `contest_id`, `match_id`, `chosen_team`, and optional `timestamp`.
    
    Returns:
        Pick: The persisted Pick instance with database-populated fields (for example, `id`) refreshed.
    """
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
    """
    Update an existing Pick's chosen team.
    
    Parameters:
        session (Session): Database session used for the update.
        pick_id (int): Primary key of the Pick to update.
        chosen_team (Optional[str]): New team name to set; if None the field is left unchanged.
    
    Returns:
        Optional[Pick]: The updated Pick if found, otherwise None.
    """
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
    """
    Delete a Pick record identified by its primary key.
    
    Attempts to remove the Pick with the given id from the database and commit the change.
    
    Parameters:
        pick_id (int): Primary key of the Pick to delete.
    
    Returns:
        bool: `True` if the pick was deleted, `False` if no pick with the given id existed.
    """
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
    """
    Create a Result record linking a match to its winner and optional score.
    
    Parameters:
        match_id (int): Primary key of the match the result belongs to.
        winner (str): Identifier or name of the winning team.
        score (Optional[str]): Optional score string (for example "2-1").
    
    Returns:
        Result: The newly created and refreshed Result instance.
    """
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
    """
    Update fields of an existing Result record.
    
    Only parameters provided (non-None) are applied to the stored Result. If the result with the given id does not exist, nothing is changed.
    
    Parameters:
        result_id (int): Primary key of the Result to update.
        winner (Optional[str]): New winner value to set, if provided.
        score (Optional[str]): New score value to set, if provided.
    
    Returns:
        Optional[Result]: The updated Result object when found and saved, or `None` if no matching Result exists.
    """
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
    """
    Delete the Result with the given primary key.
    
    Returns:
        True if a Result with the given `result_id` was found and deleted, False otherwise.
    """
    logger.info(f"Deleting result ID: {result_id}")
    result = session.get(Result, result_id)
    if not result:
        logger.warning(f"Result with ID {result_id} not found for deletion.")
        return False
    _delete_and_commit(session, result)
    logger.info(f"Deleted result ID: {result_id}")
    return True
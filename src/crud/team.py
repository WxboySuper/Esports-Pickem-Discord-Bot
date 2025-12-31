import logging
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models import Team
from .sync_utils import _upsert_by_leaguepedia

logger = logging.getLogger(__name__)


async def upsert_team(
    session: AsyncSession, team_data: dict
) -> Optional[Team]:
    """
    Create or update a Team using its `leaguepedia_id`.

    Parameters:
        team_data (dict): Mapping containing team fields. Must include
            `leaguepedia_id`; other keys may include `name`,
            `image_url`, `roster`, and any other Team fields to set.

    Returns:
        team (Optional[Team]): The created or updated Team instance,
            or `None` if `leaguepedia_id` is missing or an error
            occurred during upsert.
    """
    return await _upsert_by_leaguepedia(
        session,
        Team,
        team_data,
        update_keys=["name", "image_url", "roster"],
    )


async def upsert_team_by_pandascore(
    session: AsyncSession, team_data: dict
) -> Optional[Team]:
    """
    Create or update a Team using its PandaScore ID.

    Parameters:
        team_data (dict): Mapping containing team fields. Must include
            `pandascore_id`; other keys may include `name`, `acronym`,
            `image_url`, and other Team fields.

    Returns:
        Optional[Team]: The created or updated Team instance,
            or None if pandascore_id is missing or an error occurred.
    """
    pandascore_id = team_data.get("pandascore_id")
    if pandascore_id is None:
        logger.error("Missing pandascore_id in team_data")
        return None

    try:
        team = await _find_team_by_pandascore_or_name(session, team_data)

        if team:
            _update_team_from_data(team, team_data)
        else:
            team = _create_team_from_data(team_data)

        session.add(team)
        await session.flush()
        logger.info("Upserted team: %s (ID: %s)", team.name, team.id)
        return team
    except Exception:
        logger.exception("Error upserting team with data: %s", team_data)
        return None


async def _find_team_by_pandascore_or_name(
    session: AsyncSession,
    team_data: dict,
    allow_name_fallback: bool = False,
) -> Optional[Team]:
    """Finds a team by PandaScore ID or optionally by name.

    Lookup strategy:
    1. If `pandascore_id` is present, return the team matching that ID.
    2. If not found and `allow_name_fallback` is True, attempt a name-based
       lookup but only if additional validation attributes (such as
       `acronym` or `region`) are provided. When falling back, require at
       least one validation field to match the candidate before returning
       it. This avoids silently linking wrong teams by name alone.

    Parameters:
        session: AsyncSession to use for DB queries.
        team_data: Mapping with incoming team fields (may include
            `pandascore_id`, `name`, `acronym`, `region`).
        allow_name_fallback: If True, permit name-based fallback subject to
            validation (default False).

    Returns:
        Optional[Team]: Matched `Team` or `None` if no safe match was found.
    """
    pandascore_id = team_data.get("pandascore_id")
    if pandascore_id is not None:
        team = await _get_team_by_pandascore(session, pandascore_id)
        if team:
            return team

    # Short-circuit when name fallback isn't allowed
    if not allow_name_fallback:
        return None

    name = team_data.get("name")
    if not name:
        return None

    provided_acronym = team_data.get("acronym")
    provided_region = team_data.get("region")
    if not provided_acronym and not provided_region:
        logger.debug(
            "Name fallback disabled; no validation fields for '%s'",
            name,
        )
        return None

    validation = {"acronym": provided_acronym, "region": provided_region}
    return await _find_valid_candidate_by_name(
        session, name, validation, team_data.get("pandascore_id")
    )


async def _get_team_by_pandascore(
    session: AsyncSession, pandascore_id: int
) -> Optional[Team]:
    result = await session.exec(
        select(Team).where(Team.pandascore_id == pandascore_id)
    )
    return result.first()


async def _get_candidates_by_name(
    session: AsyncSession, name: str
) -> list[Team]:
    result = await session.exec(select(Team).where(Team.name == name))
    return result.all()


def _candidate_matches_validation(
    cand: Team, provided_acronym: Optional[str], provided_region: Optional[str]
) -> bool:
    if (
        provided_acronym is not None
        and getattr(cand, "acronym", None) != provided_acronym
    ):
        return False
    if (
        provided_region is not None
        and getattr(cand, "region", None) != provided_region
    ):
        return False
    return True


async def _find_valid_candidate_by_name(
    session: AsyncSession,
    name: str,
    validation: dict[str, Optional[str]] | None = None,
    incoming_pandascore_id: Optional[int] = None,
) -> Optional[Team]:
    """Return the first candidate matching validation rules, or None.

    `validation` may contain keys like `acronym` and `region` used to
    validate candidate matches.
    """
    provided_acronym = (
        None if validation is None else validation.get("acronym")
    )
    provided_region = None if validation is None else validation.get("region")

    candidates = await _get_candidates_by_name(session, name)
    for cand in candidates:
        if _candidate_matches_validation(
            cand, provided_acronym, provided_region
        ):
            logger.warning(
                "Name fallback matched id %s for incoming id %s (name=%s)",
                cand.id,
                incoming_pandascore_id,
                name,
            )
            return cand
    logger.debug("No validated name-fallback for %s", name)
    return None


def _update_team_from_data(team: Team, team_data: dict) -> None:
    """Updates existing team fields from data."""
    logger.info("Updating existing team: %s", team.name)
    for key in ["name", "acronym", "image_url", "pandascore_id"]:
        if key in team_data and team_data[key] is not None:
            setattr(team, key, team_data[key])


def _create_team_from_data(team_data: dict) -> Team:
    """Creates a new team instance from data."""
    logger.info("Creating new team: %s", team_data.get("name"))
    return Team(**team_data)


async def get_team_by_pandascore_id(
    session: AsyncSession, pandascore_id: int
) -> Optional[Team]:
    """
    Fetch a team by its PandaScore ID.

    Parameters:
        pandascore_id: The PandaScore team ID

    Returns:
        Optional[Team]: The Team if found, None otherwise
    """
    result = await session.exec(
        select(Team).where(Team.pandascore_id == pandascore_id)
    )
    return result.first()

from typing import Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models import Team
from .sync_utils import _upsert_by_leaguepedia

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

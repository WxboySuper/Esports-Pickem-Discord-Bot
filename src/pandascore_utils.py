"""
Small helpers extracted from pandascore_sync to reduce file-level complexity.
"""

import logging
from typing import Any, Dict, Optional

from src.crud import get_match_by_pandascore_id
from src.notifications import send_result_notification
from src.reminders import schedule_reminders

logger = logging.getLogger(__name__)


async def safe_schedule(match: Any) -> None:
    try:
        await schedule_reminders(match)
    except Exception:
        logger.exception("Failed to schedule reminders for match %s", match.id)


async def safe_notify(match_id: int, result_id: int) -> None:
    try:
        await send_result_notification(match_id, result_id)
    except Exception:
        logger.exception(
            "Failed to notify for match %s (result %s)", match_id, result_id
        )


async def maybe_start_running_match(
    db_session: Any, match_data: Dict[str, Any]
) -> Optional[int]:
    pandascore_id = match_data.get("id")
    if not pandascore_id:
        return None

    match = await get_match_by_pandascore_id(db_session, pandascore_id)
    if not match:
        return None

    if match.status == "running":
        return None

    match.status = "running"
    db_session.add(match)
    logger.info("Match %s started (PandaScore: %s)", match.id, pandascore_id)
    return match.id


async def maybe_finish_running_match(
    db_session: Any, match_data: Dict[str, Any]
) -> Optional[int]:
    """
    Detect if a running match has finished according to PandaScore data and
    update its status in the provided DB session. Returns the match id if
    the status was transitioned to 'finished', otherwise None.
    """
    pandascore_id = match_data.get("id")
    if not pandascore_id:
        return None

    # Only consider matches that are reported as finished by PandaScore
    if match_data.get("status") != "finished":
        return None

    match = await get_match_by_pandascore_id(db_session, pandascore_id)
    if not match:
        return None

    if match.status == "finished":
        return None

    match.status = "finished"
    db_session.add(match)
    logger.info("Match %s finished (PandaScore: %s)", match.id, pandascore_id)
    return match.id

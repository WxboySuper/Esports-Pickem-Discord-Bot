"""
src/admin_utils.py - Utilities for admin permission checks.
"""

import os
import logging

logger = logging.getLogger("esports-bot.admin_utils")

# Parse ADMIN_IDS from environment
_raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = []
if _raw_admin_ids.strip():
    for part in _raw_admin_ids.split(","):
        token = part.strip()
        if not token:
            continue
        if token.isdigit():
            try:
                ADMIN_IDS.append(int(token))
            except ValueError:
                logger.warning(
                    "ADMIN_IDS entry could not be converted to int: %r",
                    token,
                )
        else:
            logger.warning("Ignoring non-numeric ADMIN_IDS entry: %r", token)


def is_admin(user_id: int) -> bool:
    """Check if a user ID is in the admin list."""
    return user_id in ADMIN_IDS

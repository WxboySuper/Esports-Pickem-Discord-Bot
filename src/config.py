import os
import logging

logger = logging.getLogger(__name__)

# Load ADMIN_IDS from environment, this is a comma-separated list of user IDs.
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

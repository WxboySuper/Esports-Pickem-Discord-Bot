import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from src.db import DATABASE_URL

logger = logging.getLogger(__name__)

jobstores = {"default": SQLAlchemyJobStore(url=DATABASE_URL)}

# Lazily create the AsyncIOScheduler to avoid creating background
# scheduler objects (and associated event loop hooks) at import time
# which can interfere with test runners and cause processes to not exit.
_scheduler = None


def get_scheduler() -> AsyncIOScheduler:
    """
    Lazily instantiate and return the module-level AsyncIOScheduler.

    Returns:
        AsyncIOScheduler: The shared scheduler instance used by the
            module; created on first invocation and reused thereafter.
    """
    global _scheduler  # skipcq: PYL-W0603
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(jobstores=jobstores)
    return _scheduler


# A lightweight proxy object that forwards attribute access to the
# lazily-created scheduler. This keeps `scheduler` available at module
# level so tests and code that patch `src.scheduler.scheduler` continue to
# work, while still avoiding creation of the real scheduler until needed.
class _SchedulerProxy:
    def __getattr__(self, item):
        """
        Delegate attribute lookups to the underlying
        lazily-instantiated scheduler.

        Parameters:
            item (str): Name of the attribute being accessed on
                the proxy.

        Returns:
            Any: The attribute value retrieved from the underlying
                scheduler instance.
        """
        return getattr(get_scheduler(), item)


# Public module-level symbol for compatibility
scheduler = _SchedulerProxy()

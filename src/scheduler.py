import logging
from src.scheduler_instance import scheduler

logger = logging.getLogger(__name__)


def start_scheduler():
    """
    Ensure the module scheduler has the required recurring jobs and start
    it if not already running.

    Registers a 6-hour interval job to sync Leaguepedia data and a
    5-minute interval job to schedule live match polling, then starts the
    scheduler if it is not running. If the scheduler is already running,
    the function leaves it unchanged.
    """
    from src.sync_logic import perform_leaguepedia_sync
    from src.polling_manager import schedule_live_polling

    if not getattr(scheduler, "running", False):
        logger.info("Scheduler not running. Starting jobs...")
        scheduler.add_job(
            perform_leaguepedia_sync,
            "interval",
            hours=6,
            id="sync_all_tournaments_job",
            replace_existing=True,
        )
        logger.info("Added 'sync_all_tournaments_job' to scheduler.")
        scheduler.add_job(
            schedule_live_polling,
            "interval",
            minutes=5,
            id="schedule_live_polling_job",
            replace_existing=True,
        )
        logger.info("Added 'schedule_live_polling_job' to scheduler.")

        scheduler.start()
        logger.info("Scheduler started.")
    else:
        logger.info("Scheduler is already running.")

import logging
from src.scheduler_instance import scheduler

logger = logging.getLogger(__name__)


def start_scheduler():
    """
    Ensure the module scheduler has the required recurring jobs and start
    it if not already running.

    Registers a 6-hour interval job to sync PandaScore data and a
    5-minute interval job to schedule live match polling, then starts the
    scheduler if it is not running. If the scheduler is already running,
    the function leaves it unchanged.
    """
    from src.pandascore_sync import perform_pandascore_sync
    from src.polling_manager import schedule_live_polling
    from src.pandascore_polling import poll_running_matches_job
    from src.scripts.fix_pick_statuses import fix_pick_statuses

    if not getattr(scheduler, "running", False):
        logger.info("Scheduler not running. Starting jobs...")
        scheduler.add_job(
            perform_pandascore_sync,
            "interval",
            hours=6,
            id="sync_pandascore_job",
            replace_existing=True,
        )
        scheduler.add_job(
            fix_pick_statuses,
            "interval",
            hours=6,
            id="fix_pick_statuses_job",
            replace_existing=True,
        )
        logger.info("Added 'sync_pandascore_job' to scheduler.")
        scheduler.add_job(
            schedule_live_polling,
            "interval",
            minutes=5,
            id="schedule_live_polling_job",
            replace_existing=True,
        )
        logger.info("Added 'schedule_live_polling_job' to scheduler.")
        # Poll running matches every 2 minutes for score updates
        scheduler.add_job(
            poll_running_matches_job,
            "interval",
            minutes=2,
            id="poll_running_matches_job",
            replace_existing=True,
        )
        logger.info("Added 'poll_running_matches_job' to scheduler.")

        scheduler.start()
        logger.info("Scheduler started.")
    else:
        logger.info("Scheduler is already running.")

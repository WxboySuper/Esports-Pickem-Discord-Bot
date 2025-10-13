from unittest.mock import patch, MagicMock, call

# Import the function to test
from src.scheduler import (
    start_scheduler,
    perform_leaguepedia_sync,
    schedule_live_polling,
    ANNOUNCEMENT_GUILD_ID,
)


def test_start_scheduler_adds_jobs_with_replace_existing():
    """
    Tests that start_scheduler calls add_job with replace_existing=True
    to prevent conflicts on subsequent startups.
    """
    mock_scheduler = MagicMock()
    mock_scheduler.running = False

    # Patch the global scheduler instance with our mock
    with patch("src.scheduler.scheduler", mock_scheduler):
        # Call the function that configures and starts the scheduler
        start_scheduler()

        # Verify that the jobs were added with the correct parameters
        expected_calls = [
            call(
                perform_leaguepedia_sync,
                "interval",
                hours=6,
                id="sync_all_tournaments_job",
                replace_existing=True,
            ),
            call(
                schedule_live_polling,
                "interval",
                minutes=1,
                id="schedule_live_polling_job",
                args=[ANNOUNCEMENT_GUILD_ID],
                replace_existing=True,
            ),
        ]
        mock_scheduler.add_job.assert_has_calls(expected_calls, any_order=True)

        # Verify that the scheduler was started
        mock_scheduler.start.assert_called_once()

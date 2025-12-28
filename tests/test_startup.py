from unittest.mock import patch, MagicMock

from src.sync_logic import perform_leaguepedia_sync
from src.scheduler import (
    start_scheduler,
)


def test_start_scheduler_adds_jobs_with_replace_existing():
    """
    Tests that start_scheduler calls add_job with replace_existing=True
    to prevent conflicts on subsequent startups.
    """
    mock_scheduler = MagicMock()
    mock_scheduler.running = False

    # Since perform_leaguepedia_sync is now imported locally within
    # start_scheduler, we need to patch it in the scheduler module's context.
    with patch("src.scheduler.scheduler", mock_scheduler), patch(
        "src.scheduler.perform_leaguepedia_sync",
        new=perform_leaguepedia_sync,
        create=True,
    ):
        # Call the function that configures and starts the scheduler
        start_scheduler()

        # Verify that the jobs were added with replace_existing=True
        calls = mock_scheduler.add_job.call_args_list
        assert any(
            c.kwargs.get("id") == "sync_all_tournaments_job"
            and c.kwargs.get("replace_existing") is True
            for c in calls
        )
        assert any(
            c.kwargs.get("id") == "schedule_live_polling_job"
            and c.kwargs.get("replace_existing") is True
            for c in calls
        )

        # Verify that the scheduler was started
        mock_scheduler.start.assert_called_once()

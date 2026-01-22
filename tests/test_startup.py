from unittest.mock import patch, MagicMock, AsyncMock
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

    # Since `perform_pandascore_sync` is imported locally within
    # `start_scheduler`, avoid importing it here at collection time and
    # patch the symbol in the scheduler module with an AsyncMock instead.
    with patch("src.scheduler.scheduler", mock_scheduler), patch(
        "src.scheduler.perform_pandascore_sync",
        new=AsyncMock(),
        create=True,
    ):
        # Call the function that configures and starts the scheduler
        start_scheduler()

        # Verify that the jobs were added with replace_existing=True
        calls = mock_scheduler.add_job.call_args_list
        assert any(
            c.kwargs.get("id") == "sync_pandascore_job"
            and c.kwargs.get("replace_existing") is True
            for c in calls
        )

        # 'schedule_live_polling_job' was removed in refactor

        assert any(
            c.kwargs.get("id") == "poll_running_matches_job"
            and c.kwargs.get("replace_existing") is True
            for c in calls
        )

        # Verify that the scheduler was started
        mock_scheduler.start.assert_called_once()

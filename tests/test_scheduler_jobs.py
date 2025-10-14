import pytest
import pickle
from unittest.mock import AsyncMock, Mock, patch, mock_open
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine

from src.commands.sync_leaguepedia import perform_leaguepedia_sync


@pytest.fixture
def jobstore(tmp_path):
    """Fixture to create a temporary SQLAlchemyJobStore."""
    db_path = tmp_path / "test_jobs.db"
    engine = create_engine(f"sqlite:///{db_path}")
    store = SQLAlchemyJobStore(engine=engine)
    yield store
    store.shutdown()


@pytest.mark.asyncio
async def test_perform_leaguepedia_sync_is_picklable(jobstore):
    """
    Asserts that the main sync job function can be serialized by pickle,
    which is a requirement for APScheduler's SQLAlchemyJobStore.
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_jobstore(jobstore, "default")
    scheduler.start(paused=True)  # Start scheduler to initialize event loop
    try:
        scheduler.add_job(
            func=perform_leaguepedia_sync,
            trigger="interval",
            hours=1,
            id="test_job",
        )
    except (pickle.PicklingError, TypeError) as e:
        pytest.fail(f"Job function is not picklable: {e}")
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
@patch("src.commands.sync_leaguepedia.schedule_reminders", new_callable=AsyncMock)
@patch("src.commands.sync_leaguepedia.get_async_session")
@patch(
    "src.commands.sync_leaguepedia.open",
    mock_open(read_data='["Worlds 2025"]'),
)
@patch("src.leaguepedia_client.leaguepedia_client.fetch_upcoming_matches")
async def test_perform_leaguepedia_sync_logic(
    mock_fetch_matches, mock_get_session, mock_schedule_reminders
):
    """
    Tests the core logic of the sync function with the new cargo query,
    ensuring it calls the correct client methods and database operations.
    """
    # Arrange
    mock_db_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_db_session

    # Mock the DB calls to simulate a new contest and teams
    mock_contest = Mock()
    mock_contest.id = 1
    mock_db_session.exec.return_value.first.return_value = (
        None  # No existing contest
    )

    # Mock the return value for upsert_match to be a tuple (match, time_changed)
    mock_match = Mock()
    mock_upsert_match_return_value = (mock_match, True)

    with patch(
        "src.commands.sync_leaguepedia.upsert_contest",
        return_value=mock_contest,
    ) as mock_upsert_contest, patch(
        "src.commands.sync_leaguepedia.upsert_team", new_callable=AsyncMock
    ) as mock_upsert_team, patch(
        "src.commands.sync_leaguepedia.upsert_match",
        return_value=mock_upsert_match_return_value,
    ) as mock_upsert_match:

        # Mock the API response
        mock_fetch_matches.return_value = [
            {
                "Name": "Worlds 2025",
                "OverviewPage": "Worlds_2025",
                "DateTime UTC": "2025-10-13T18:00:00Z",
                "Team1": "Team A",
                "Team2": "Team B",
                "MatchId": "12345",
            }
        ]

        # Act
        summary = await perform_leaguepedia_sync()

        # Assert
        assert summary is not None
        mock_fetch_matches.assert_awaited_once_with("Worlds 2025")

        # Verify that upsert functions were called with correct data
        expected_start_date = datetime(2025, 10, 13, 18, 0, tzinfo=timezone.utc)
        expected_end_date = datetime(2025, 10, 13, 18, 0, tzinfo=timezone.utc)
        mock_upsert_contest.assert_awaited_once_with(
            mock_db_session,
            {
                "leaguepedia_id": "Worlds_2025",
                "name": "Worlds 2025",
                "start_date": expected_start_date,
                "end_date": expected_end_date,
            },
        )
        assert mock_upsert_team.call_count == 2
        mock_upsert_match.assert_awaited_once()

        assert summary["contests"] == 1
        assert summary["matches"] == 1
        assert summary["teams"] == 2
        mock_db_session.commit.assert_awaited_once()
        mock_schedule_reminders.assert_awaited_once_with(mock_match)

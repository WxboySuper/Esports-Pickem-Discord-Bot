import pytest
import pickle
from unittest.mock import AsyncMock, Mock, patch, mock_open

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
@patch("src.commands.sync_leaguepedia.aiohttp.ClientSession")
@patch("src.commands.sync_leaguepedia.get_async_session")
@patch(
    "src.commands.sync_leaguepedia.open",
    mock_open(read_data='["LCS 2024 Summer", "LEC 2024 Summer"]'),
)
async def test_perform_leaguepedia_sync_logic(
    mock_get_session, mock_client_session
):
    """
    Tests the core logic of the sync function, ensuring it calls the
    correct client methods and database operations.
    """
    # Arrange
    mock_db_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_db_session

    # Configure the mock for session.exec(...) to return a result object
    # whose .first() method returns a non-async Mock or None.
    result_mock = Mock()
    result_mock.first.return_value = None  # Simulate contest not found
    mock_db_session.exec.return_value = result_mock

    mock_http_session = AsyncMock()
    mock_client_session.return_value.__aenter__.return_value = (
        mock_http_session
    )

    mock_leaguepedia_client = AsyncMock()
    # Mock the return values of the client methods
    mock_leaguepedia_client.get_tournament_by_slug.return_value = {
        "Name": "LCS 2024 Summer",
        "DateStart": "2024-06-15",
        "DateEnd": "2024-09-01",
    }
    mock_leaguepedia_client.get_matches_for_tournament.return_value = []
    # Patch the client instantiation to return our mock
    with patch(
        "src.commands.sync_leaguepedia.LeaguepediaClient",
        return_value=mock_leaguepedia_client,
    ):
        # Act
        summary = await perform_leaguepedia_sync()

    # Assert
    assert summary is not None
    assert summary["contests"] > 0
    mock_db_session.commit.assert_awaited_once()
    assert mock_leaguepedia_client.get_tournament_by_slug.call_count == 2

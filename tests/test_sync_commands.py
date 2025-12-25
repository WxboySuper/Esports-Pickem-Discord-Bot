import json
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from src.commands.configure_sync import ConfigureSync
from src.commands.sync_leaguepedia import SyncLeaguepedia
from tests.testing_utils import (
    setup_test_db,
    teardown_test_db,
    get_test_async_session,
)


# Mock bot and interaction
class MockBot:
    def __init__(self):
        self.cogs = {}

    async def add_cog(self, cog):
        self.cogs[cog.__class__.__name__] = cog


class MockInteraction:
    def __init__(self):
        self.response = MagicMock()
        self.response.send_message = AsyncMock()
        self.response.defer = AsyncMock()
        self.followup = MagicMock()
        self.followup.send = AsyncMock()


@pytest_asyncio.fixture(scope="module", autouse=True)
async def db_setup_teardown():
    """
    Set up the test database for the module and tear it down after tests complete.
    
    Pytest async fixture that performs database setup before the module's tests run, yields control to execute the tests, and performs database teardown after the tests finish. Intended for module-scoped, autouse usage.
    """
    await setup_test_db()
    yield
    await teardown_test_db()


@pytest_asyncio.fixture(autouse=True)
async def test_session():
    """Provides a clean test database session for each test."""
    async with get_test_async_session() as session:
        yield session


@pytest.fixture
def mock_bot():
    return MockBot()


@pytest.fixture
def mock_interaction():
    return MockInteraction()


@pytest.fixture
def temp_config_file(tmp_path):
    """Creates a temporary config file for tests."""
    config_path = tmp_path / "tournaments.json"
    with open(config_path, "w") as f:
        json.dump([], f)
    return config_path


@pytest.mark.asyncio
async def test_configure_sync_add_remove_list(
    mock_bot, mock_interaction, temp_config_file
):
    """Tests the full add/remove/list flow of the configure-sync command."""
    with patch("src.commands.configure_sync.CONFIG_PATH", temp_config_file):
        cog = ConfigureSync(mock_bot)

        # Add a tournament
        await cog.add_tournament.callback(
            cog, mock_interaction, slug="LCS_2024_Summer"
        )
        mock_interaction.response.send_message.assert_called_with(
            "Successfully added `LCS_2024_Summer` to the sync list.",
            ephemeral=True,
        )

        # List tournaments
        await cog.list_tournaments.callback(cog, mock_interaction)
        assert (
            "LCS_2024_Summer"
            in mock_interaction.response.send_message.call_args[1][
                "embed"
            ].description
        )

        # Remove tournament
        await cog.remove_tournament.callback(
            cog, mock_interaction, slug="LCS_2024_Summer"
        )
        mock_interaction.response.send_message.assert_called_with(
            "Successfully removed `LCS_2024_Summer` from the sync list.",
            ephemeral=True,
        )


@pytest.mark.asyncio
@patch("src.commands.sync_leaguepedia.perform_leaguepedia_sync")
async def test_sync_leaguepedia_command(
    mock_perform_sync, mock_bot, mock_interaction
):
    """Tests the main sync-leaguepedia command."""
    # Arrange
    mock_perform_sync.return_value = {
        "contests": 1,
        "matches": 5,
        "teams": 10,
    }
    cog = SyncLeaguepedia(mock_bot)

    # Act
    await cog.sync_leaguepedia.callback(cog, mock_interaction)

    # Assert
    mock_interaction.response.defer.assert_called_once_with(
        ephemeral=True, thinking=True
    )
    mock_perform_sync.assert_awaited_once()
    mock_interaction.followup.send.assert_called_once()

    # Check the content of the success message
    call_args = mock_interaction.followup.send.call_args[0][0]
    assert "Leaguepedia sync complete!" in call_args
    assert "Upserted 1 contests." in call_args
    assert "Upserted 5 matches." in call_args
    assert "Upserted 10 teams." in call_args
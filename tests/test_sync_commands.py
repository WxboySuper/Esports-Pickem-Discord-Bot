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
    """Module-level fixture to set up and tear down the test database."""
    await setup_test_db()
    yield
    teardown_test_db()


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
@patch("src.commands.sync_leaguepedia.LeaguepediaClient")
async def test_sync_leaguepedia_command(
    MockLeaguepediaClient, mock_bot, mock_interaction, temp_config_file
):
    """Tests the main sync-leaguepedia command."""
    # Setup mock client
    mock_client_instance = MockLeaguepediaClient.return_value
    mock_client_instance.get_tournament_by_slug = AsyncMock(
        return_value={
            "Name": "LCS",
            "DateStart": "2024-01-01",
            "DateEnd": "2024-12-31",
        }
    )
    mock_client_instance.get_matches_for_tournament = AsyncMock(
        return_value=[
            {
                "MatchId": "1",
                "Team1": "Team A",
                "Team2": "Team B",
                "DateTime_UTC": "2024-05-05T12:00:00Z",
            }
        ]
    )

    async def mock_get_team(team_name):
        if team_name == "Team A":
            return {"Name": "Team A", "Image": "a.png", "Roster": "[]"}
        if team_name == "Team B":
            return {"Name": "Team B", "Image": "b.png", "Roster": "[]"}
        return {}

    mock_client_instance.get_team = AsyncMock(side_effect=mock_get_team)

    # Setup config file
    with open(temp_config_file, "w") as f:
        json.dump(["LCS_2024_Summer"], f)

    with patch(
        "src.commands.sync_leaguepedia.CONFIG_PATH", temp_config_file
    ), patch(
        "src.commands.sync_leaguepedia.get_async_session",
        get_test_async_session,
    ):

        cog = SyncLeaguepedia(mock_bot)
        await cog.sync_leaguepedia.callback(cog, mock_interaction)

        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "Leaguepedia sync complete!" in call_args
        assert "Upserted 1 contests." in call_args
        assert "Upserted 1 matches." in call_args
        assert "Upserted 2 teams." in call_args

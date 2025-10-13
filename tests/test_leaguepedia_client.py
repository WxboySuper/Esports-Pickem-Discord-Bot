import pytest
import pytest_asyncio
from aiohttp import ClientSession
from unittest.mock import MagicMock, AsyncMock

from src.leaguepedia_client import LeaguepediaClient


@pytest_asyncio.fixture
async def mock_aiohttp_session():
    """Fixture for a mocked aiohttp ClientSession."""
    session = MagicMock(spec=ClientSession)
    session.get = MagicMock()
    return session


@pytest.fixture
def leaguepedia_client(mock_aiohttp_session):
    """Fixture for a LeaguepediaClient with a mocked session."""
    return LeaguepediaClient(session=mock_aiohttp_session)


@pytest.mark.asyncio
async def test_get_tournament_by_slug(
    leaguepedia_client, mock_aiohttp_session
):
    """Tests fetching a tournament by slug."""
    mock_response = {
        "cargoquery": [
            {
                "title": {
                    "Name": "LCS 2024 Summer",
                    "DateStart": "2024-06-15",
                    "DateEnd": "2024-09-08",
                }
            }
        ]
    }
    # Configure the async context manager mock
    async_mock = MagicMock()
    async_mock.__aenter__.return_value.json = AsyncMock(
        return_value=mock_response
    )
    async_mock.__aenter__.return_value.raise_for_status = MagicMock()
    mock_aiohttp_session.get.return_value = async_mock

    slug = "LCS/2024_Season/Summer_Season"
    result = await leaguepedia_client.get_tournament_by_slug(slug)

    assert result["Name"] == "LCS 2024 Summer"
    mock_aiohttp_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_matches_for_tournament(
    leaguepedia_client, mock_aiohttp_session
):
    """Tests fetching matches for a tournament."""
    mock_response = {
        "cargoquery": [
            {
                "title": {
                    "MatchId": "123",
                    "Team1": "Team A",
                    "Team2": "Team B",
                }
            },
            {
                "title": {
                    "MatchId": "124",
                    "Team1": "Team C",
                    "Team2": "Team D",
                }
            },
        ]
    }
    async_mock = MagicMock()
    async_mock.__aenter__.return_value.json = AsyncMock(
        return_value=mock_response
    )
    async_mock.__aenter__.return_value.raise_for_status = MagicMock()
    mock_aiohttp_session.get.return_value = async_mock

    slug = "LCS/2024_Season/Summer_Season"
    result = await leaguepedia_client.get_matches_for_tournament(slug)

    assert len(result) == 2
    assert result[0]["MatchId"] == "123"
    mock_aiohttp_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_team(leaguepedia_client, mock_aiohttp_session):
    """Tests fetching a team by name."""
    mock_response = {
        "cargoquery": [
            {
                "title": {
                    "Name": "Team Liquid",
                    "Image": "tl.png",
                    "Roster": "Player1, Player2",
                }
            }
        ]
    }
    async_mock = MagicMock()
    async_mock.__aenter__.return_value.json = AsyncMock(
        return_value=mock_response
    )
    async_mock.__aenter__.return_value.raise_for_status = MagicMock()
    mock_aiohttp_session.get.return_value = async_mock

    team_name = "Team Liquid"
    result = await leaguepedia_client.get_team(team_name)

    assert result["Name"] == "Team Liquid"
    mock_aiohttp_session.get.assert_called_once()

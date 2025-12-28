import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from src.commands.contest import Contest
from src.models import Contest as ContestModel


@pytest.fixture
def mock_interaction():
    """Fixture for a mock discord.Interaction."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 12345
    return interaction


@pytest.mark.asyncio
@patch("src.commands.contest.ContestModal", autospec=True)
async def test_contest_create_command_sends_modal(
    mock_contest_modal, mock_interaction
):
    """Test that the /contest create command sends the ContestModal."""
    # Arrange
    contest_command = Contest()

    # Act
    await contest_command.create.callback(contest_command, mock_interaction)

    # Assert
    mock_contest_modal.assert_called_once_with()
    mock_interaction.response.send_modal.assert_called_once_with(
        mock_contest_modal.return_value
    )


@pytest.mark.asyncio
@patch("src.commands.contest.create_contest")
@patch("src.commands.contest.get_session")
async def test_contest_modal_on_submit(
    mock_get_session,
    mock_create_contest,
    mock_interaction,
):
    """Test the ContestModal's on_submit method."""
    # Arrange
    from src.commands.contest import ContestModal

    modal = ContestModal()
    modal.name = MagicMock()
    modal.name.value = "Test Contest"
    modal.start_date = MagicMock()
    modal.start_date.value = "2025-01-01"
    modal.end_date = MagicMock()
    modal.end_date.value = "2025-01-31"

    mock_session = MagicMock()
    mock_get_session.return_value.__enter__.return_value = mock_session
    created_contest = ContestModel(id=1, name="Test Contest")
    mock_create_contest.return_value = created_contest

    # Act
    await modal.on_submit(mock_interaction)

    # Assert
    mock_create_contest.assert_called_once_with(
        mock_session,
        {
            "name": "Test Contest",
            "start_date": ANY,
            "end_date": ANY,
        },
    )
    mock_interaction.response.send_message.assert_called_once_with(
        "Contest 'Test Contest' created with ID 1",
        ephemeral=True,
    )
    mock_get_session.return_value.__exit__.assert_called_once()

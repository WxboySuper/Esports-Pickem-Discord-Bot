import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.commands.matches import upload

# A minimal, valid CSV for testing, matching the new expected headers
VALID_CSV = (
    "team1,team2,scheduled_time\n"
    "Team A,Team B,2025-01-01T12:00:00\n"
    "Team C,Team D,2025-01-02T15:30:00\n"
)

# CSV with a missing column
INVALID_CSV_MISSING_COLUMN = (
    "team1,scheduled_time\n" "Team A,2025-01-01T12:00:00\n"
)

# CSV with an invalid date format
INVALID_CSV_BAD_DATE = (
    "team1,team2,scheduled_time\n" "Team A,Team B,2025/01/01 12:00\n"
)

# CSV with leaguepedia_id provided
VALID_CSV_WITH_ID = (
    "team1,team2,scheduled_time,leaguepedia_id\n"
    "Team A,Team B,2025-01-01T12:00:00,custom-id-123\n"
)


@pytest.fixture
def mock_interaction():
    """Fixture for a mock discord.Interaction."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = 12345
    interaction.user.name = "TestAdmin"
    return interaction


@pytest.mark.asyncio
@patch("src.commands.matches.get_session")
@patch("src.commands.matches.crud")
async def test_upload_command_valid_csv(
    mock_crud, mock_get_session, mock_interaction
):
    # Arrange
    attachment = AsyncMock(spec=discord.Attachment)
    attachment.read.return_value = VALID_CSV.encode("utf-8")

    mock_contest = MagicMock()
    mock_contest.name = "Test Contest"
    mock_crud.get_contest_by_id.return_value = mock_contest
    mock_session = mock_get_session.return_value.__enter__.return_value

    # Act
    await upload.callback(
        mock_interaction, contest_id=1, attachment=attachment
    )

    # Assert
    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    mock_crud.get_contest_by_id.assert_called_once_with(mock_session, 1)

    mock_crud.bulk_create_matches.assert_called_once()
    args, _ = mock_crud.bulk_create_matches.call_args
    session_arg, matches_data = args

    assert len(matches_data) == 2
    assert matches_data[0]["team1"] == "Team A"
    assert matches_data[0]["leaguepedia_id"].startswith(
        "manual-1-Team A-Team B-"
    )
    assert matches_data[0]["scheduled_time"] == datetime.fromisoformat(
        "2025-01-01T12:00:00"
    )

    mock_interaction.followup.send.assert_called_once_with(
        "Successfully uploaded 2 matches for 'Test Contest'.",
        ephemeral=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "csv_content, expected_error_part",
    [
        (INVALID_CSV_MISSING_COLUMN, "Invalid data or format. 'team2'"),
        (INVALID_CSV_BAD_DATE, "Invalid data or format."),
    ],
)
async def test_upload_command_invalid_csv(
    mock_interaction,
    csv_content,
    expected_error_part,
):
    # Use context managers for patching to reduce function args
    """
        Verifies that upload.callback responds with an error and does not
    create matches when given invalid CSV input.

        This test patches the matches CRUD layer and session provider, supplies
    a mocked Attachment containing the provided CSV content, invokes
    upload.callback, and asserts that a follow-up error message containing
    `expected_error_part` was sent and that no matches were created.

    Parameters:
                mock_interaction: Mocked discord.Interaction with deferred and
        followup behaviors.
                csv_content (str): CSV text to feed to the attachment;
        intentionally invalid for the test case.
                expected_error_part (str): Substring expected to appear in the
        error message sent to the interaction.
    """
    with patch("src.commands.matches.crud") as mock_crud, patch(
        "src.commands.matches.get_session"
    ):
        # Arrange
        attachment = AsyncMock(spec=discord.Attachment)
        attachment.read.return_value = csv_content.encode("utf-8")

        mock_contest = MagicMock()
        mock_contest.name = "Test Contest"
        mock_crud.get_contest_by_id.return_value = mock_contest

        # Act
        await upload.callback(
            mock_interaction, contest_id=1, attachment=attachment
        )

        # Assert
        mock_interaction.followup.send.assert_called_once()
        args, _ = mock_interaction.followup.send.call_args
        assert expected_error_part in args[0]
        mock_crud.bulk_create_matches.assert_not_called()


@pytest.mark.asyncio
@patch("src.commands.matches.get_session")
@patch("src.commands.matches.crud")
async def test_upload_command_with_leaguepedia_id(
    mock_crud, mock_get_session, mock_interaction
):
    # Arrange
    attachment = AsyncMock(spec=discord.Attachment)
    attachment.read.return_value = VALID_CSV_WITH_ID.encode("utf-8")

    mock_contest = MagicMock()
    mock_contest.name = "Test Contest"
    mock_crud.get_contest_by_id.return_value = mock_contest

    # Act
    await upload.callback(
        mock_interaction, contest_id=1, attachment=attachment
    )

    # Assert
    mock_crud.bulk_create_matches.assert_called_once()
    args, _ = mock_crud.bulk_create_matches.call_args
    _, matches_data = args

    assert len(matches_data) == 1
    assert matches_data[0]["leaguepedia_id"] == "custom-id-123"

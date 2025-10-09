import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch

from src.commands.match import Match as MatchCommand

# A minimal, valid CSV for testing
VALID_CSV = (
    "match_datetime,team_a,team_b\n"
    "2025-01-01T12:00:00,Team A,Team B\n"
    "2025-01-02T15:30:00,Team C,Team D\n"
)

# CSV with a missing column
INVALID_CSV_MISSING_COLUMN = (
    "match_datetime,team_a\n"
    "2025-01-01T12:00:00,Team A\n"
)

# CSV with an invalid date format
INVALID_CSV_BAD_DATE = (
    "match_datetime,team_a,team_b\n"
    "2025/01/01 12:00,Team A,Team B\n"
)

# CSV with an empty team name
INVALID_CSV_EMPTY_TEAM = (
    "match_datetime,team_a,team_b\n"
    "2025-01-01T12:00:00,,Team B\n"
)


@pytest.mark.asyncio
@patch("src.commands.match.get_session")
@patch("src.commands.match.get_contest_by_id")
@patch("src.commands.match.bulk_create_matches")
@patch("src.commands.match.ADMIN_IDS", [12345])
async def test_upload_command_valid_csv(
    mock_bulk_create, mock_get_contest, mock_get_session
):
    # Arrange
    command = MatchCommand()
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345
    attachment = AsyncMock(spec=discord.Attachment)
    attachment.read.return_value = VALID_CSV.encode("utf-8")

    mock_get_contest.return_value = True  # Contest exists

    # Act
    await command.upload.callback(command, interaction, contest_id=1, attachment=attachment)

    # Assert
    interaction.response.send_message.assert_called_once_with(
        "Successfully uploaded 2 matches to contest 1.",
        ephemeral=True,
    )
    mock_bulk_create.assert_called_once()
    args, _ = mock_bulk_create.call_args
    matches_data = args[1]
    assert len(matches_data) == 2
    assert matches_data[0]["team1"] == "Team A"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "csv_content, expected_error_part",
    [
        (INVALID_CSV_MISSING_COLUMN, "Invalid data - 'team_b'"),
        (INVALID_CSV_BAD_DATE, "Invalid data"),
        (INVALID_CSV_EMPTY_TEAM, "team_a and team_b cannot be empty"),
    ],
)
@patch("src.commands.match.get_session")
@patch("src.commands.match.get_contest_by_id")
@patch("src.commands.match.bulk_create_matches")
@patch("src.commands.match.ADMIN_IDS", [12345])
async def test_upload_command_invalid_csv(
    mock_bulk_create,
    mock_get_contest,
    mock_get_session,
    csv_content,
    expected_error_part,
):
    # Arrange
    command = MatchCommand()
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 12345
    attachment = AsyncMock(spec=discord.Attachment)
    attachment.read.return_value = csv_content.encode("utf-8")

    mock_get_contest.return_value = True  # Contest exists

    # Act
    await command.upload.callback(command, interaction, contest_id=1, attachment=attachment)

    # Assert
    interaction.response.send_message.assert_called_once()
    args, _ = interaction.response.send_message.call_args
    assert expected_error_part in args[0]
    mock_bulk_create.assert_not_called()
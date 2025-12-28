import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import discord

from src.commands import picks
from src.models import Match, Pick, Result, User, Contest


@pytest.fixture
def mock_interaction():
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = 123
    interaction.user.name = "TestUser"
    interaction.user.display_name = "TestUser"
    interaction.user.avatar.url = "http://example.com/avatar.png"
    return interaction


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.mark.asyncio
@patch("src.commands.picks.get_session")
@patch("src.commands.picks.crud.get_user_by_discord_id")
async def test_view_history_no_picks(
    mock_get_user, mock_get_session, mock_interaction, mock_session
):
    mock_get_session.return_value.__enter__.return_value = mock_session
    mock_get_user.return_value = User(
        id=1, discord_id="123", username="TestUser"
    )

    # Mock empty result
    mock_session.exec.return_value.all.return_value = []

    await picks.view_history.callback(mock_interaction)

    mock_interaction.response.send_message.assert_called_with(
        "You have no resolved picks.", ephemeral=True
    )


def _setup_history_test_data(user):
    # Create mock data
    contest = Contest(
        id=1,
        leaguepedia_id="contest-1",
        name="Test Tournament",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    # Match 1: User picked Team A, Team A won (Correct)
    match1 = Match(
        id=1,
        leaguepedia_id="match-1",
        contest_id=contest.id,
        team1="Team A",
        team2="Team B",
        scheduled_time=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
    )
    match1.result = Result(match_id=match1.id, winner="Team A", score="2-0")

    pick1 = Pick(
        user_id=user.id,
        contest_id=contest.id,
        match_id=match1.id,
        chosen_team="Team A",
        is_correct=True,
        status="correct",
    )
    pick1.match = match1

    # Match 2: User picked Team C, Team D won (Incorrect)
    match2 = Match(
        id=2,
        leaguepedia_id="match-2",
        contest_id=contest.id,
        team1="Team C",
        team2="Team D",
        scheduled_time=datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc),
    )
    match2.result = Result(match_id=match2.id, winner="Team D", score="1-2")

    pick2 = Pick(
        user_id=user.id,
        contest_id=contest.id,
        match_id=match2.id,
        chosen_team="Team C",
        is_correct=False,
        status="incorrect",
    )
    pick2.match = match2

    return [pick2, pick1]


@pytest.mark.asyncio
@patch("src.commands.picks.get_session")
@patch("src.commands.picks.crud.get_user_by_discord_id")
async def test_view_history_with_picks(
    mock_get_user, mock_get_session, mock_interaction, mock_session
):
    mock_get_session.return_value.__enter__.return_value = mock_session
    user = User(id=1, discord_id="123", username="TestUser")
    mock_get_user.return_value = user

    # Mock session return
    mock_session.exec.return_value.all.return_value = _setup_history_test_data(
        user
    )

    await picks.view_history.callback(mock_interaction)

    # Verify response
    assert mock_interaction.response.send_message.called
    _, kwargs = mock_interaction.response.send_message.call_args
    embed = kwargs["embed"]

    assert embed.title == "Your Pick History"
    assert len(embed.fields) == 2

    # Verify content of fields
    # Field 0 should be Match 2 (most recent)
    field0 = embed.fields[0]
    assert "Team C vs Team D" in field0.name
    assert "Your pick: **Team C**" in field0.value
    assert "Winner: Team D (1-2)" in field0.value
    assert "❌ Incorrect" in field0.value

    # Field 1 should be Match 1
    field1 = embed.fields[1]
    assert "Team A vs Team B" in field1.name
    assert "Your pick: **Team A**" in field1.value
    assert "Winner: Team A (2-0)" in field1.value
    assert "✅ Correct" in field1.value

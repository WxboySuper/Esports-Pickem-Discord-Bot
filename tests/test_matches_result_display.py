import pytest
import discord
from unittest.mock import MagicMock
from datetime import datetime, timezone
from src.commands.matches import create_matches_embed
from src.models import Match, Contest, Result


@pytest.mark.asyncio
async def test_create_matches_embed_with_result():
    # Arrange
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.display_name = "TestUser"
    interaction.user.avatar = None

    contest = Contest(name="Test Tournament")

    match_no_result = Match(
        team1="Team A",
        team2="Team B",
        scheduled_time=datetime(2025, 12, 26, 12, 0, tzinfo=timezone.utc),
        contest=contest,
    )

    match_with_result = Match(
        team1="Team C",
        team2="Team D",
        scheduled_time=datetime(2025, 12, 26, 15, 0, tzinfo=timezone.utc),
        contest=contest,
    )
    result = Result(winner="Team C", score="2-0")
    match_with_result.result = result

    matches = [match_no_result, match_with_result]

    # Act
    embed = await create_matches_embed("Test Matches", matches, interaction)

    # Assert
    assert len(embed.fields) == 2

    # Field 0: No result
    assert embed.fields[0].name == "Team A vs Team B"
    assert "Result" not in embed.fields[0].value

    # Field 1: With result
    assert embed.fields[1].name == "Team C vs Team D"
    assert "Result: Team C won (2-0)" in embed.fields[1].value


@pytest.mark.asyncio
async def test_create_matches_embed_no_matches():
    # Arrange
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.display_name = "TestUser"
    interaction.user.avatar = None
    matches = []

    # Act
    embed = await create_matches_embed("Empty", matches, interaction)

    # Assert
    assert embed.description == "No matches found."
    assert len(embed.fields) == 0

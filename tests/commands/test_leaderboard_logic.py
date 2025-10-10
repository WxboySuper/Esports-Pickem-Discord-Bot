import pytest
from unittest.mock import MagicMock

from src.commands.leaderboard import (
    get_leaderboard_data,
    create_leaderboard_embed,
)
from src.models import User


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def mock_interaction():
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.display_name = "TestUser"
    interaction.user.avatar.url = "http://example.com/avatar.png"
    return interaction


def create_mock_user(discord_id, username):
    user = User(id=int(discord_id), discord_id=str(discord_id), username=username)
    return user


@pytest.mark.asyncio
async def test_get_leaderboard_data_accuracy(mock_session):
    # --- Test Data ---
    user1 = create_mock_user(1, "UserOne")
    user2 = create_mock_user(2, "UserTwo")
    user4 = create_mock_user(4, "UserFour")  # Perfect accuracy

    mock_session.exec.return_value.all.return_value = [
        (user4, 100.0, 5),  # 5/5 correct
        (user1, 80.0, 8),  # 8/10 correct
        (user2, 75.0, 6),  # 6/8 correct
    ]

    # --- Call the function ---
    data = await get_leaderboard_data(session=mock_session)

    # --- Assertions ---
    assert len(data) == 3
    # User4 should be first (100% accuracy)
    assert data[0][0].username == "UserFour"
    assert data[0][1] == 100.0
    # User1 should be second (80% accuracy)
    assert data[1][0].username == "UserOne"
    assert data[1][1] == 80.0
    # User2 should be third (75% accuracy)
    assert data[2][0].username == "UserTwo"
    assert data[2][1] == 75.0


@pytest.mark.asyncio
async def test_get_leaderboard_data_count_based(mock_session):
    # --- Test Data ---
    user1 = create_mock_user(1, "UserOne")
    user2 = create_mock_user(2, "UserTwo")

    mock_session.exec.return_value.all.return_value = [
        (user1, 10),  # 10 correct picks
        (user2, 7),  # 7 correct picks
    ]

    # --- Call the function for a weekly leaderboard ---
    data = await get_leaderboard_data(session=mock_session, days=7)

    # --- Assertions ---
    assert len(data) == 2
    assert data[0] == (user1, 10)
    assert data[1] == (user2, 7)


@pytest.mark.asyncio
async def test_create_leaderboard_embed_accuracy(mock_interaction):
    # --- Test Data ---
    user1 = create_mock_user(1, "UserOne")
    user2 = create_mock_user(2, "UserTwo")
    leaderboard_data = [(user1, 95.5, 19), (user2, 88.888, 16)]

    # --- Call the function ---
    embed = await create_leaderboard_embed(
        "Global Accuracy", leaderboard_data, mock_interaction
    )

    # --- Assertions ---
    assert "Global Accuracy" in embed.title
    assert "**1.** UserOne - `95.50%` accuracy" in embed.description
    assert "**2.** UserTwo - `88.89%` accuracy" in embed.description


@pytest.mark.asyncio
async def test_create_leaderboard_embed_count_based(mock_interaction):
    # --- Test Data ---
    user1 = create_mock_user(1, "UserOne")
    user2 = create_mock_user(2, "UserTwo")
    user3 = create_mock_user(3, "UserThree")
    leaderboard_data = [(user1, 10), (user2, 5), (user3, 1)]

    # --- Call the function ---
    embed = await create_leaderboard_embed(
        "Weekly Winners", leaderboard_data, mock_interaction
    )

    # --- Assertions ---
    assert "Weekly Winners" in embed.title
    assert "**1.** UserOne - `10` correct picks" in embed.description
    assert "**2.** UserTwo - `5` correct picks" in embed.description
    assert "**3.** UserThree - `1` correct pick" in embed.description  # Singular

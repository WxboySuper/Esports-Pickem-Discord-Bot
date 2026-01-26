import pytest
from unittest.mock import AsyncMock
from discord import app_commands, Interaction
from src.commands.pick import pick_error


@pytest.mark.asyncio
async def test_pick_error_cooldown():
    # Arrange
    interaction = AsyncMock(spec=Interaction)
    interaction.response.send_message = AsyncMock()
    # Mock is_done to False by default
    interaction.response.is_done.return_value = False

    # But constructor is simple enough.
    # Cooldown(rate, per)
    cooldown = app_commands.Cooldown(1, 5.0)
    # discord.py 2.0+: CommandOnCooldown(cooldown, retry_after)
    error = app_commands.CommandOnCooldown(cooldown, 2.5)

    # Act
    await pick_error(interaction, error)

    # Assert
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "Slow down!" in args[0]
    assert "2.5s" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_pick_error_generic():
    # Arrange
    interaction = AsyncMock(spec=Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.response.is_done.return_value = False

    error = app_commands.AppCommandError("Generic error")

    # Act
    await pick_error(interaction, error)

    # Assert
    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "An error occurred" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_pick_error_generic_followup():
    # Arrange
    interaction = AsyncMock(spec=Interaction)
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()

    error = app_commands.AppCommandError("Generic error")

    # Act
    await pick_error(interaction, error)

    # Assert
    interaction.followup.send.assert_called_once()
    args, kwargs = interaction.followup.send.call_args
    assert "An error occurred" in args[0]
    assert kwargs.get("ephemeral") is True

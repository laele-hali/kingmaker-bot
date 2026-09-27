import asyncio
from unittest.mock import AsyncMock

import pytest

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.discord_calendar_commands import register_calendar_commands
from discord import app_commands


class EmptyRepository:
    def get(self, guild_id: int):
        return None

    def save(self, state):
        return state


class FakeTree:
    def __init__(self) -> None:
        self.commands = []

    def add_command(self, command) -> None:
        self.commands.append(command)


def test_calendar_command_group_is_guild_only_and_registers_subcommands() -> None:
    tree = FakeTree()
    group = register_calendar_commands(tree, CalendarService(EmptyRepository()))  # type: ignore[arg-type]

    assert isinstance(group, app_commands.Group)
    assert group.guild_only
    assert {command.name for command in group.commands} == {"date", "set", "advance", "level", "weather"}
    assert tree.commands == [group]


def test_date_command_handles_context_without_guild() -> None:
    group = register_calendar_commands(FakeTree(), CalendarService(EmptyRepository()))  # type: ignore[arg-type]
    command = group.get_command("date")
    interaction = AsyncMock()
    interaction.guild_id = None

    asyncio.run(command.callback(interaction))

    interaction.response.send_message.assert_awaited_once_with(
        "Calendar commands can only be used in a server.", ephemeral=True
    )

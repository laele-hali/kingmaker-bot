import asyncio
from unittest.mock import AsyncMock, Mock

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
    assert {command.name for command in group.commands} == {
        "date", "set", "advance", "level", "weather", "weather-gm", "predict"
    }
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


@pytest.mark.parametrize(
    ("command", "method", "args", "message"),
    [
        ("set", "set_date", (32, 3, 4710),
         "Enter a valid Golarion date with a positive year, a month from 1 to 12, "
         "and a day that exists in that month."),
        ("advance", "advance", (-1,), "Enter a positive whole number of days to advance."),
        ("level", "set_party_level", (21,), "Party level must be between 1 and 20."),
    ],
)
def test_validation_messages_do_not_forward_exception_text(command, method, args, message):
    service = Mock()
    getattr(service, method).side_effect = ValueError(
        "internal database state: check_dc=20 survival_total=19 is_false=True"
    )
    group = register_calendar_commands(FakeTree(), service)
    interaction = AsyncMock()
    interaction.guild_id = 111

    asyncio.run(group.get_command(command).callback(interaction, *args))

    interaction.response.send_message.assert_awaited_once_with(message, ephemeral=True)

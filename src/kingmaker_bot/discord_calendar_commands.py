"""Discord command adapter for campaign calendar operations."""

import discord
from discord import app_commands

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.calendar import CalendarDate

_CALENDAR_NOT_CONFIGURED = "No campaign calendar is configured for this server."
_GUILD_ONLY_MESSAGE = "Calendar commands can only be used in a server."


def format_calendar_date(date: CalendarDate) -> str:
    """Format the information supplied by the calendar domain model."""
    return f"{date.weekday}, {date.day} {date.month_name} {date.year} AR ({date.season})"


async def _guild_id_or_respond(interaction: discord.Interaction) -> int | None:
    if interaction.guild_id is None:
        await interaction.response.send_message(_GUILD_ONLY_MESSAGE, ephemeral=True)
        return None
    return interaction.guild_id


def register_calendar_commands(
    tree: app_commands.CommandTree,
    service: CalendarService,
) -> app_commands.Group:
    """Register a guild-only ``/calendar`` command group on a command tree."""
    group = app_commands.Group(
        name="calendar",
        description="View and manage this server's campaign calendar",
        guild_only=True,
    )

    @group.command(name="date", description="Show the current campaign date")
    async def date(interaction: discord.Interaction) -> None:
        guild_id = await _guild_id_or_respond(interaction)
        if guild_id is None:
            return

        state = service.get_campaign_state(guild_id)
        if state is None:
            response = _CALENDAR_NOT_CONFIGURED
        else:
            response = f"Current campaign date: {format_calendar_date(state.current_date)}"
        await interaction.response.send_message(response)

    @group.command(name="set", description="Set this server's campaign date")
    async def set_date(
        interaction: discord.Interaction,
        day: int,
        month: int,
        year: int,
    ) -> None:
        guild_id = await _guild_id_or_respond(interaction)
        if guild_id is None:
            return

        try:
            state = service.set_date(guild_id, day, month, year)
        except ValueError as error:
            await interaction.response.send_message(f"Invalid Golarion date: {error}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Campaign date set to {format_calendar_date(state.current_date)}."
        )

    @group.command(name="advance", description="Advance this server's campaign date")
    async def advance(interaction: discord.Interaction, days: int) -> None:
        guild_id = await _guild_id_or_respond(interaction)
        if guild_id is None:
            return

        try:
            state = service.advance(guild_id, days)
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        if state is None:
            response = _CALENDAR_NOT_CONFIGURED
        else:
            response = f"Campaign date advanced to {format_calendar_date(state.current_date)}."
        await interaction.response.send_message(response)

    tree.add_command(group)
    return group

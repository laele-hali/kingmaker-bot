"""Discord command adapter for campaign calendar operations."""

import re

import discord
from discord import app_commands

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.application.predict_weather_service import PredictWeatherService
from kingmaker_bot.discord_weather_formatter import format_weather
from kingmaker_bot.discord_prediction_formatter import format_prediction
from kingmaker_bot.prediction import (
    PredictionAlreadyAttemptedError,
    PredictionConditions,
)
from kingmaker_bot.weather import PROFILE_ID

_CALENDAR_NOT_CONFIGURED = "No campaign calendar is configured for this server."
_GUILD_ONLY_MESSAGE = "Calendar commands can only be used in a server."
_SURVIVAL_TOTAL_MESSAGE = "Survival check total must be an integer."


def format_calendar_date(date: CalendarDate) -> str:
    """Format the information supplied by the calendar domain model."""
    return f"{date.weekday}, {date.day} {date.month_name} {date.year} AR ({date.season})"


async def _guild_id_or_respond(interaction: discord.Interaction) -> int | None:
    if interaction.guild_id is None:
        await interaction.response.send_message(_GUILD_ONLY_MESSAGE, ephemeral=True)
        return None
    return interaction.guild_id


class PredictWeatherModal(discord.ui.Modal, title="Predict Weather"):
    """Collect a final Survival total, then delegate prediction to the service."""

    survival_total = discord.ui.TextInput(
        label="Survival check total",
        placeholder="Final total only; do not enter the die result",
        required=True,
        max_length=12,
    )

    def __init__(
        self,
        calendar_service: CalendarService,
        prediction_service: PredictWeatherService,
        conditions: PredictionConditions,
    ) -> None:
        super().__init__(timeout=300)
        self._calendar_service = calendar_service
        self._prediction_service = prediction_service
        self._conditions = conditions

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_total = self.survival_total.value.strip()
        if re.fullmatch(r"[+-]?\d+", raw_total) is None:
            await interaction.response.send_message(_SURVIVAL_TOTAL_MESSAGE, ephemeral=True)
            return
        try:
            total = int(raw_total)
        except ValueError:
            await interaction.response.send_message(_SURVIVAL_TOTAL_MESSAGE, ephemeral=True)
            return

        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message(_GUILD_ONLY_MESSAGE, ephemeral=True)
            return
        state = self._calendar_service.get_campaign_state(guild_id)
        if state is None:
            await interaction.response.send_message(_CALENDAR_NOT_CONFIGURED, ephemeral=True)
            return
        if state.party_level is None:
            await interaction.response.send_message(
                "No party level is configured. Ask the GM to set it with /calendar level <level>.",
                ephemeral=True,
            )
            return

        try:
            attempt = self._prediction_service.predict(
                guild_id=guild_id,
                user_id=interaction.user.id,
                current_date=state.current_date,
                party_level=state.party_level,
                survival_total=total,
                conditions=self._conditions,
            )
        except PredictionAlreadyAttemptedError:
            await interaction.response.send_message(
                "You have already attempted Predict Weather for this campaign date.",
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.response.send_message(
                "The prediction could not be completed. Please try again later.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(format_prediction(attempt), ephemeral=False)


def register_calendar_commands(
    tree: app_commands.CommandTree,
    service: CalendarService,
    weather_service: WeatherService | None = None,
    prediction_service: PredictWeatherService | None = None,
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

    @group.command(name="level", description="View or set this server's party level")
    async def level(interaction: discord.Interaction, level: int | None = None) -> None:
        guild_id = await _guild_id_or_respond(interaction)
        if guild_id is None:
            return
        if level is None:
            state = service.get_campaign_state(guild_id)
            if state is None:
                response = _CALENDAR_NOT_CONFIGURED
            elif state.party_level is None:
                response = "No party level is configured. Set one with /calendar level <level>."
            else:
                response = f"Configured party level: {state.party_level}."
        else:
            try:
                state = service.set_party_level(guild_id, level)
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            if state is None:
                response = _CALENDAR_NOT_CONFIGURED
            else:
                response = f"Party level set to {state.party_level}."
        await interaction.response.send_message(response)

    @group.command(name="weather", description="Reveal today's campaign weather")
    async def weather(interaction: discord.Interaction) -> None:
        guild_id = await _guild_id_or_respond(interaction)
        if guild_id is None:
            return
        state = service.get_campaign_state(guild_id)
        if state is None:
            await interaction.response.send_message(_CALENDAR_NOT_CONFIGURED)
            return
        if state.party_level is None:
            await interaction.response.send_message(
                "No party level is configured. Set one with /calendar level <level>."
            )
            return
        if weather_service is None:
            await interaction.response.send_message("Weather is temporarily unavailable.", ephemeral=True)
            return
        try:
            weather_service.get_or_generate(
                guild_id, state.current_date, state.party_level, PROFILE_ID
            )
            revealed = weather_service.reveal(guild_id, state.current_date, PROFILE_ID)
            if revealed is None:
                raise RuntimeError("canonical weather disappeared before reveal")
        except Exception:
            # Discord receives no database or engine details; application layers retain their errors.
            await interaction.response.send_message(
                "Weather could not be generated or loaded. Please try again later.", ephemeral=True
            )
            return
        await interaction.response.send_message(format_weather(revealed.weather))

    @group.command(name="predict", description="Predict weather for the coming day")
    @app_commands.choices(
        conditions=[
            app_commands.Choice(name="Good visibility / commanding view", value=PredictionConditions.COMMANDING_VIEW.value),
            app_commands.Choice(name="Normal conditions", value=PredictionConditions.NORMAL.value),
            app_commands.Choice(name="Poor visibility", value=PredictionConditions.POOR.value),
        ]
    )
    async def predict(
        interaction: discord.Interaction,
        conditions: app_commands.Choice[str],
    ) -> None:
        guild_id = await _guild_id_or_respond(interaction)
        if guild_id is None:
            return
        state = service.get_campaign_state(guild_id)
        if state is None:
            await interaction.response.send_message(_CALENDAR_NOT_CONFIGURED, ephemeral=True)
            return
        if state.party_level is None:
            await interaction.response.send_message(
                "No party level is configured. Ask the GM to set it with /calendar level <level>.",
                ephemeral=True,
            )
            return
        if prediction_service is None:
            await interaction.response.send_message(
                "Predict Weather is temporarily unavailable.", ephemeral=True
            )
            return
        try:
            selected_conditions = PredictionConditions(conditions.value)
        except ValueError:
            await interaction.response.send_message("Choose a valid prediction condition.", ephemeral=True)
            return
        await interaction.response.send_modal(
            PredictWeatherModal(service, prediction_service, selected_conditions)
        )

    tree.add_command(group)
    return group

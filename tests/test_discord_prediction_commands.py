import asyncio
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from discord import app_commands

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign import CampaignState
from kingmaker_bot.application.predict_weather_service import PredictWeatherService
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.database import (
    SQLiteCampaignStateRepository,
    SQLitePredictionRepository,
    SQLiteWeatherRepository,
)
from kingmaker_bot.discord_calendar_commands import (
    PredictWeatherModal,
    register_calendar_commands,
)
from kingmaker_bot.prediction import (
    DegreeOfSuccess,
    PredictionAlreadyAttemptedError,
    PredictionAttempt,
    PredictionConditions,
    WeatherForecast,
)
from kingmaker_bot.weather import PrecipitationType
from kingmaker_bot.weather import KingmakerStolenLandsProfile, PROFILE_ID, WeatherEngine
from kingmaker_bot.weather import HazardLevel, WeatherEvent, WeatherEventDefinition


class FakeTree:
    def add_command(self, command):
        self.group = command


class FakeCalendarService:
    def __init__(self, state):
        self.state = state
        self.guilds_read = []

    def get_campaign_state(self, guild_id):
        self.guilds_read.append(guild_id)
        return self.state

    def get(self, guild_id):
        self.guilds_read.append(guild_id)
        return self.state


class FakePredictionService:
    def __init__(self, attempt=None, error=None):
        self.attempt = attempt
        self.error = error
        self.calls = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.attempt


def make_attempt(
    current_date=CalendarDate(17, 3, 4710),
    conditions=PredictionConditions.NORMAL,
    total=20,
    degree=DegreeOfSuccess.SUCCESS,
    forecast=None,
):
    return PredictionAttempt(
        guild_id=123,
        user_id=456,
        campaign_date=current_date,
        forecast_date=current_date.advance(),
        profile_id="kingmaker_stolen_lands",
        survival_total=total,
        conditions=conditions,
        degree=degree,
        forecast=forecast or WeatherForecast(
            PrecipitationType.RAIN, None, False, None, 1
        ),
    )


def command_interaction(guild_id=123, user_id=456):
    interaction = AsyncMock()
    interaction.guild_id = guild_id
    interaction.user = SimpleNamespace(id=user_id)
    return interaction


def register(state, prediction_service):
    calendar = FakeCalendarService(state)
    group = register_calendar_commands(
        FakeTree(), CalendarService(calendar), prediction_service=prediction_service
    )
    return group


def open_modal(group, conditions=PredictionConditions.NORMAL):
    interaction = command_interaction()
    choice = app_commands.Choice(name="Normal conditions", value=conditions.value)
    asyncio.run(group.get_command("predict").callback(interaction, choice))
    interaction.response.send_modal.assert_awaited_once()
    return interaction.response.send_modal.await_args.args[0]


def submit(modal, value, guild_id=123, user_id=456):
    modal.survival_total._value = value
    interaction = command_interaction(guild_id, user_id)
    asyncio.run(modal.on_submit(interaction))
    return interaction


def test_predict_command_is_registered_with_user_facing_condition_choices():
    group = register(CampaignState(123, CalendarDate(17, 3, 4710), party_level=4), FakePredictionService())
    command = group.get_command("predict")

    assert command is not None
    choices = command._params["conditions"].choices
    assert [(choice.name, choice.value) for choice in choices] == [
        ("Good visibility / commanding view", PredictionConditions.COMMANDING_VIEW.value),
        ("Normal conditions", PredictionConditions.NORMAL.value),
        ("Poor visibility", PredictionConditions.POOR.value),
    ]
    assert all(not any(character.isdigit() for character in choice.name) for choice in choices)


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (None, "No campaign calendar is configured for this server."),
        (
            CampaignState(123, CalendarDate(17, 3, 4710)),
            "No party level is configured. Ask the GM to set it with /calendar level <level>.",
        ),
    ],
)
def test_missing_prerequisites_reply_ephemerally_without_modal_or_service_call(state, message):
    prediction = FakePredictionService()
    group = register(state, prediction)
    interaction = command_interaction()
    choice = app_commands.Choice(name="Normal conditions", value="normal")

    asyncio.run(group.get_command("predict").callback(interaction, choice))

    interaction.response.send_message.assert_awaited_once_with(message, ephemeral=True)
    interaction.response.send_modal.assert_not_awaited()
    assert prediction.calls == []


def test_modal_requires_a_final_integer_total_and_passes_selected_inputs():
    current = CalendarDate(17, 3, 4710)
    state = CampaignState(123, current, party_level=6)
    attempt = make_attempt(
        current_date=current,
        conditions=PredictionConditions.POOR,
        total=31,
        degree=DegreeOfSuccess.SUCCESS,
    )
    prediction = FakePredictionService(attempt)
    group = register(state, prediction)
    modal = open_modal(group, PredictionConditions.POOR)

    assert isinstance(modal, PredictWeatherModal)
    assert modal.title == "Predict Weather"
    assert modal.survival_total.to_component_dict()["label"] == "Survival check total"
    assert modal.survival_total.required
    assert "die result" in modal.survival_total.placeholder
    assert "dc" not in (
        modal.title + modal.survival_total.to_component_dict()["label"]
        + modal.survival_total.placeholder
    ).lower()

    interaction = submit(modal, "31")

    assert prediction.calls == [
        {
            "guild_id": 123,
            "user_id": 456,
            "current_date": current,
            "party_level": 6,
            "survival_total": 31,
            "conditions": PredictionConditions.POOR,
        }
    ]
    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is False


@pytest.mark.parametrize("value", ["", "twenty", "20.5"])
def test_non_integer_modal_input_is_ephemeral_and_does_not_call_service(value):
    prediction = FakePredictionService(make_attempt())
    modal = open_modal(
        register(CampaignState(123, CalendarDate(17, 3, 4710), party_level=4), prediction)
    )

    interaction = submit(modal, value)

    interaction.response.send_message.assert_awaited_once_with(
        "Survival check total must be an integer.", ephemeral=True
    )
    assert prediction.calls == []


def test_duplicate_attempt_reply_is_ephemeral_without_revealing_degree():
    prediction = FakePredictionService(error=PredictionAlreadyAttemptedError("duplicate"))
    modal = open_modal(
        register(CampaignState(123, CalendarDate(17, 3, 4710), party_level=4), prediction)
    )

    interaction = submit(modal, "30")

    response = interaction.response.send_message.await_args.args[0]
    assert response == "You have already attempted Predict Weather for this campaign date."
    assert "success" not in response.lower()
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True


def test_modal_submission_rechecks_campaign_prerequisites_ephemerally():
    prediction = FakePredictionService(make_attempt())
    calendar = FakeCalendarService(None)
    modal = PredictWeatherModal(CalendarService(calendar), prediction, PredictionConditions.NORMAL)
    interaction = submit(modal, "20")

    interaction.response.send_message.assert_awaited_once_with(
        "No campaign calendar is configured for this server.", ephemeral=True
    )
    assert prediction.calls == []


def test_calendar_client_passes_weather_and_prediction_services_to_registration(monkeypatch):
    from kingmaker_bot import discord_client

    received = {}

    def capture(tree, calendar_service, weather_service, prediction_service):
        received.update(
            calendar=calendar_service,
            weather=weather_service,
            prediction=prediction_service,
        )

    monkeypatch.setattr(discord_client, "register_calendar_commands", capture)
    campaign_repository = object()
    weather_service = object()
    prediction_service = object()

    discord_client.KingmakerClient(campaign_repository, weather_service, prediction_service)

    assert received["weather"] is weather_service
    assert received["prediction"] is prediction_service
    assert isinstance(received["calendar"], CalendarService)


def test_discord_prediction_keeps_canonical_weather_hidden_and_reuses_it(tmp_path):
    database = tmp_path / "discord-predict.sqlite3"
    current = CalendarDate(17, 3, 4710)
    campaigns = SQLiteCampaignStateRepository(database)
    campaigns.save(CampaignState(123, current, party_level=4))

    class CountingRolls:
        def __init__(self):
            self.values = iter((15, 1))
            self.count = 0

        def roll(self, sides):
            self.count += 1
            return next(self.values)

    dice = CountingRolls()
    weather_repository = SQLiteWeatherRepository(database)
    weather_service = WeatherService(
        weather_repository,
        {PROFILE_ID: WeatherEngine(KingmakerStolenLandsProfile(), dice)},
    )
    prediction_repository = SQLitePredictionRepository(database)
    prediction_service = PredictWeatherService(prediction_repository, weather_service, PROFILE_ID)
    group = register_calendar_commands(
        FakeTree(), CalendarService(campaigns), weather_service, prediction_service
    )
    predict_command = group.get_command("predict")
    choice = app_commands.Choice(name="Normal conditions", value="normal")

    async def make_prediction():
        invoke = command_interaction()
        await predict_command.callback(invoke, choice)
        modal = invoke.response.send_modal.await_args.args[0]
        modal.survival_total._value = "20"
        submit_interaction = command_interaction()
        await modal.on_submit(submit_interaction)
        return submit_interaction

    first = asyncio.run(make_prediction())
    assert first.response.send_message.await_args.kwargs["ephemeral"] is False
    assert dice.count == 2
    canonical = weather_repository.get(123, current.advance(), PROFILE_ID)
    assert canonical is not None
    assert canonical.revealed_at is None
    stored_attempt = prediction_repository.get(123, 456, current, PROFILE_ID)
    assert stored_attempt is not None

    later_weather = weather_service.get_or_generate(123, current.advance(), 4, PROFILE_ID)
    assert later_weather == canonical
    assert dice.count == 2

    duplicate = asyncio.run(make_prediction())
    assert duplicate.response.send_message.await_args.kwargs["ephemeral"] is True
    assert "already attempted" in duplicate.response.send_message.await_args.args[0]
    assert dice.count == 2
    assert prediction_repository.get(123, 456, current, PROFILE_ID) == stored_attempt


@pytest.mark.parametrize("conditions", list(PredictionConditions))
@pytest.mark.parametrize(
    ("degree", "offset"),
    [(DegreeOfSuccess.CRITICAL_SUCCESS, 11), (DegreeOfSuccess.SUCCESS, 1),
     (DegreeOfSuccess.FAILURE, -1), (DegreeOfSuccess.CRITICAL_FAILURE, -11)],
)
def test_all_resolved_forecasts_are_public_without_check_or_degree_details(conditions, degree, offset):
    total = conditions.dc + offset
    detailed = degree in (DegreeOfSuccess.CRITICAL_SUCCESS, DegreeOfSuccess.CRITICAL_FAILURE)
    forecast = (
        WeatherForecast(None, None, None, None, None)
        if degree is DegreeOfSuccess.FAILURE else
        WeatherForecast(
            PrecipitationType.NONE, None, True,
            WeatherEventDefinition(WeatherEvent.WINDSTORM, HazardLevel(exact=1)) if detailed else None,
            2 if detailed else 1,
            is_false=degree is DegreeOfSuccess.CRITICAL_FAILURE,
        )
    )
    attempt = make_attempt(conditions=conditions, total=total, degree=degree, forecast=forecast)
    prediction = FakePredictionService(attempt)
    modal = open_modal(
        register(CampaignState(123, CalendarDate(17, 3, 4710), party_level=4), prediction),
        conditions,
    )

    interaction = submit(modal, str(total))

    interaction.response.send_message.assert_awaited_once()
    response = interaction.response.send_message.await_args
    assert response.kwargs["ephemeral"] is False
    output = response.args[0]
    for secret in ("dc", "success", "failure", "false", "check total"):
        assert secret not in output.lower()
    assert str(total) not in re.findall(r"\b\d+\b", output)
    assert str(conditions.dc) not in re.findall(r"\b\d+\b", output)
    if degree is DegreeOfSuccess.FAILURE:
        assert "unable to obtain a useful forecast" in output
        assert "precipitation" not in output.lower()
    else:
        assert "No precipitation" in output
        assert ("Windstorm is expected" in output) is detailed


@pytest.mark.parametrize("error", [ValueError("DC 20 total 19"), RuntimeError("DC 30")])
def test_application_errors_are_private_and_do_not_expose_internal_details(error):
    prediction = FakePredictionService(error=error)
    modal = open_modal(
        register(CampaignState(123, CalendarDate(17, 3, 4710), party_level=4), prediction)
    )
    interaction = submit(modal, "19")
    interaction.response.send_message.assert_awaited_once_with(
        "The prediction could not be completed. Please try again later.", ephemeral=True
    )


@pytest.mark.parametrize("value", ["invalid", "normal"])
def test_invalid_conditions_and_unavailable_service_are_private(value):
    group = register(
        CampaignState(123, CalendarDate(17, 3, 4710), party_level=4),
        FakePredictionService() if value == "invalid" else None,
    )
    interaction = command_interaction()
    asyncio.run(group.get_command("predict").callback(
        interaction, app_commands.Choice(name=value, value=value)
    ))
    response = interaction.response.send_message.await_args
    assert response.kwargs["ephemeral"] is True
    assert "dc" not in response.args[0].lower()
    interaction.response.send_modal.assert_not_awaited()

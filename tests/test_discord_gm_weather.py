"""Private inspection against real services and temporary SQLite persistence."""

import asyncio
import sqlite3
from unittest.mock import Mock

import pytest
from discord import app_commands

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.application.predict_weather_service import PredictWeatherService
from kingmaker_bot.database import SQLitePredictionRepository
from kingmaker_bot.discord_calendar_commands import register_calendar_commands
from kingmaker_bot.discord_weather_formatter import format_weather
from kingmaker_bot.prediction import PredictionConditions, PredictionWeatherRevealedError
from test_discord_calendar_weather_commands import (
    FakeTree, command_interaction, open_confirmation, press, services,
)
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign import CampaignState
from kingmaker_bot.database import SQLiteWeatherRepository
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.weather import PROFILE_ID, KingmakerStolenLandsProfile, WeatherEngine


def inspect_weather(group):
    interaction = command_interaction()
    asyncio.run(group.get_command("weather-gm").callback(interaction))
    interaction.response.send_message.assert_awaited_once()
    response = interaction.response.send_message.await_args
    assert response.kwargs == {"ephemeral": True}
    interaction.followup.send.assert_not_awaited()
    return response.args[0]


@pytest.mark.parametrize("prediction_first", [False, True])
def test_inspection_prediction_and_public_reveal_share_canonical_weather(tmp_path, prediction_first):
    campaigns, dice, _ = services(tmp_path)
    date = CalendarDate(20, 3, 4710)
    state = campaigns.save(CampaignState(111, date, party_level=3))
    repository = SQLiteWeatherRepository(tmp_path / "state.sqlite3")
    weather = WeatherService(repository, {PROFILE_ID: WeatherEngine(KingmakerStolenLandsProfile(), dice)})
    predictions = SQLitePredictionRepository(tmp_path / "state.sqlite3")
    prediction = PredictWeatherService(predictions, weather)
    group = register_calendar_commands(FakeTree(), CalendarService(campaigns), weather, prediction)

    def predict(user_id=333):
        return prediction.predict(111, user_id, date, 3, 30, PredictionConditions.NORMAL)

    attempt = predict() if prediction_first else None
    before = repository.get(111, date, PROFILE_ID)
    output = inspect_weather(group)
    canonical = repository.get(111, date, PROFILE_ID)
    assert canonical is not None
    assert canonical.revealed_at is None
    if before is not None:
        assert canonical == before
    assert output == f"Actual weather — {format_weather(canonical.weather)}\n\nGM view — this weather has not been revealed to the group."
    with sqlite3.connect(tmp_path / "state.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM prediction_attempt").fetchone()[0] == int(prediction_first)
    assert inspect_weather(group) == output
    assert repository.get(111, date, PROFILE_ID) == canonical
    assert campaigns.get(111) == state  # Includes date, level, and save timestamp.
    assert dice.count == 2

    if attempt is None:
        attempt = predict()
    assert attempt.forecast.precipitation == canonical.weather.precipitation.precipitation_type
    assert attempt.forecast.significant_event_occurs == canonical.weather.significant_event_check.occurs
    assert inspect_weather(group) == output
    assert repository.get(111, date, PROFILE_ID) == canonical
    assert predictions.get(111, 333, date, PROFILE_ID) == attempt

    view, _ = open_confirmation(group)
    assert repository.get(111, date, PROFILE_ID) == canonical
    assert inspect_weather(group) == output  # Pending confirmation remains deliberate.
    revealed_response = press(view, "Reveal Weather")
    assert revealed_response.response.send_message.await_args.kwargs["ephemeral"] is False
    assert revealed_response.response.send_message.await_args.args[0] == format_weather(canonical.weather)
    revealed = repository.get(111, date, PROFILE_ID)
    assert revealed.weather == canonical.weather
    assert revealed.created_at == canonical.created_at
    assert revealed.revealed_at is not None
    assert "this weather has already been revealed." in inspect_weather(group)
    assert repository.get(111, date, PROFILE_ID) == revealed
    assert predictions.get(111, 333, date, PROFILE_ID) == attempt
    with pytest.raises(PredictionWeatherRevealedError):
        predict(user_id=444)
    assert predictions.get(111, 444, date, PROFILE_ID) is None
    assert dice.count == 2
    assert campaigns.get(111) == state


@pytest.mark.parametrize("rolls", [(14, 16), (15, 17, 10), (15, 17, 17), (15, 20, 15, 20)])
def test_gm_display_reuses_result_formatter_without_generation_secrets(tmp_path, rolls):
    campaigns, dice, group = services(tmp_path, values=rolls)
    date = CalendarDate(23, 3, 4710)
    campaigns.save(CampaignState(111, date, party_level=3))
    output = inspect_weather(group)
    record = SQLiteWeatherRepository(tmp_path / "state.sqlite3").get(111, date, PROFILE_ID)
    assert format_weather(record.weather) in output
    for secret in ("dc", "roll", "check", "is_false", "degree", "critical", "success", "survival", "kingmaker_stolen_lands", "revealed_at", "event_table"):
        assert secret not in output.lower()
    assert record.weather.precipitation.roll == rolls[0]
    assert record.revealed_at is None
    assert dice.count == len(rolls)


@pytest.mark.parametrize("case", ["dm", "campaign", "level", "unavailable", "storage", "generation"])
def test_gm_errors_are_private_and_do_not_expose_internals(tmp_path, case):
    campaigns, dice, group = services(tmp_path, values=())
    if case not in ("dm", "campaign"):
        campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710), party_level=None if case == "level" else 3))
    if case == "unavailable":
        group = register_calendar_commands(FakeTree(), CalendarService(campaigns))
    if case == "storage":
        calendar = Mock()
        calendar.get_campaign_state.side_effect = RuntimeError("secret database path check_dc=20")
        group = register_calendar_commands(FakeTree(), calendar)
    interaction = command_interaction(guild_id=None if case == "dm" else 111)
    asyncio.run(group.get_command("weather-gm").callback(interaction))
    response = interaction.response.send_message.await_args
    assert response.kwargs == {"ephemeral": True}
    assert "Actual weather" not in response.args[0]
    assert "secret" not in response.args[0]
    assert "check_dc" not in response.args[0]
    assert SQLiteWeatherRepository(tmp_path / "state.sqlite3").get(111, CalendarDate(1, 3, 4710), PROFILE_ID) is None


def test_weather_commands_remain_separate_executable_subcommands(tmp_path):
    _, _, group = services(tmp_path)
    for name in ("weather", "weather-gm"):
        command = group.get_command(name)
        assert isinstance(command, app_commands.Command)
        assert command.to_dict(FakeTree())["type"] == 1
        assert command.to_dict(FakeTree())["options"] == []
    assert "GM" in group.get_command("weather-gm").description

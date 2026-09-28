import asyncio
import sqlite3
from dataclasses import replace

import pytest

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.application.predict_weather_service import PredictWeatherService
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign.repository import StaleCampaignStateError
from kingmaker_bot.database import (
    SQLiteCampaignStateRepository, SQLitePredictionRepository, SQLiteWeatherRepository,
)
from kingmaker_bot.discord_calendar_commands import register_calendar_commands
from kingmaker_bot.prediction import PredictionConditions
from kingmaker_bot.weather import KingmakerStolenLandsProfile, PROFILE_ID, WeatherEngine
from test_discord_calendar_weather_commands import FakeTree, command_interaction, press
from test_prediction_repository import make_attempt


class Rolls:
    def __init__(self):
        self.count = 0

    def roll(self, sides):
        self.count += 1
        return 1


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "rewind.sqlite3"
    campaigns = SQLiteCampaignStateRepository(path)
    weather = SQLiteWeatherRepository(path)
    predictions = SQLitePredictionRepository(path)
    calendar = CalendarService(campaigns)
    calendar.set_date(111, 24, 3, 4710)
    calendar.set_party_level(111, 3)
    dice = Rolls()
    weather_service = WeatherService(weather, {PROFILE_ID: WeatherEngine(KingmakerStolenLandsProfile(), dice)})
    prediction_service = PredictWeatherService(predictions, weather_service)
    for guild in (111, 999):
        for date in (CalendarDate(31, 12, 4709), CalendarDate(16, 3, 4710),
                     CalendarDate(17, 3, 4710), CalendarDate(18, 3, 4710), CalendarDate(1, 1, 4711)):
            record = weather_service.get_or_generate(guild, date, 3, PROFILE_ID)
            if date.day == 17:
                weather.mark_revealed(guild, date, PROFILE_ID)
            weather.save_generated(guild, replace(record.weather, profile_id="other"))
            for user in (222, 333):
                for profile in (PROFILE_ID, "other"):
                    predictions.save(make_attempt(guild, user, date, profile))
    group = register_calendar_commands(FakeTree(), calendar, weather_service, prediction_service)
    return path, calendar, weather, predictions, weather_service, prediction_service, dice, group


def snapshot(path):
    with sqlite3.connect(path) as connection:
        return {table: connection.execute(f"SELECT * FROM {table}").fetchall()
                for table in ("campaign_state", "daily_weather", "prediction_attempt")}


def open_prompt(setup, target=CalendarDate(17, 3, 4710)):
    interaction = command_interaction()
    asyncio.run(setup[-1].get_command("set").callback(interaction, target.day, target.month, target.year))
    result = interaction.response.send_message.await_args
    assert result.kwargs["ephemeral"] is True
    return result.kwargs["view"], result.args[0]


def test_confirmed_rewind_inclusive_cleanup_and_preservation(setup):
    path, calendar, weather, predictions, *_ = setup
    before = snapshot(path)
    old = calendar.get_campaign_state(111)
    view, prompt = open_prompt(setup)
    assert snapshot(path) == before
    assert "17 Pharast 4710 AR and later" in prompt
    assert "permanently removed" in prompt
    assert [button.label for button in view.children] == ["Set Date", "Cancel"]
    response = press(view, "Set Date")
    assert response.response.send_message.await_args.kwargs["ephemeral"] is False
    state = calendar.get_campaign_state(111)
    assert state.current_date == CalendarDate(17, 3, 4710)
    assert state.party_level == old.party_level
    assert state.created_at == old.created_at
    assert state.updated_at > old.updated_at
    after = snapshot(path)
    assert after["daily_weather"] == [row for row in before["daily_weather"]
        if row[0] != 111 or tuple(row[1:4]) < (4710, 3, 17)]
    assert after["prediction_attempt"] == [row for row in before["prediction_attempt"]
        if row[0] != 111 or tuple(row[2:5]) < (4710, 3, 17)]
    press(view, "Set Date")
    assert snapshot(path) == after


@pytest.mark.parametrize("action", ["Cancel", "timeout"])
def test_cancel_timeout_and_opening_do_not_mutate(setup, action):
    before = snapshot(setup[0])
    view, _ = open_prompt(setup)
    assert snapshot(setup[0]) == before
    assert view.timeout == 300
    if action == "timeout":
        asyncio.run(view.on_timeout())
    else:
        press(view, action)
    assert view.is_finished()
    assert all(button.disabled for button in view.children)
    press(view, "Set Date")
    assert snapshot(setup[0]) == before


@pytest.mark.parametrize("action", ["Set Date", "Cancel"])
def test_other_user_cannot_act(setup, action):
    before = snapshot(setup[0])
    view, _ = open_prompt(setup)
    result = press(view, action, user_id=999)
    assert result.response.send_message.await_args.kwargs["ephemeral"] is True
    assert not view.is_finished()
    assert snapshot(setup[0]) == before


@pytest.mark.parametrize("change", ["advance", "same", "return", "level"])
def test_stale_confirmation_rejected(setup, change):
    calendar = setup[1]
    view, _ = open_prompt(setup)
    if change == "advance":
        calendar.advance(111, 1)
    elif change == "same":
        calendar.set_date(111, 24, 3, 4710)
    elif change == "return":
        calendar.advance(111, 1)
        calendar.set_date(111, 24, 3, 4710)
    else:
        calendar.set_party_level(111, 4)
    before = snapshot(setup[0])
    result = press(view, "Set Date")
    assert "campaign has changed" in result.response.send_message.await_args.args[0]
    assert result.response.send_message.await_args.kwargs["ephemeral"] is True
    assert snapshot(setup[0]) == before


@pytest.mark.parametrize("target", [CalendarDate(24, 3, 4710), CalendarDate(25, 3, 4710), CalendarDate(1, 4, 4710)])
def test_non_destructive_set(setup, target):
    before = snapshot(setup[0])
    interaction = command_interaction()
    asyncio.run(setup[-1].get_command("set").callback(interaction, target.day, target.month, target.year))
    assert "view" not in interaction.response.send_message.await_args.kwargs
    after = snapshot(setup[0])
    assert after["daily_weather"] == before["daily_weather"]
    assert after["prediction_attempt"] == before["prediction_attempt"]
    assert setup[1].get_campaign_state(111).current_date == target


def test_clean_target_can_predict_and_future_weather_is_generated_again(setup):
    _, calendar, weather, predictions, weather_service, predictor, dice, _ = setup
    target = CalendarDate(17, 3, 4710)
    old = weather.get(111, target.advance(), PROFILE_ID)
    view, _ = open_prompt(setup)
    press(view, "Set Date")
    count = dice.count
    attempt = predictor.predict(111, 222, target, 3, 30, PredictionConditions.NORMAL)
    assert attempt.campaign_date == target
    assert weather.get(111, target, PROFILE_ID).revealed_at is None
    assert dice.count > count
    state = calendar.advance(111, 1)
    count = dice.count
    new = weather_service.get_or_generate(111, state.current_date, 3, PROFILE_ID)
    assert dice.count > count
    assert new.created_at != old.created_at


def test_legacy_forecast_crossing_boundary_is_removed(setup):
    predictions = setup[3]
    for day in (15, 16):
        attempt = make_attempt(111, 444, CalendarDate(day, 3, 4710))
        predictions.save(replace(attempt, forecast_date=attempt.campaign_date.advance()))
    setup[1].rewind(setup[1].get_campaign_state(111), CalendarDate(17, 3, 4710))
    assert predictions.get(111, 444, CalendarDate(15, 3, 4710), PROFILE_ID) is not None
    assert predictions.get(111, 444, CalendarDate(16, 3, 4710), PROFILE_ID) is None


@pytest.mark.parametrize("table", ["daily_weather", "campaign_state"])
def test_failure_rolls_back_everything(setup, table):
    path, calendar, *_ = setup
    operation = "UPDATE" if table == "campaign_state" else "DELETE"
    with sqlite3.connect(path) as connection:
        connection.execute(f"""CREATE TRIGGER fail_rewind BEFORE {operation} ON {table}
                            BEGIN SELECT RAISE(ABORT, 'private failure'); END""")
    before = snapshot(path)
    view, _ = open_prompt(setup)
    result = press(view, "Set Date")
    assert result.response.send_message.await_args.args[0] == (
        "The campaign date could not be changed. Please try again later.")
    assert result.response.send_message.await_args.kwargs["ephemeral"] is True
    assert snapshot(path) == before


def test_repository_rejects_stale_snapshot_and_non_rewind(setup):
    calendar = setup[1]
    old = calendar.get_campaign_state(111)
    calendar.set_date(111, 24, 3, 4710)
    before = snapshot(setup[0])
    with pytest.raises(StaleCampaignStateError):
        calendar.rewind(old, CalendarDate(17, 3, 4710))
    with pytest.raises(ValueError):
        calendar.rewind(old, old.current_date)
    assert snapshot(setup[0]) == before


@pytest.mark.parametrize("current,target", [
    (CalendarDate(1, 4, 4710), CalendarDate(31, 3, 4710)),
    (CalendarDate(1, 1, 4711), CalendarDate(31, 12, 4710)),
])
def test_rewind_compares_year_month_then_day(setup, current, target):
    setup[1].set_date(111, current.day, current.month, current.year)
    view, _ = open_prompt(setup, target)
    press(view, "Set Date")
    assert setup[1].get_campaign_state(111).current_date == target

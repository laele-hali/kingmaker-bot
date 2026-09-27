from dataclasses import replace

import pytest

from kingmaker_bot.application.predict_weather_service import PredictWeatherService
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.database import SQLitePredictionRepository, SQLiteWeatherRepository
from kingmaker_bot.prediction import (
    DegreeOfSuccess,
    PredictionAlreadyAttemptedError,
    PredictionConditions,
)
from kingmaker_bot.weather import (
    KingmakerStolenLandsProfile,
    PrecipitationType,
    PROFILE_ID,
    WeatherEngine,
)


class SequenceDice:
    def __init__(self, *rolls: int):
        self.rolls = list(rolls)
        self.consumed = 0

    def roll(self, sides: int) -> int:
        assert self.rolls, "unexpected weather generation roll"
        self.consumed += 1
        return self.rolls.pop(0)


class FirstChoice:
    def choice(self, values):
        return values[0]


class RepeatedFirstChoice:
    def __init__(self):
        self.calls = 0

    def choice(self, values):
        self.calls += 1
        return values[0]


def service_bundle(tmp_path, rolls=(15, 1), profile_id=PROFILE_ID, choice=None):
    database = tmp_path / "predict.sqlite3"
    dice = SequenceDice(*rolls)
    engine = WeatherEngine(KingmakerStolenLandsProfile(), dice)
    class AlternateProfile:
        def generate(self, date, party_level):
            return replace(engine.generate(date, party_level), profile_id="other_profile")

    weather = WeatherService(
        SQLiteWeatherRepository(database), {PROFILE_ID: engine, "other_profile": AlternateProfile()}
    )
    predictions = SQLitePredictionRepository(database)
    return PredictWeatherService(predictions, weather, profile_id, choice or FirstChoice()), predictions, weather, dice


@pytest.mark.parametrize(
    ("conditions", "dc"),
    [
        (PredictionConditions.COMMANDING_VIEW, 15),
        (PredictionConditions.NORMAL, 20),
        (PredictionConditions.POOR, 30),
    ],
)
def test_condition_dc_values(conditions, dc):
    assert conditions.dc == dc


@pytest.mark.parametrize(
    ("total", "dc", "degree"),
    [
        (30, 20, DegreeOfSuccess.CRITICAL_SUCCESS),
        (29, 20, DegreeOfSuccess.SUCCESS),
        (20, 20, DegreeOfSuccess.SUCCESS),
        (19, 20, DegreeOfSuccess.FAILURE),
        (11, 20, DegreeOfSuccess.FAILURE),
        (10, 20, DegreeOfSuccess.CRITICAL_FAILURE),
    ],
)
def test_total_to_dc_degree_boundaries(total, dc, degree):
    from kingmaker_bot.prediction import determine_degree_of_success

    assert determine_degree_of_success(total, dc) is degree


@pytest.mark.parametrize(
    ("current", "forecast"),
    [
        (CalendarDate(17, 3, 4710), CalendarDate(18, 3, 4710)),
        (CalendarDate(31, 3, 4710), CalendarDate(1, 4, 4710)),
        (CalendarDate(31, 12, 4710), CalendarDate(1, 1, 4711)),
        (CalendarDate(28, 2, 4712), CalendarDate(29, 2, 4712)),
        (CalendarDate(28, 2, 4710), CalendarDate(1, 3, 4710)),
    ],
)
def test_prediction_targets_next_campaign_date(tmp_path, current, forecast):
    service, _, _, _ = service_bundle(tmp_path, rolls=(1, 1, 1, 1, 1, 1, 1, 1))

    attempt = service.predict(123, 456, current, 1, 20, PredictionConditions.NORMAL)

    assert attempt.forecast_date == forecast


def test_critical_success_reports_accurate_data_bonus_and_ambiguous_event(tmp_path):
    # Wildfire (17) has a GM-selected hazard level; preserve both options.
    service, _, weather_service, _ = service_bundle(tmp_path, rolls=(15, 17, 17))
    attempt = service.predict(123, 456, CalendarDate(17, 3, 4710), 1, 30, PredictionConditions.NORMAL)
    canonical = weather_service.get_or_generate(123, attempt.forecast_date, 1, PROFILE_ID)

    assert attempt.degree is DegreeOfSuccess.CRITICAL_SUCCESS
    assert attempt.forecast.precipitation is canonical.weather.precipitation.precipitation_type
    assert attempt.forecast.mild_cold is None
    assert attempt.forecast.significant_event_occurs is True
    assert attempt.forecast.event == canonical.weather.selected_event
    assert attempt.forecast.event.hazard.choices == (4, 10)
    assert attempt.forecast.event_gm_resolution_required
    assert attempt.forecast.preparation_bonus == 2
    assert attempt.forecast.event_timing_known is False
    assert attempt.forecast.wind_information_available is False
    assert canonical.revealed_at is None


def test_critical_success_reports_winter_temperature_and_snow(tmp_path):
    service, _, _, _ = service_bundle(tmp_path, rolls=(8, 16, 1))
    attempt = service.predict(123, 456, CalendarDate(31, 12, 4710), 1, 30, PredictionConditions.NORMAL)

    assert attempt.forecast_date == CalendarDate(1, 1, 4711)
    assert attempt.forecast.precipitation is PrecipitationType.SNOW
    assert attempt.forecast.mild_cold is True


def test_success_reports_event_occurrence_without_identifying_event(tmp_path):
    service, _, weather_service, _ = service_bundle(tmp_path, rolls=(15, 17, 17))
    attempt = service.predict(123, 456, CalendarDate(17, 3, 4710), 1, 20, PredictionConditions.NORMAL)
    canonical = weather_service.get_or_generate(123, attempt.forecast_date, 1, PROFILE_ID)

    assert attempt.degree is DegreeOfSuccess.SUCCESS
    assert attempt.forecast.precipitation is canonical.weather.precipitation.precipitation_type
    assert attempt.forecast.significant_event_occurs is True
    assert attempt.forecast.event is None
    assert attempt.forecast.preparation_bonus == 1


def test_failure_contains_no_canonical_weather_data(tmp_path):
    service, _, _, _ = service_bundle(tmp_path)
    attempt = service.predict(123, 456, CalendarDate(17, 3, 4710), 1, 19, PredictionConditions.NORMAL)

    assert attempt.degree is DegreeOfSuccess.FAILURE
    assert attempt.forecast.precipitation is None
    assert attempt.forecast.mild_cold is None
    assert attempt.forecast.significant_event_occurs is None
    assert attempt.forecast.event is None
    assert attempt.forecast.preparation_bonus is None


def test_critical_failure_is_deterministic_false_and_does_not_mutate_canonical(tmp_path):
    choices = RepeatedFirstChoice()
    service, _, weather_service, _ = service_bundle(tmp_path, rolls=(15, 17, 17), choice=choices)
    current = CalendarDate(17, 3, 4710)
    attempt = service.predict(123, 456, current, 1, 10, PredictionConditions.NORMAL)
    canonical_before = weather_service.get_or_generate(123, attempt.forecast_date, 1, PROFILE_ID)
    expected_false_precipitation = PrecipitationType.NONE

    assert attempt.degree is DegreeOfSuccess.CRITICAL_FAILURE
    assert attempt.forecast.is_false
    assert attempt.forecast.preparation_bonus == 2
    assert attempt.forecast.precipitation is expected_false_precipitation
    assert attempt.forecast.precipitation is not canonical_before.weather.precipitation.precipitation_type
    assert attempt.forecast.event is not None
    assert choices.calls == 1
    assert canonical_before.revealed_at is None
    assert weather_service.get_or_generate(123, attempt.forecast_date, 1, PROFILE_ID) == canonical_before


def test_injected_false_forecast_randomness_reproduces_the_same_result(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_service, _, _, _ = service_bundle(first_dir, rolls=(15, 17, 17), choice=FirstChoice())
    second_service, _, _, _ = service_bundle(second_dir, rolls=(15, 17, 17), choice=FirstChoice())

    first = first_service.predict(123, 456, CalendarDate(17, 3, 4710), 1, 10, PredictionConditions.NORMAL)
    second = second_service.predict(123, 456, CalendarDate(17, 3, 4710), 1, 10, PredictionConditions.NORMAL)

    assert first.forecast == second.forecast


def test_existing_canonical_weather_is_reused_without_rolls_or_reveal(tmp_path):
    service, _, weather_service, dice = service_bundle(tmp_path, rolls=(1, 1))
    current = CalendarDate(17, 3, 4710)
    forecast_date = current.advance()
    canonical = weather_service.get_or_generate(123, forecast_date, 1, PROFILE_ID)
    consumed = dice.consumed

    attempt = service.predict(123, 456, current, 1, 20, PredictionConditions.NORMAL)

    assert dice.consumed == consumed
    assert attempt.forecast.precipitation is canonical.weather.precipitation.precipitation_type
    assert weather_service.get_or_generate(123, forecast_date, 1, PROFILE_ID) == canonical
    from kingmaker_bot.database import SQLiteWeatherRepository
    assert SQLiteWeatherRepository(tmp_path / "predict.sqlite3").get(
        123, forecast_date, PROFILE_ID
    ).revealed_at is None


def test_same_day_duplicate_is_rejected_before_weather_generation(tmp_path):
    service, _, _, dice = service_bundle(tmp_path, rolls=(1, 1))
    current = CalendarDate(17, 3, 4710)
    service.predict(123, 456, current, 1, 20, PredictionConditions.NORMAL)
    consumed = dice.consumed

    with pytest.raises(PredictionAlreadyAttemptedError):
        service.predict(123, 456, current, 1, 20, PredictionConditions.NORMAL)

    assert dice.consumed == consumed


def test_distinct_user_guild_campaign_day_and_profile_have_independent_attempts(tmp_path):
    service, repository, weather, _ = service_bundle(tmp_path, rolls=(1, 1, 1, 1, 1, 1, 1, 1))
    date = CalendarDate(17, 3, 4710)
    first = service.predict(123, 456, date, 1, 20, PredictionConditions.NORMAL)
    other_user = service.predict(123, 789, date, 1, 20, PredictionConditions.NORMAL)
    other_guild = service.predict(999, 456, date, 1, 20, PredictionConditions.NORMAL)
    next_day = service.predict(123, 456, date.advance(), 1, 20, PredictionConditions.NORMAL)
    other_profile_service = PredictWeatherService(repository, weather, "other_profile", FirstChoice())
    other_profile = other_profile_service.predict(123, 456, date, 1, 20, PredictionConditions.NORMAL)

    assert len({first.user_id, other_user.user_id}) == 2
    assert other_guild.guild_id == 999
    assert next_day.campaign_date == date.advance()
    assert other_profile.profile_id == "other_profile"


@pytest.mark.parametrize(
    ("guild", "user", "date", "party_level", "total", "conditions"),
    [
        (0, 2, CalendarDate(1, 3, 4710), 1, 20, PredictionConditions.NORMAL),
        (1, 0, CalendarDate(1, 3, 4710), 1, 20, PredictionConditions.NORMAL),
        (1, 2, CalendarDate(1, 3, 4710), 0, 20, PredictionConditions.NORMAL),
        (1, 2, CalendarDate(1, 3, 4710), 1, True, PredictionConditions.NORMAL),
        (1, 2, CalendarDate(1, 3, 4710), 1, 20, "normal"),
    ],
)
def test_invalid_inputs_are_rejected(tmp_path, guild, user, date, party_level, total, conditions):
    service, _, _, _ = service_bundle(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        service.predict(guild, user, date, party_level, total, conditions)

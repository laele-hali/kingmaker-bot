import sqlite3
from dataclasses import replace
from datetime import timezone

import pytest

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.database import SQLitePredictionRepository
from kingmaker_bot.database.prediction_serialization import PredictionSerializationError
from kingmaker_bot.prediction import (
    DegreeOfSuccess,
    PredictionAttempt,
    PredictionConditions,
    WeatherForecast,
    determine_degree_of_success,
)
from kingmaker_bot.weather import (
    HazardLevel,
    PrecipitationType,
    WeatherEvent,
    WeatherEventDefinition,
)


def make_attempt(
    guild_id=101,
    user_id=201,
    campaign_date=CalendarDate(17, 3, 4710),
    profile_id="kingmaker_stolen_lands",
):
    total = 30
    conditions = PredictionConditions.NORMAL
    event = WeatherEventDefinition(WeatherEvent.WILDFIRE, HazardLevel(choices=(4, 10)))
    return PredictionAttempt(
        guild_id=guild_id,
        user_id=user_id,
        campaign_date=campaign_date,
        forecast_date=campaign_date.advance(),
        profile_id=profile_id,
        survival_total=total,
        conditions=conditions,
        degree=determine_degree_of_success(total, conditions.dc),
        forecast=WeatherForecast(
            PrecipitationType.RAIN, None, True, event, 2,
            event_gm_resolution_required=True,
        ),
    )


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "predictions.sqlite3"


@pytest.fixture
def repository(database_path):
    return SQLitePredictionRepository(database_path)


def test_schema_initialization_is_idempotent(repository, database_path):
    repository.initialize()
    SQLitePredictionRepository(database_path).initialize()
    assert repository.get(101, 201, CalendarDate(17, 3, 4710), "kingmaker_stolen_lands") is None


def test_unknown_attempt_returns_none(repository):
    assert repository.get(101, 201, CalendarDate(17, 3, 4710), "kingmaker_stolen_lands") is None


def test_attempt_round_trips_with_utc_timestamp(repository):
    expected = repository.save(make_attempt())
    loaded = repository.get(101, 201, CalendarDate(17, 3, 4710), "kingmaker_stolen_lands")

    assert loaded == expected
    assert loaded.created_at.tzinfo is timezone.utc
    assert loaded.dc == 20
    assert loaded.forecast.event.hazard.choices == (4, 10)


def test_prediction_rows_are_isolated_by_user_guild_date_and_profile(repository):
    first = repository.save(make_attempt())
    other_user = repository.save(make_attempt(user_id=202))
    other_guild = repository.save(make_attempt(guild_id=102))
    other_date = repository.save(make_attempt(campaign_date=CalendarDate(18, 3, 4710)))
    other_profile = repository.save(make_attempt(profile_id="other_profile"))

    assert len({first.user_id, other_user.user_id}) == 2
    assert other_guild.guild_id == 102
    assert other_date.campaign_date == CalendarDate(18, 3, 4710)
    assert other_profile.profile_id == "other_profile"


def test_prediction_survives_repository_reconstruction(database_path):
    first = SQLitePredictionRepository(database_path)
    expected = first.save(make_attempt())
    second = SQLitePredictionRepository(database_path)

    assert second.get(101, 201, expected.campaign_date, expected.profile_id) == expected


def test_duplicate_save_returns_existing_attempt_without_overwriting(repository):
    original = repository.save(make_attempt())
    competing = replace(
        make_attempt(),
        forecast=WeatherForecast(PrecipitationType.SNOW, None, False, None, 2),
    )

    returned = repository.save(competing)

    assert returned == original
    assert repository.get(101, 201, original.campaign_date, original.profile_id) == original


def test_malformed_forecast_json_raises_clearly(repository, database_path):
    attempt = repository.save(make_attempt())
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE prediction_attempt SET forecast_json = ?", ("not-json",))

    with pytest.raises(PredictionSerializationError, match="invalid stored prediction forecast"):
        repository.get(attempt.guild_id, attempt.user_id, attempt.campaign_date, attempt.profile_id)


def test_naive_persisted_timestamp_is_rejected(repository, database_path):
    attempt = repository.save(make_attempt())
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE prediction_attempt SET created_at = ?", ("2026-01-01T12:00:00",))

    with pytest.raises(ValueError, match="timezone-aware"):
        repository.get(attempt.guild_id, attempt.user_id, attempt.campaign_date, attempt.profile_id)

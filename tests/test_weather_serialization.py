from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.database.weather_serialization import deserialize_weather, serialize_weather
from kingmaker_bot.weather import (
    DailyWeather,
    EventTableAttempt,
    HazardLevel,
    PrecipitationResult,
    PrecipitationType,
    SecondaryEventCheck,
    SignificantEventCheck,
    WeatherEvent,
    WeatherEventDefinition,
    WinterTemperatureResult,
)


def test_complete_daily_weather_result_round_trips_all_hazard_variants() -> None:
    date = CalendarDate(1, 1, 4712)
    exact = WeatherEventDefinition(WeatherEvent.COLD_SNAP, HazardLevel(exact=1))
    choices = WeatherEventDefinition(WeatherEvent.WILDFIRE, HazardLevel(choices=(4, 10)))
    open_ended = WeatherEventDefinition(WeatherEvent.SUPERNATURAL_STORM, HazardLevel(minimum=6))
    weather = DailyWeather(
        profile_id="serialization_test_profile",
        date=date,
        precipitation=PrecipitationResult(roll=20, dc=16, occurs=True, precipitation_type=PrecipitationType.SNOW),
        winter_temperature=WinterTemperatureResult(True, 18, 16, True),
        significant_event_check=SignificantEventCheck(20, 17, True),
        event_attempts=(
            EventTableAttempt(8, exact, False),
            EventTableAttempt(17, choices, True),
            EventTableAttempt(15, open_ended, True),
        ),
        selected_event=open_ended,
        gm_event_resolution_required=True,
        event_reroll_limit_exhausted=False,
        secondary_event_check=SecondaryEventCheck(19, 17, True, True),
    )

    restored = deserialize_weather(serialize_weather(weather))

    assert restored == weather
    assert restored.event_attempts[0].result.hazard.exact == 1
    assert restored.event_attempts[1].result.hazard.choices == (4, 10)
    assert restored.event_attempts[2].result.hazard.minimum == 6


def test_optional_winter_temperature_and_secondary_check_round_trip() -> None:
    weather = DailyWeather(
        profile_id="optional_fields_test",
        date=CalendarDate(1, 3, 4712),
        precipitation=PrecipitationResult(1, 15, False, PrecipitationType.NONE),
        winter_temperature=WinterTemperatureResult(False, None, None, False),
        significant_event_check=SignificantEventCheck(1, 17, False),
        event_attempts=(),
        selected_event=None,
        gm_event_resolution_required=False,
        event_reroll_limit_exhausted=False,
        secondary_event_check=None,
    )

    restored = deserialize_weather(serialize_weather(weather))

    assert restored == weather
    assert restored.winter_temperature.roll is None
    assert restored.secondary_event_check is None

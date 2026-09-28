import pytest
from dataclasses import replace

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.discord_prediction_formatter import format_prediction
from kingmaker_bot.prediction import (
    DegreeOfSuccess,
    PredictionAttempt,
    PredictionConditions,
    WeatherForecast,
)
from kingmaker_bot.weather import (
    HazardLevel,
    PrecipitationType,
    WeatherEvent,
    WeatherEventDefinition,
)


def make_attempt(degree, forecast, total, campaign_date=CalendarDate(17, 3, 4710)):
    return PredictionAttempt(
        guild_id=1,
        user_id=2,
        campaign_date=campaign_date,
        forecast_date=campaign_date,
        profile_id="kingmaker_stolen_lands",
        survival_total=total,
        conditions=PredictionConditions.NORMAL,
        degree=degree,
        forecast=forecast,
    )


def test_critical_success_formats_detail_and_event_during_target_day():
    forecast = WeatherForecast(
        precipitation=PrecipitationType.RAIN,
        mild_cold=None,
        significant_event_occurs=True,
        event=WeatherEventDefinition(WeatherEvent.WINDSTORM, HazardLevel(exact=1)),
        preparation_bonus=2,
    )

    output = format_prediction(make_attempt(DegreeOfSuccess.CRITICAL_SUCCESS, forecast, 30))

    assert "Weather forecast for" in output and "17 Pharast 4710 AR" in output
    assert "Light rain" in output
    assert "Windstorm is expected during the day ahead" in output
    assert "+2 circumstance bonus" in output
    assert "hour" not in output.lower()
    assert "ordinary wind" not in output.lower()


def test_success_formats_precipitation_temperature_and_event_without_identity():
    forecast = WeatherForecast(
        precipitation=PrecipitationType.SNOW,
        mild_cold=True,
        significant_event_occurs=True,
        event=None,
        preparation_bonus=1,
    )

    output = format_prediction(
        make_attempt(
            DegreeOfSuccess.SUCCESS,
            forecast,
            20,
            campaign_date=CalendarDate(30, 12, 4710),
        )
    )

    assert "Light snow" in output
    assert "Mild Cold" in output
    assert "A significant weather event is expected during the day ahead" in output
    assert "Windstorm" not in output
    assert "+1 circumstance bonus" in output
    assert "success" not in output.lower()


def test_failure_does_not_expose_canonical_weather_details():
    output = format_prediction(
        make_attempt(
            DegreeOfSuccess.FAILURE,
            WeatherForecast(None, None, None, None, None),
            19,
        )
    )

    assert "unable to obtain a useful forecast" in output
    assert "precipitation" not in output.lower()
    assert "significant weather" not in output.lower()
    assert "survival checks" not in output.lower()


def test_critical_failure_formats_detailed_false_forecast_without_revealing_it():
    forecast = WeatherForecast(
        precipitation=PrecipitationType.NONE,
        mild_cold=None,
        significant_event_occurs=True,
        event=WeatherEventDefinition(WeatherEvent.TORNADO, HazardLevel(choices=(12, 17))),
        preparation_bonus=2,
        is_false=True,
        event_gm_resolution_required=True,
    )

    output = format_prediction(make_attempt(
        DegreeOfSuccess.CRITICAL_FAILURE, forecast, 10,
        campaign_date=CalendarDate(18, 3, 4710),
    ))

    assert "No precipitation" in output
    assert "Tornado is expected during the day ahead" in output
    assert "Ask the GM how this event affects your preparations" in output
    assert "+2 circumstance bonus" in output
    assert "critical failure" not in output.lower()
    assert "false" not in output.lower()
    assert "is_false" not in output.lower()
    assert "12" not in output and "17" not in output


def test_event_hazard_resolution_is_shown_without_selecting_a_level():
    forecast = WeatherForecast(
        PrecipitationType.RAIN,
        None,
        True,
        WeatherEventDefinition(WeatherEvent.SUPERNATURAL_STORM, HazardLevel(minimum=6)),
        2,
        event_gm_resolution_required=True,
    )

    output = format_prediction(make_attempt(DegreeOfSuccess.CRITICAL_SUCCESS, forecast, 30))

    assert "Supernatural Storm" in output
    assert "Ask the GM how this event affects your preparations" in output
    assert "Hazard 6" not in output


@pytest.mark.parametrize("precipitation", list(PrecipitationType))
def test_all_precipitation_labels_are_formatted(precipitation):
    forecast = WeatherForecast(precipitation, None, False, None, 2)
    output = format_prediction(make_attempt(DegreeOfSuccess.CRITICAL_SUCCESS, forecast, 30))
    assert {
        PrecipitationType.NONE: "No precipitation",
        PrecipitationType.RAIN: "Light rain",
        PrecipitationType.SNOW: "Light snow",
    }[precipitation] in output


def test_critical_failure_and_confident_detailed_forecast_have_identical_presentation():
    forecast = WeatherForecast(
        PrecipitationType.RAIN, None, True,
        WeatherEventDefinition(WeatherEvent.TORNADO, HazardLevel(choices=(12, 17))),
        2, event_gm_resolution_required=True,
    )
    accurate = make_attempt(DegreeOfSuccess.CRITICAL_SUCCESS, forecast, 30)
    false = make_attempt(DegreeOfSuccess.CRITICAL_FAILURE, replace(forecast, is_false=True), 1)
    assert format_prediction(accurate) == format_prediction(false)
    assert "+2 circumstance bonus" in format_prediction(false)
    assert "Ask the GM how this event affects your preparations." in format_prediction(false)

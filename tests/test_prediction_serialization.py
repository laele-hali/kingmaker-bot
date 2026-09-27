import pytest

from kingmaker_bot.database.prediction_serialization import (
    PredictionSerializationError,
    deserialize_forecast,
    serialize_forecast,
)
from kingmaker_bot.prediction import WeatherForecast
from kingmaker_bot.weather import (
    HazardLevel,
    PrecipitationType,
    WeatherEvent,
    WeatherEventDefinition,
)


@pytest.mark.parametrize(
    "forecast",
    [
        WeatherForecast(None, None, None, None, None),
        WeatherForecast(PrecipitationType.SNOW, True, True, None, 1),
        WeatherForecast(
            PrecipitationType.RAIN,
            False,
            True,
            WeatherEventDefinition(WeatherEvent.WILDFIRE, HazardLevel(choices=(4, 10))),
            2,
            is_false=True,
            event_gm_resolution_required=True,
        ),
        WeatherForecast(
            PrecipitationType.NONE,
            None,
            True,
            WeatherEventDefinition(WeatherEvent.SUPERNATURAL_STORM, HazardLevel(minimum=6)),
            2,
            event_gm_resolution_required=True,
        ),
    ],
)
def test_forecast_json_round_trip_preserves_domain_objects(forecast):
    assert deserialize_forecast(serialize_forecast(forecast)) == forecast


def test_malformed_and_unsupported_documents_fail_clearly():
    with pytest.raises(PredictionSerializationError):
        deserialize_forecast("not-json")
    with pytest.raises(PredictionSerializationError, match="unsupported"):
        deserialize_forecast('{"version":99}')

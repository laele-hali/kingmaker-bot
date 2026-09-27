"""Versioned explicit JSON serialization for Predict Weather forecasts."""

import json
from typing import Any

from kingmaker_bot.prediction import WeatherForecast
from kingmaker_bot.weather import HazardLevel, PrecipitationType, WeatherEvent, WeatherEventDefinition

_VERSION = 1


class PredictionSerializationError(ValueError):
    """Stored prediction forecast JSON is malformed or unsupported."""


def serialize_forecast(forecast: WeatherForecast) -> str:
    if not isinstance(forecast, WeatherForecast):
        raise TypeError("forecast must be a WeatherForecast")
    return json.dumps(
        {
            "version": _VERSION,
            "precipitation": None if forecast.precipitation is None else forecast.precipitation.value,
            "mild_cold": forecast.mild_cold,
            "significant_event_occurs": forecast.significant_event_occurs,
            "event": None if forecast.event is None else _event_to_data(forecast.event),
            "preparation_bonus": forecast.preparation_bonus,
            "is_false": forecast.is_false,
            "wind_information_available": forecast.wind_information_available,
            "event_timing_known": forecast.event_timing_known,
            "event_gm_resolution_required": forecast.event_gm_resolution_required,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def deserialize_forecast(document: str) -> WeatherForecast:
    try:
        payload = _object(json.loads(document), "forecast")
        version = _integer(payload["version"], "version")
        if version != _VERSION:
            raise PredictionSerializationError(f"unsupported prediction serialization version: {version}")
        raw_precipitation = payload["precipitation"]
        precipitation = (
            None if raw_precipitation is None
            else PrecipitationType(_string(raw_precipitation, "precipitation"))
        )
        raw_event = payload["event"]
        return WeatherForecast(
            precipitation=precipitation,
            mild_cold=_optional_boolean(payload["mild_cold"], "mild_cold"),
            significant_event_occurs=_optional_boolean(
                payload["significant_event_occurs"], "significant_event_occurs"
            ),
            event=None if raw_event is None else _event_from_data(raw_event),
            preparation_bonus=_optional_integer(payload["preparation_bonus"], "preparation_bonus"),
            is_false=_boolean(payload["is_false"], "is_false"),
            wind_information_available=_boolean(
                payload["wind_information_available"], "wind_information_available"
            ),
            event_timing_known=_boolean(payload["event_timing_known"], "event_timing_known"),
            event_gm_resolution_required=_boolean(
                payload["event_gm_resolution_required"], "event_gm_resolution_required"
            ),
        )
    except PredictionSerializationError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise PredictionSerializationError(f"invalid stored prediction forecast: {error}") from error


def _event_to_data(event: WeatherEventDefinition) -> dict[str, Any]:
    hazard = event.hazard
    if hazard.exact is not None:
        hazard_data = {"kind": "exact", "level": hazard.exact}
    elif hazard.choices:
        hazard_data = {"kind": "choices", "levels": list(hazard.choices)}
    else:
        hazard_data = {"kind": "open_ended", "minimum": hazard.minimum}
    return {"name": event.event.value, "hazard": hazard_data}


def _event_from_data(value: Any) -> WeatherEventDefinition:
    data = _object(value, "event")
    hazard_data = _object(data["hazard"], "event.hazard")
    kind = _string(hazard_data["kind"], "event.hazard.kind")
    if kind == "exact":
        hazard = HazardLevel(exact=_nonnegative(hazard_data["level"], "event.hazard.level"))
    elif kind == "choices":
        levels = hazard_data["levels"]
        if not isinstance(levels, list):
            raise PredictionSerializationError("event.hazard.levels must be an array")
        hazard = HazardLevel(choices=tuple(
            _nonnegative(level, f"event.hazard.levels[{index}]") for index, level in enumerate(levels)
        ))
    elif kind == "open_ended":
        hazard = HazardLevel(minimum=_nonnegative(hazard_data["minimum"], "event.hazard.minimum"))
    else:
        raise PredictionSerializationError(f"unknown event hazard kind: {kind}")
    return WeatherEventDefinition(WeatherEvent(_string(data["name"], "event.name")), hazard)


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PredictionSerializationError(f"{field} must be an object")
    return value


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PredictionSerializationError(f"{field} must be an integer")
    return value


def _nonnegative(value: Any, field: str) -> int:
    integer = _integer(value, field)
    if integer < 0:
        raise PredictionSerializationError(f"{field} must not be negative")
    return integer


def _optional_integer(value: Any, field: str) -> int | None:
    return None if value is None else _integer(value, field)


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise PredictionSerializationError(f"{field} must be a boolean")
    return value


def _optional_boolean(value: Any, field: str) -> bool | None:
    return None if value is None else _boolean(value, field)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise PredictionSerializationError(f"{field} must be a string")
    return value

"""Explicit JSON serialization for structured daily weather results."""

import json
from typing import Any

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.events import HazardLevel, WeatherEvent, WeatherEventDefinition, event_for_roll
from kingmaker_bot.weather.models import (
    DailyWeather,
    EventTableAttempt,
    PrecipitationResult,
    PrecipitationType,
    SecondaryEventCheck,
    SignificantEventCheck,
    WinterTemperatureResult,
)
from kingmaker_bot.weather.profile import PROFILE_ID

_SERIALIZATION_VERSION = 1


class WeatherSerializationError(ValueError):
    """Persisted weather could not be decoded or failed consistency checks."""


def serialize_weather(weather: DailyWeather) -> str:
    """Serialize all weather fields into a versioned, explicit JSON document."""
    if not isinstance(weather, DailyWeather):
        raise TypeError("weather must be a DailyWeather result")
    _validate_weather(weather)

    payload = {
        "version": _SERIALIZATION_VERSION,
        "profile_id": weather.profile_id,
        "date": {
            "day": weather.date.day,
            "month": weather.date.month,
            "year": weather.date.year,
        },
        "precipitation": {
            "roll": weather.precipitation.roll,
            "dc": weather.precipitation.dc,
            "occurs": weather.precipitation.occurs,
            "type": weather.precipitation.precipitation_type.value,
        },
        "winter_temperature": {
            "check_occurred": weather.winter_temperature.check_occurred,
            "roll": weather.winter_temperature.roll,
            "dc": weather.winter_temperature.dc,
            "mild_cold": weather.winter_temperature.mild_cold,
        },
        "significant_event_check": {
            "roll": weather.significant_event_check.roll,
            "dc": weather.significant_event_check.dc,
            "occurs": weather.significant_event_check.occurs,
        },
        "event_attempts": [
            {
                "roll": attempt.roll,
                "is_reroll": attempt.is_reroll,
                "result": _event_to_dict(attempt.result),
            }
            for attempt in weather.event_attempts
        ],
        "selected_event": (
            _event_to_dict(weather.selected_event) if weather.selected_event is not None else None
        ),
        "gm_event_resolution_required": weather.gm_event_resolution_required,
        "event_reroll_limit_exhausted": weather.event_reroll_limit_exhausted,
        "secondary_event_check": (
            {
                "roll": weather.secondary_event_check.roll,
                "dc": weather.secondary_event_check.dc,
                "succeeds": weather.secondary_event_check.succeeds,
                "gm_resolution_required": weather.secondary_event_check.gm_resolution_required,
            }
            if weather.secondary_event_check is not None
            else None
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_weather(document: str) -> DailyWeather:
    """Reconstruct and validate a daily weather result from stored JSON."""
    try:
        raw: Any = json.loads(document)
        payload = _object(raw, "weather")
        version = _integer(payload["version"], "version")
        if version != _SERIALIZATION_VERSION:
            raise WeatherSerializationError(f"unsupported weather serialization version: {version}")

        profile_id = _string(payload["profile_id"], "profile_id")
        date_data = _object(payload["date"], "date")
        date = CalendarDate(
            day=_integer(date_data["day"], "date.day"),
            month=_integer(date_data["month"], "date.month"),
            year=_integer(date_data["year"], "date.year"),
        )

        precipitation_data = _object(payload["precipitation"], "precipitation")
        precipitation = PrecipitationResult(
            roll=_d20(precipitation_data["roll"], "precipitation.roll"),
            dc=_d20(precipitation_data["dc"], "precipitation.dc"),
            occurs=_boolean(precipitation_data["occurs"], "precipitation.occurs"),
            precipitation_type=PrecipitationType(
                _string(precipitation_data["type"], "precipitation.type")
            ),
        )

        temperature_data = _object(payload["winter_temperature"], "winter_temperature")
        temperature_occurred = _boolean(
            temperature_data["check_occurred"], "winter_temperature.check_occurred"
        )
        temperature_roll = _optional_d20(temperature_data["roll"], "winter_temperature.roll")
        temperature_dc = _optional_d20(temperature_data["dc"], "winter_temperature.dc")
        temperature = WinterTemperatureResult(
            check_occurred=temperature_occurred,
            roll=temperature_roll,
            dc=temperature_dc,
            mild_cold=_boolean(temperature_data["mild_cold"], "winter_temperature.mild_cold"),
        )

        event_check_data = _object(payload["significant_event_check"], "significant_event_check")
        significant_check = SignificantEventCheck(
            roll=_d20(event_check_data["roll"], "significant_event_check.roll"),
            dc=_d20(event_check_data["dc"], "significant_event_check.dc"),
            occurs=_boolean(event_check_data["occurs"], "significant_event_check.occurs"),
        )

        raw_attempts = payload["event_attempts"]
        if not isinstance(raw_attempts, list):
            raise WeatherSerializationError("event_attempts must be a JSON array")
        attempts = tuple(_attempt_from_dict(item, index) for index, item in enumerate(raw_attempts))
        selected_data = payload["selected_event"]
        selected_event = None if selected_data is None else _event_from_dict(selected_data, "selected_event")
        gm_resolution = _boolean(payload["gm_event_resolution_required"], "gm_event_resolution_required")
        reroll_exhausted = _boolean(
            payload["event_reroll_limit_exhausted"], "event_reroll_limit_exhausted"
        )

        secondary_data = payload["secondary_event_check"]
        if secondary_data is None:
            secondary_check = None
        else:
            secondary_data = _object(secondary_data, "secondary_event_check")
            secondary_check = SecondaryEventCheck(
                roll=_d20(secondary_data["roll"], "secondary_event_check.roll"),
                dc=_d20(secondary_data["dc"], "secondary_event_check.dc"),
                succeeds=_boolean(secondary_data["succeeds"], "secondary_event_check.succeeds"),
                gm_resolution_required=_boolean(
                    secondary_data["gm_resolution_required"],
                    "secondary_event_check.gm_resolution_required",
                ),
            )

        weather = DailyWeather(
            profile_id=profile_id,
            date=date,
            precipitation=precipitation,
            winter_temperature=temperature,
            significant_event_check=significant_check,
            event_attempts=attempts,
            selected_event=selected_event,
            gm_event_resolution_required=gm_resolution,
            event_reroll_limit_exhausted=reroll_exhausted,
            secondary_event_check=secondary_check,
        )
        _validate_weather(weather)
        return weather
    except WeatherSerializationError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise WeatherSerializationError(f"invalid stored weather: {error}") from error


def _event_to_dict(event: WeatherEventDefinition) -> dict[str, Any]:
    hazard = event.hazard
    if hazard.exact is not None:
        hazard_data = {"kind": "exact", "level": hazard.exact}
    elif hazard.choices:
        hazard_data = {"kind": "choices", "levels": list(hazard.choices)}
    else:
        hazard_data = {"kind": "open_ended", "minimum": hazard.minimum}
    return {"event": event.event.value, "hazard": hazard_data}


def _event_from_dict(value: Any, field: str) -> WeatherEventDefinition:
    data = _object(value, field)
    hazard_data = _object(data["hazard"], f"{field}.hazard")
    kind = _string(hazard_data["kind"], f"{field}.hazard.kind")
    if kind == "exact":
        hazard = HazardLevel(exact=_nonnegative_integer(hazard_data["level"], f"{field}.hazard.level"))
    elif kind == "choices":
        levels = hazard_data["levels"]
        if not isinstance(levels, list):
            raise WeatherSerializationError(f"{field}.hazard.levels must be a JSON array")
        hazard = HazardLevel(
            choices=tuple(
                _nonnegative_integer(level, f"{field}.hazard.levels[{index}]")
                for index, level in enumerate(levels)
            )
        )
    elif kind == "open_ended":
        hazard = HazardLevel(
            minimum=_nonnegative_integer(hazard_data["minimum"], f"{field}.hazard.minimum")
        )
    else:
        raise WeatherSerializationError(f"{field}.hazard.kind is not recognized: {kind}")
    return WeatherEventDefinition(
        event=WeatherEvent(_string(data["event"], f"{field}.event")),
        hazard=hazard,
    )


def _attempt_from_dict(value: Any, index: int) -> EventTableAttempt:
    field = f"event_attempts[{index}]"
    data = _object(value, field)
    return EventTableAttempt(
        roll=_d20(data["roll"], f"{field}.roll"),
        result=_event_from_dict(data["result"], f"{field}.result"),
        is_reroll=_boolean(data["is_reroll"], f"{field}.is_reroll"),
    )


def _validate_weather(weather: DailyWeather) -> None:
    if not isinstance(weather.date, CalendarDate):
        raise WeatherSerializationError("weather date must be a CalendarDate")
    if not isinstance(weather.profile_id, str) or not weather.profile_id.strip():
        raise WeatherSerializationError("weather profile_id must be a non-empty string")
    if weather.precipitation.occurs != (weather.precipitation.roll >= weather.precipitation.dc):
        raise WeatherSerializationError("precipitation outcome does not match its roll and DC")
    if (weather.precipitation.precipitation_type is PrecipitationType.NONE) == weather.precipitation.occurs:
        raise WeatherSerializationError("precipitation type does not match its outcome")

    temperature = weather.winter_temperature
    if temperature.check_occurred:
        if temperature.roll is None or temperature.dc is None:
            raise WeatherSerializationError("winter temperature check is missing its roll or DC")
        if temperature.mild_cold != (temperature.roll >= temperature.dc):
            raise WeatherSerializationError("Mild Cold outcome does not match its roll and DC")
    elif temperature.roll is not None or temperature.dc is not None or temperature.mild_cold:
        raise WeatherSerializationError("unchecked winter temperature must not contain check results")

    check = weather.significant_event_check
    if check.occurs != (check.roll >= check.dc):
        raise WeatherSerializationError("significant-event outcome does not match its roll and DC")
    if check.occurs:
        if not weather.event_attempts or weather.selected_event is None:
            raise WeatherSerializationError("successful significant check is missing its event result")
        if weather.selected_event != weather.event_attempts[-1].result:
            raise WeatherSerializationError("selected event does not match the last table attempt")
    elif weather.event_attempts or weather.selected_event is not None:
        raise WeatherSerializationError("failed significant check cannot contain an event-table result")

    for index, attempt in enumerate(weather.event_attempts):
        if attempt.is_reroll != (index > 0):
            raise WeatherSerializationError("event reroll flags are inconsistent with attempt order")
        if weather.profile_id == PROFILE_ID and attempt.result != event_for_roll(attempt.roll):
            raise WeatherSerializationError("event result does not match its Stolen Lands table roll")

    expected_gm_resolution = bool(
        weather.selected_event is not None and weather.selected_event.hazard.requires_gm_resolution
    ) or weather.event_reroll_limit_exhausted
    if weather.gm_event_resolution_required != expected_gm_resolution:
        raise WeatherSerializationError("GM event-resolution flag is inconsistent with the selected event")
    if weather.event_reroll_limit_exhausted and not weather.event_attempts:
        raise WeatherSerializationError("reroll exhaustion requires at least one event-table attempt")

    secondary = weather.secondary_event_check
    if check.natural_twenty != (secondary is not None):
        raise WeatherSerializationError("secondary check must be present only after an initial natural 20")
    if secondary is not None:
        if secondary.succeeds != (secondary.roll >= secondary.dc):
            raise WeatherSerializationError("secondary-check outcome does not match its roll and DC")
        if secondary.gm_resolution_required != secondary.succeeds:
            raise WeatherSerializationError("secondary GM-resolution flag does not match its outcome")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WeatherSerializationError(f"{field} must be a JSON object")
    return value


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise WeatherSerializationError(f"{field} must be an integer")
    return value


def _nonnegative_integer(value: Any, field: str) -> int:
    value = _integer(value, field)
    if value < 0:
        raise WeatherSerializationError(f"{field} must be non-negative")
    return value


def _d20(value: Any, field: str) -> int:
    value = _integer(value, field)
    if not 1 <= value <= 20:
        raise WeatherSerializationError(f"{field} must be from 1 to 20")
    return value


def _optional_d20(value: Any, field: str) -> int | None:
    return None if value is None else _d20(value, field)


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise WeatherSerializationError(f"{field} must be a boolean")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise WeatherSerializationError(f"{field} must be a string")
    return value

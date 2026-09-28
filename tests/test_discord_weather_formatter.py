import re
from dataclasses import replace

import pytest

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.discord_weather_formatter import format_weather
from kingmaker_bot.weather import KingmakerStolenLandsProfile, WeatherEngine


class Rolls:
    def __init__(self, values):
        self.values = iter(values)

    def roll(self, sides: int) -> int:
        return next(self.values)


def generate(date, rolls, level=1, max_rerolls=10):
    return WeatherEngine(KingmakerStolenLandsProfile(max_event_rerolls=max_rerolls), Rolls(rolls)).generate(date, level)


def test_formats_no_precipitation_and_no_event_without_audit_rolls() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [14, 16]))
    assert f"{CalendarDate(1, 3, 4710).weekday}, 1 Pharast 4710 AR — Spring" in output
    assert "Precipitation: No precipitation" in output
    assert "Significant weather: None" in output


def test_formats_rain_and_exact_hazard_level() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 17, 10]))
    assert "Precipitation: Light rain" in output
    assert "Windstorm, Hazard 1" in output


def test_formats_winter_snow_and_mild_cold() -> None:
    output = format_weather(generate(CalendarDate(1, 1, 4710), [8, 18, 17, 1]))
    assert "Light snow" in output
    assert "Temperature: Mild Cold" in output


def test_formats_ambiguous_hazard_and_gm_resolution() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 17, 17]))
    assert "Significant weather: Wildfire" in output
    assert "Ask the GM to confirm this event's hazard level and effects." in output
    assert "4 or 10" not in output


def test_formats_open_hazard_and_secondary_selection() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 20, 15, 20]))
    assert "Significant weather: Supernatural Storm" in output
    assert "Ask the GM to determine the additional weather effects." in output
    assert "Hazard 6+" not in output


def test_formats_event_reroll_exhaustion() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 17, 14, 14, 14], level=1, max_rerolls=1))
    assert "Significant weather: Blizzard" in output
    assert "Ask the GM to confirm this event's hazard level and effects." in output
    assert "reroll" not in output.lower()
    assert "Hazard 6" not in output


@pytest.mark.parametrize(
    ("date", "rolls", "level", "max_rerolls", "expected"),
    [
        (CalendarDate(23, 3, 4710), [14, 16], 1, 10, "Precipitation: No precipitation"),
        (CalendarDate(23, 3, 4710), [16, 15], 1, 10, "Precipitation: Light rain"),
        (CalendarDate(23, 1, 4710), [8, 18, 16], 1, 10, "Temperature: Mild Cold"),
        (CalendarDate(23, 1, 4710), [8, 15, 16], 1, 10, "Temperature: No Mild Cold"),
        (CalendarDate(23, 3, 4710), [15, 17, 10], 1, 10, "Windstorm, Hazard 1"),
        (CalendarDate(23, 3, 4710), [15, 17, 17], 1, 10, "Significant weather: Wildfire"),
        (CalendarDate(23, 3, 4710), [15, 17, 14, 14], 1, 1, "Significant weather: Blizzard"),
        (CalendarDate(23, 3, 4710), [15, 17, 14, 10], 1, 1, "Windstorm, Hazard 1"),
        (CalendarDate(23, 3, 4710), [15, 20, 15, 20], 1, 10, "additional weather effects"),
        (CalendarDate(23, 3, 4710), [15, 20, 10, 16], 1, 10, "Windstorm, Hazard 1"),
    ],
)
def test_weather_output_excludes_all_generation_metadata(date, rolls, level, max_rerolls, expected):
    weather = generate(date, rolls, level, max_rerolls)
    output = format_weather(weather)
    assert output.startswith(f"{date.weekday}, {date.day} {date.month_name} {date.year} AR — {date.season}")
    assert expected in output
    assert "Precipitation:" in output and "Significant weather:" in output
    for secret in (
        "vs dc", "dc", "roll", "check", "table", "candidate", "exhaust",
        "succeeded", "failed", "success", "failure", "is_false", "degree",
        "survival_total", "profile", "kingmaker_stolen_lands", "canonical",
        "revealed_at", "created_at", "gm_resolution_required",
    ):
        assert secret not in output.lower()
    # Dates and resolved hazard levels are results, not leaked generation values.
    body = output.split("\n", 1)[1]
    body = re.sub(r"Hazard \d+", "", body)
    assert re.findall(r"\d+", body) == []

    # Changing only audit metadata must never change what Discord displays.
    metadata_variant = replace(
        weather,
        profile_id="internal_profile_debug",
        precipitation=replace(weather.precipitation, roll=901, dc=902),
        winter_temperature=replace(weather.winter_temperature, roll=903, dc=904),
        significant_event_check=replace(weather.significant_event_check, roll=905, dc=906),
        event_attempts=tuple(replace(attempt, roll=907) for attempt in weather.event_attempts),
        secondary_event_check=(
            replace(weather.secondary_event_check, roll=908, dc=909)
            if weather.secondary_event_check is not None else None
        ),
    )
    assert format_weather(metadata_variant) == output
    if weather.secondary_event_check is not None and not weather.secondary_event_check.succeeds:
        assert "additional" not in output.lower()

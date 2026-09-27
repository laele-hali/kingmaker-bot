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


def test_formats_no_precipitation_and_no_event_with_audit_rolls() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [14, 16]))
    assert f"{CalendarDate(1, 3, 4710).weekday}, 1 Pharast 4710 AR — Spring" in output
    assert "Precipitation: No precipitation (14 vs DC 15)" in output
    assert "Significant weather: None (16 vs DC 17)" in output


def test_formats_rain_and_exact_hazard_level() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 17, 10]))
    assert "Precipitation: Light rain" in output
    assert "Windstorm, Hazard 1" in output


def test_formats_winter_snow_and_mild_cold() -> None:
    output = format_weather(generate(CalendarDate(1, 1, 4710), [8, 18, 17, 1]))
    assert "Light snow" in output
    assert "Mild Cold (18 vs DC 16)" in output


def test_formats_ambiguous_hazard_and_gm_resolution() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 17, 17]))
    assert "Wildfire, Hazard 4 or 10" in output
    assert "GM resolution required" in output


def test_formats_open_hazard_and_secondary_selection() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 20, 15, 20]))
    assert "Supernatural Storm, Hazard 6+" in output
    assert "Linked secondary event check succeeded" in output
    assert "GM selection required" in output


def test_formats_event_reroll_exhaustion() -> None:
    output = format_weather(generate(CalendarDate(1, 3, 4710), [15, 17, 14, 14, 14], level=1, max_rerolls=1))
    assert "Event reroll limit exhausted" in output

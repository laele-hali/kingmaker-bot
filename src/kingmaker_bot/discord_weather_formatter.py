"""Discord-friendly formatting for generated Kingmaker weather."""

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.models import DailyWeather, PrecipitationType


def _check(roll: int, dc: int) -> str:
    return f"{roll} vs DC {dc}"


def format_weather(weather: DailyWeather) -> str:
    """Format a weather result with rolls and any unresolved GM decisions."""
    date: CalendarDate = weather.date
    lines = [f"{date.weekday}, {date.day} {date.month_name} {date.year} AR — {date.season}"]

    precip = weather.precipitation
    names = {
        PrecipitationType.NONE: "No precipitation",
        PrecipitationType.RAIN: "Light rain",
        PrecipitationType.SNOW: "Light snow",
    }
    lines.append(f"Precipitation: {names[precip.precipitation_type]} ({_check(precip.roll, precip.dc)})")

    temperature = weather.winter_temperature
    if temperature.check_occurred:
        result = "Mild Cold" if temperature.mild_cold else "No Mild Cold"
        lines.append(f"Winter temperature: {result} ({_check(temperature.roll, temperature.dc)})")

    event_check = weather.significant_event_check
    if weather.selected_event is None:
        lines.append(f"Significant weather: None ({_check(event_check.roll, event_check.dc)})")
    else:
        event = weather.selected_event
        hazard = event.hazard
        if hazard.exact is not None:
            hazard_text = f"Hazard {hazard.exact}"
        elif hazard.choices:
            hazard_text = "Hazard " + " or ".join(map(str, hazard.choices))
        else:
            hazard_text = f"Hazard {hazard.minimum}+"
        lines.append(
            f"Significant weather: {event.event.value}, {hazard_text} "
            f"({_check(event_check.roll, event_check.dc)})"
        )
        if weather.gm_event_resolution_required:
            lines.append("GM resolution required for hazard level.")
    if weather.event_reroll_limit_exhausted:
        lines.append("Event reroll limit exhausted; GM resolution required.")

    secondary = weather.secondary_event_check
    if secondary is not None:
        if secondary.succeeds:
            lines.append(
                f"Linked secondary event check succeeded ({_check(secondary.roll, secondary.dc)}); "
                "GM selection required."
            )
        else:
            lines.append(f"Linked secondary event check failed ({_check(secondary.roll, secondary.dc)}).")
    return "\n".join(lines)

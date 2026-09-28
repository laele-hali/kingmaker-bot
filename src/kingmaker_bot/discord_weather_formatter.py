"""Discord-friendly formatting for generated Kingmaker weather."""

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.models import DailyWeather, PrecipitationType


def format_weather(weather: DailyWeather) -> str:
    """Present weather and gameplay results, keeping generation mechanics internal."""
    date: CalendarDate = weather.date
    lines = [f"{date.weekday}, {date.day} {date.month_name} {date.year} AR — {date.season}"]

    precip = weather.precipitation
    names = {
        PrecipitationType.NONE: "No precipitation",
        PrecipitationType.RAIN: "Light rain",
        PrecipitationType.SNOW: "Light snow",
    }
    lines.append(f"Precipitation: {names[precip.precipitation_type]}")

    temperature = weather.winter_temperature
    if temperature.check_occurred:
        result = "Mild Cold" if temperature.mild_cold else "No Mild Cold"
        lines.append(f"Temperature: {result}")

    if weather.selected_event is None:
        lines.append("Significant weather: None")
    else:
        event = weather.selected_event
        hazard = event.hazard
        needs_gm = (
            weather.gm_event_resolution_required
            or weather.event_reroll_limit_exhausted
            or hazard.requires_gm_resolution
        )
        event_text = f"Significant weather: {event.event.value}"
        if not needs_gm:
            event_text += f", Hazard {hazard.exact}"
        lines.append(event_text)
        if needs_gm:
            lines.append("Ask the GM to confirm this event's hazard level and effects.")

    secondary = weather.secondary_event_check
    if secondary is not None and secondary.gm_resolution_required:
        lines.append("Ask the GM to determine the additional weather effects.")
    return "\n".join(lines)

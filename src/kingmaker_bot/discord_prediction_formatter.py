"""Player-facing formatting for Predict Weather outcomes."""

from kingmaker_bot.prediction import DegreeOfSuccess, PredictionAttempt
from kingmaker_bot.weather import PrecipitationType


def format_prediction(attempt: PredictionAttempt) -> str:
    """Format the forecast only; never expose internal degree or false marker."""
    forecast = attempt.forecast
    target = attempt.forecast_date
    heading = f"Weather forecast for {target.weekday}, {target.day} {target.month_name} {target.year} AR"

    if attempt.degree is DegreeOfSuccess.FAILURE:
        return f"{heading}\nYou are unable to obtain a useful forecast."

    precipitation_names = {
        PrecipitationType.NONE: "No precipitation",
        PrecipitationType.RAIN: "Light rain",
        PrecipitationType.SNOW: "Light snow",
    }
    lines = [heading, f"Precipitation: {precipitation_names[forecast.precipitation]}."]
    if forecast.mild_cold is not None:
        temperature = "Mild Cold" if forecast.mild_cold else "No Mild Cold"
        lines.append(f"Temperature: {temperature}.")

    if forecast.significant_event_occurs:
        if forecast.event is None:
            lines.append("A significant weather event is expected during the day ahead.")
        else:
            lines.append(
                f"{forecast.event.event.value} is expected during the day ahead."
            )
            if forecast.event_gm_resolution_required:
                lines.append("The event's hazard level requires GM resolution.")
    else:
        lines.append("No significant weather event is expected during the day ahead.")

    bonus = forecast.preparation_bonus
    lines.append(
        f"You gain a +{bonus} circumstance bonus to Survival checks to prepare for this weather."
    )
    return "\n".join(lines)

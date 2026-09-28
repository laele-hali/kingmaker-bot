"""Predict Weather domain models and repository contract."""

from kingmaker_bot.prediction.models import (
    DegreeOfSuccess,
    PredictionAlreadyAttemptedError,
    PredictionWeatherRevealedError,
    PredictionAttempt,
    PredictionConditions,
    WeatherForecast,
    determine_degree_of_success,
)
from kingmaker_bot.prediction.repository import PredictionRepository

__all__ = [
    "DegreeOfSuccess",
    "PredictionAlreadyAttemptedError",
    "PredictionWeatherRevealedError",
    "PredictionAttempt",
    "PredictionConditions",
    "PredictionRepository",
    "WeatherForecast",
    "determine_degree_of_success",
]

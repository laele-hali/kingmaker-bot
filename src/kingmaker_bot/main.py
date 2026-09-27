"""Application entry point for the Kingmaker campaign bot."""

import os
from pathlib import Path

from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.database import SQLiteCampaignStateRepository, SQLiteWeatherRepository
from kingmaker_bot.discord_client import create_bot
from kingmaker_bot.weather import KingmakerStolenLandsProfile, PROFILE_ID, WeatherEngine

_DEFAULT_DATABASE_PATH = Path("data/kingmaker.db")


def main() -> None:
    """Start the bot using the token in ``DISCORD_BOT_TOKEN``."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN must be set to start the bot")

    database_path = os.environ.get("KINGMAKER_DATABASE_PATH", str(_DEFAULT_DATABASE_PATH))
    campaign_repository = SQLiteCampaignStateRepository(database_path)
    weather_repository = SQLiteWeatherRepository(database_path)
    weather_engine = WeatherEngine(KingmakerStolenLandsProfile())
    weather_service = WeatherService(weather_repository, {PROFILE_ID: weather_engine})
    create_bot(campaign_repository, weather_service).run(token)


if __name__ == "__main__":
    main()

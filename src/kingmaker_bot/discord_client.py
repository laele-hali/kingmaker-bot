"""Discord client setup and command registration."""

import discord
from discord import app_commands

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.application.health import ping_response
from kingmaker_bot.application.predict_weather_service import PredictWeatherService
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.campaign import CampaignStateRepository
from kingmaker_bot.discord_calendar_commands import register_calendar_commands


class KingmakerClient(discord.Client):
    """Discord transport adapter for the campaign application."""

    def __init__(
        self,
        repository: CampaignStateRepository,
        weather_service: WeatherService,
        prediction_service: PredictWeatherService,
    ) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

        @self.tree.command(name="ping", description="Check whether the bot is responding")
        async def ping(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(ping_response())

        register_calendar_commands(
            self.tree, CalendarService(repository), weather_service, prediction_service
        )

    async def setup_hook(self) -> None:
        await self.tree.sync()


def create_bot(
    repository: CampaignStateRepository,
    weather_service: WeatherService,
    prediction_service: PredictWeatherService,
) -> KingmakerClient:
    """Create the Discord client using an application-provided repository."""
    return KingmakerClient(repository, weather_service, prediction_service)

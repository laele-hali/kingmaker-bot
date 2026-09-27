import asyncio
from unittest.mock import AsyncMock

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign import CampaignState
from kingmaker_bot.database import SQLiteCampaignStateRepository, SQLiteWeatherRepository
from kingmaker_bot.discord_calendar_commands import register_calendar_commands
from kingmaker_bot.weather import KingmakerStolenLandsProfile, PROFILE_ID, WeatherEngine


class CountingRolls:
    def __init__(self, values=(15, 1)):
        self.values = iter(values)
        self.count = 0

    def roll(self, sides: int) -> int:
        self.count += 1
        return next(self.values)


class FakeTree:
    def add_command(self, command) -> None:
        self.command = command


def command_interaction(guild_id=111):
    interaction = AsyncMock()
    interaction.guild_id = guild_id
    return interaction


def services(tmp_path, values=(15, 1)):
    campaigns = SQLiteCampaignStateRepository(tmp_path / "state.sqlite3")
    dice = CountingRolls(values)
    engine = WeatherEngine(KingmakerStolenLandsProfile(), dice)
    weather = WeatherService(
        SQLiteWeatherRepository(tmp_path / "state.sqlite3"), {PROFILE_ID: engine}
    )
    tree = FakeTree()
    group = register_calendar_commands(tree, CalendarService(campaigns), weather)
    return campaigns, dice, group


def test_level_command_displays_missing_and_configured_level(tmp_path) -> None:
    campaigns, _, group = services(tmp_path)
    campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710)))
    command = group.get_command("level")

    missing = command_interaction()
    asyncio.run(command.callback(missing))
    missing.response.send_message.assert_awaited_once_with(
        "No party level is configured. Set one with /calendar level <level>."
    )

    setting = command_interaction()
    asyncio.run(command.callback(setting, 4))
    setting.response.send_message.assert_awaited_once_with("Party level set to 4.")

    viewing = command_interaction()
    asyncio.run(command.callback(viewing))
    viewing.response.send_message.assert_awaited_once_with("Configured party level: 4.")


def test_level_command_invalid_level_is_clear(tmp_path) -> None:
    campaigns, _, group = services(tmp_path)
    campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710)))
    interaction = command_interaction()
    asyncio.run(group.get_command("level").callback(interaction, 21))
    interaction.response.send_message.assert_awaited_once_with(
        "Party level must be between 1 and 20.", ephemeral=True
    )


def test_weather_command_handles_unconfigured_campaign_and_party_level(tmp_path) -> None:
    campaigns, _, group = services(tmp_path)

    no_campaign = command_interaction()
    asyncio.run(group.get_command("weather").callback(no_campaign))
    no_campaign.response.send_message.assert_awaited_once_with(
        "No campaign calendar is configured for this server."
    )

    campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710)))
    no_level = command_interaction()
    asyncio.run(group.get_command("weather").callback(no_level))
    no_level.response.send_message.assert_awaited_once_with(
        "No party level is configured. Set one with /calendar level <level>."
    )


def test_weather_uses_current_date_generates_once_and_reveals_canonical_record(tmp_path) -> None:
    campaigns, dice, group = services(tmp_path)
    campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710), party_level=3))
    command = group.get_command("weather")
    first = command_interaction()
    asyncio.run(command.callback(first))
    response = first.response.send_message.await_args.args[0]
    assert response.startswith(f"{CalendarDate(1, 3, 4710).weekday}, 1 Pharast 4710 AR — Spring")
    assert "Light rain" in response
    assert "Significant weather: None" in response
    assert dice.count == 2

    second = command_interaction()
    asyncio.run(command.callback(second))
    assert second.response.send_message.await_args.args[0] == response
    assert dice.count == 2

    import sqlite3
    with sqlite3.connect(tmp_path / "state.sqlite3") as connection:
        revealed_at = connection.execute("SELECT revealed_at FROM daily_weather").fetchone()[0]
    assert revealed_at is not None


def test_weather_failure_is_not_exposed_to_discord(tmp_path) -> None:
    campaigns, _, group = services(tmp_path, values=())

    campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710), party_level=3))
    # Exhausting the deterministic source causes an engine failure at the Discord boundary.
    interaction = command_interaction()
    asyncio.run(group.get_command("weather").callback(interaction))
    assert interaction.response.send_message.await_args.args[0] == (
        "Weather could not be generated or loaded. Please try again later."
    )

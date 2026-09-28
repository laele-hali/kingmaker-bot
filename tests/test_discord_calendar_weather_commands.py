import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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


def command_interaction(guild_id=111, user_id=222):
    interaction = AsyncMock()
    interaction.guild_id = guild_id
    interaction.user = SimpleNamespace(id=user_id)
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


def open_confirmation(group, user_id=222):
    interaction = command_interaction(user_id=user_id)
    asyncio.run(group.get_command("weather").callback(interaction))
    response = interaction.response.send_message.await_args
    assert response.kwargs["ephemeral"] is True
    return response.kwargs["view"], response.args[0]


def press(view, label, user_id=222):
    interaction = command_interaction(user_id=user_id)
    button = next(item for item in view.children if item.label == label)
    asyncio.run(button.callback(interaction))
    return interaction


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


@pytest.mark.parametrize("hidden", [False, True])
def test_weather_confirmation_reveals_once_and_repeats_without_confirmation(tmp_path, hidden):
    campaigns, dice, group = services(tmp_path)
    campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710), party_level=3))
    command = group.get_command("weather")
    repository = SQLiteWeatherRepository(tmp_path / "state.sqlite3")
    before = None
    if hidden:
        before = repository.save_generated(
            111, WeatherEngine(KingmakerStolenLandsProfile(), dice).generate(CalendarDate(1, 3, 4710), 3)
        )
    consumed = dice.count
    view, prompt = open_confirmation(group)
    assert repository.get(111, CalendarDate(1, 3, 4710), PROFILE_ID) == before
    assert dice.count == consumed
    assert "1 Pharast 4710 AR" in prompt
    assert "Predict Weather can no longer be attempted" in prompt
    for secret in ("rain", "precipitation", "DC", "Significant weather", "15", "revealed_at"):
        assert secret not in prompt
    assert [item.label for item in view.children] == ["Reveal Weather", "Cancel"]
    first = press(view, "Reveal Weather")
    response = first.response.send_message.await_args.args[0]
    assert first.response.send_message.await_args.kwargs["ephemeral"] is False
    assert response.startswith(f"{CalendarDate(1, 3, 4710).weekday}, 1 Pharast 4710 AR — Spring")
    assert "Light rain" in response
    assert "Significant weather: None" in response
    assert dice.count == 2
    revealed = repository.get(111, CalendarDate(1, 3, 4710), PROFILE_ID)
    assert revealed.revealed_at is not None
    if before is not None:
        assert revealed.weather == before.weather
        assert revealed.created_at == before.created_at

    second = command_interaction()
    asyncio.run(command.callback(second))
    assert second.response.send_message.await_args.args[0] == response
    assert dice.count == 2
    assert "view" not in second.response.send_message.await_args.kwargs
    assert repository.get(111, CalendarDate(1, 3, 4710), PROFILE_ID) == revealed


def test_weather_failure_is_not_exposed_to_discord(tmp_path) -> None:
    campaigns, _, group = services(tmp_path, values=())

    campaigns.save(CampaignState(111, CalendarDate(1, 3, 4710), party_level=3))
    # Exhausting the deterministic source causes an engine failure at the Discord boundary.
    view, _ = open_confirmation(group)
    interaction = press(view, "Reveal Weather")
    assert interaction.response.send_message.await_args.args[0] == (
        "Weather could not be generated or loaded. Please try again later."
    )
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True


@pytest.mark.parametrize("hidden", [False, True])
@pytest.mark.parametrize("action", ["Cancel", "timeout"])
def test_cancel_and_timeout_have_no_gameplay_effect(tmp_path, hidden, action):
    campaigns, dice, group = services(tmp_path)
    date = CalendarDate(20, 3, 4710)
    campaigns.save(CampaignState(111, date, party_level=3))
    repository = SQLiteWeatherRepository(tmp_path / "state.sqlite3")
    before = None
    if hidden:
        before = repository.save_generated(
            111, WeatherEngine(KingmakerStolenLandsProfile(), dice).generate(date, 3)
        )
    consumed = dice.count
    view, _ = open_confirmation(group)
    assert view.timeout == 300
    if action == "Cancel":
        cancelled = press(view, action)
        cancelled.response.send_message.assert_not_awaited()
        cancelled.response.edit_message.assert_awaited_once_with(
            content="Weather reveal cancelled.", view=None
        )
    else:
        asyncio.run(view.on_timeout())
    assert view.is_finished()
    assert all(item.disabled for item in view.children)
    late_click = press(view, "Reveal Weather")
    assert late_click.response.send_message.await_args.kwargs["ephemeral"] is True
    assert repository.get(111, date, PROFILE_ID) == before
    assert dice.count == consumed


@pytest.mark.parametrize("action", ["Reveal Weather", "Cancel"])
def test_only_invoking_user_can_use_confirmation(tmp_path, action):
    campaigns, dice, group = services(tmp_path)
    date = CalendarDate(20, 3, 4710)
    campaigns.save(CampaignState(111, date, party_level=3))
    view, _ = open_confirmation(group)
    intruder = press(view, action, user_id=999)
    intruder.response.send_message.assert_awaited_once_with(
        "Only the person who requested this confirmation can use it.", ephemeral=True
    )
    intruder.response.edit_message.assert_not_awaited()
    assert not view.is_finished()
    assert dice.count == 0
    assert SQLiteWeatherRepository(tmp_path / "state.sqlite3").get(111, date, PROFILE_ID) is None
    owner = press(view, "Reveal Weather")
    assert owner.response.send_message.await_args.kwargs["ephemeral"] is False
    assert dice.count == 2


def test_changed_campaign_date_invalidates_confirmation_without_generation(tmp_path):
    campaigns, dice, group = services(tmp_path)
    date = CalendarDate(20, 3, 4710)
    campaigns.save(CampaignState(111, date, party_level=3))
    view, _ = open_confirmation(group)
    campaigns.save(CampaignState(111, date.advance(), party_level=3))
    result = press(view, "Reveal Weather")
    assert result.response.send_message.await_args.kwargs["ephemeral"] is True
    assert "campaign date has changed" in result.response.send_message.await_args.args[0]
    assert dice.count == 0


def test_two_pending_reveals_share_weather_and_first_timestamp(tmp_path):
    campaigns, dice, group = services(tmp_path)
    date = CalendarDate(20, 3, 4710)
    campaigns.save(CampaignState(111, date, party_level=3))
    first, _ = open_confirmation(group)
    second, _ = open_confirmation(group, user_id=333)
    repository = SQLiteWeatherRepository(tmp_path / "state.sqlite3")
    first_reveal = []

    async def confirm_both():
        one, two = command_interaction(), command_interaction(user_id=333)
        async def capture_first_reveal(*args, **kwargs):
            first_reveal.append(repository.get(111, date, PROFILE_ID))
            # Let the second callback run while the first public response is pending.
            await asyncio.sleep(0)
        one.response.send_message.side_effect = capture_first_reveal
        await asyncio.gather(first.reveal.callback(one), second.reveal.callback(two))
        return one, two

    one, two = asyncio.run(confirm_both())
    revealed = repository.get(111, date, PROFILE_ID)
    assert one.response.send_message.await_args == two.response.send_message.await_args
    assert revealed.revealed_at is not None
    assert revealed == first_reveal[0]
    assert dice.count == 2
    repeated = press(first, "Reveal Weather")
    assert repeated.response.send_message.await_args.kwargs["ephemeral"] is True
    assert repository.get(111, date, PROFILE_ID) == revealed

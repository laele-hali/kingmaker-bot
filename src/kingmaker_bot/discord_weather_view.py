"""Private confirmation for deliberate public weather revelation."""

import discord

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.discord_weather_formatter import format_weather
from kingmaker_bot.weather import PROFILE_ID


class RevealWeatherView(discord.ui.View):
    """One user's finite-lived confirmation, bound to a campaign date."""

    def __init__(
        self,
        calendar_service: CalendarService,
        weather_service: WeatherService,
        guild_id: int,
        user_id: int,
        date: CalendarDate,
    ) -> None:
        super().__init__(timeout=300)
        self._calendar = calendar_service
        self._weather = weather_service
        self._guild_id = guild_id
        self._user_id = user_id
        self._date = date
        self._closed = False

    @property
    def confirmation(self) -> str:
        date = self._date
        return (
            f"Reveal weather for {date.weekday}, {date.day} {date.month_name} {date.year} AR?\n\n"
            "This will reveal the day's actual weather and mechanical details to everyone "
            "in this channel.\n\n"
            "Once revealed, Predict Weather can no longer be attempted for this campaign day."
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._user_id or interaction.guild_id != self._guild_id:
            await interaction.response.send_message(
                "Only the person who requested this confirmation can use it.", ephemeral=True
            )
            return False
        if self._closed:
            await interaction.response.send_message(
                "This weather confirmation has expired or already been handled.", ephemeral=True
            )
            return False
        return True

    def _close(self) -> None:
        self._closed = True
        for item in self.children:
            item.disabled = True
        self.stop()

    async def on_timeout(self) -> None:
        self._close()

    @discord.ui.button(label="Reveal Weather", style=discord.ButtonStyle.danger)
    async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Recheck even for callbacks already queued when this view was closed.
        if not await self.interaction_check(interaction):
            return
        self._close()
        try:
            state = self._calendar.get_campaign_state(self._guild_id)
            if state is None or state.current_date != self._date:
                await interaction.response.send_message(
                    "The campaign date has changed. Run /calendar weather again to confirm "
                    "the current date.", ephemeral=True,
                )
                return
            if state.party_level is None:
                await interaction.response.send_message(
                    "No party level is configured. Set one with /calendar level <level>.",
                    ephemeral=True,
                )
                return
            # No await separates generation, canonical lookup, and marking. In the
            # current single-client event loop another command cannot interleave here.
            canonical = self._weather.get_or_generate(
                self._guild_id, self._date, state.party_level, PROFILE_ID
            )
            output = format_weather(canonical.weather)
            if canonical.revealed_at is None:
                if self._weather.reveal(self._guild_id, self._date, PROFILE_ID) is None:
                    raise RuntimeError("weather disappeared before reveal")
        except Exception:
            await interaction.response.send_message(
                "Weather could not be generated or loaded. Please try again later.", ephemeral=True
            )
            return
        # A new public interaction response, not an edit to the private prompt.
        await interaction.response.send_message(output, ephemeral=False)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.interaction_check(interaction):
            return
        self._close()
        await interaction.response.edit_message(content="Weather reveal cancelled.", view=None)

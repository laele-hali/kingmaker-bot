# Kingmaker Discord Bot

A Discord bot for Pathfinder 2e campaign calendar and weather management, initially supporting Kingmaker's Stolen Lands. For session use, see [USER_GUIDE.md](USER_GUIDE.md).

## Current development status

The calendar, guild-scoped campaign persistence, Discord calendar commands, RAW Kingmaker weather engine, canonical weather persistence, and Predict Weather workflow are implemented and covered by automated tests. Development remains incremental; the future features below are not available commands.

The project uses Python 3.12, discord.py, SQLite through the standard-library `sqlite3` module, pytest, and Docker Compose.

## Implemented features

### Golarion calendar and campaign state

- Absalom Reckoning (AR), all twelve Golarion months, seven weekdays, and seasonal groupings.
- Eight-year leap cycle: years divisible by 8 have an extra day in Calistril. This is not the Gregorian leap rule.
- Weekday epoch: 1 Abadius, 1 AR is Moonday. Dates require a positive year; advancement requires a positive whole number of days.
- Independent campaign state per Discord guild (server): current date and optional party level.
- Explicit calendar configuration; unknown guilds receive no default campaign date.
- Party-level configuration from 1 to 20, required for weather and predictions and used in weather hazard handling. Changing the date preserves the configured party level.

### RAW Kingmaker Stolen Lands weather

The current profile is `kingmaker_stolen_lands`. The profile-driven engine implements the supplied published daily procedure: seasonal precipitation, winter temperature, significant-event checks and selection, party-level hazard handling, and linked secondary-event checks. It records rolls and unresolved GM decisions without reproducing full hazard descriptions.

Weather is generated for an explicit date and stored canonically by guild, date, and profile. Repeated requests return the stored result rather than rerolling it, including after party-level changes. Date changes alone do not generate weather for elapsed days.

Stored records distinguish generation from revelation through `generated_at` and nullable `revealed_at`. Predict Weather can generate future weather invisibly; `/calendar weather` reveals the same stored weather once that date becomes current. Revealing weather does not replace it.

### Predict Weather

Players select observation conditions and submit their **final Survival check total** through a modal. The bot forecasts the **next campaign day**, approximating a 24-hour forecast with calendar-day granularity.

- Predict Weather DCs and degree-of-success labels are intentionally hidden from players. The submitted total is not posted publicly.
- Every resolved result is posted publicly in the invoking channel, including an inability to obtain a useful forecast.
- Prerequisite, validation, application, and duplicate-attempt errors remain private/ephemeral.
- Attempts are persisted and limited to once per Discord user per campaign date in the guild and current profile. The 24-hour usage restriction is approximated as once per campaign date, not elapsed real time. There is no separate character identity.
- Successful forecasts use canonical weather, with detail depending on the internal outcome. Critical-failure false forecasts never modify or reveal the canonical weather record.
- The existing false-forecast model deliberately presents a confident detailed forecast with a +2 preparation bonus; that displayed bonus does not establish critical success.
- Internal totals, conditions, check DCs, degrees, and forecasts are retained in prediction persistence.

## Discord command overview

All `/calendar` commands operate in a server. Arguments shown below are Discord slash-command options; brackets indicate an optional argument.

| Command | Current behavior |
| --- | --- |
| `/ping` | Check whether the bot responds. |
| `/calendar date` | Show the current campaign date, weekday, and season. |
| `/calendar set day:<integer> month:<integer> year:<integer>` | Create or update the campaign date; month is 1–12. |
| `/calendar advance days:<integer>` | Advance a configured calendar by a positive number of days. |
| `/calendar level [level:<integer>]` | Show party level, or set it to 1–20 on a configured campaign. |
| `/calendar weather` | Generate if absent, then reveal current-day canonical weather, including generation rolls/DCs and GM-resolution notes. |
| `/calendar predict conditions:<choice>` | Open the Survival-total modal and resolve a next-day forecast. |

Prediction choices are **Good visibility / commanding view**, **Normal conditions**, and **Poor visibility**.

The bot currently has no GM-role or administrator authorization checks for calendar commands. The GM/player distinction in the user guide describes intended table use, not enforced permissions. `/calendar weather` replies publicly in the invoking channel; use an appropriately restricted channel for GM information.

## Architecture and project structure

Discord handlers validate interface input, call application services, and format responses. Calendar, weather, and prediction logic do not require Discord objects. Repository contracts keep application/domain code separate from SQLite, and Kingmaker probabilities reside in the weather profile rather than the global engine.

```text
src/kingmaker_bot/
    application/                    Calendar, weather, prediction use cases
    calendar/                       Independent Golarion calendar domain
    campaign/                       Campaign state and repository contract
    weather/                        Engine, profiles, events, records, repository contract
    prediction/                     Forecasts, outcomes, attempts, repository contract
    database/                       SQLite repositories and serialization
    services/                       Package placeholder; orchestration is in application/
    discord_calendar_commands.py    Slash commands and prediction modal
    discord_weather_formatter.py    World-weather presentation
    discord_prediction_formatter.py Character-facing forecast presentation
    discord_client.py               Client setup and command synchronization
    main.py                         Configuration and dependency wiring
tests/                              Domain, repository, service, and Discord-adapter tests
compose.yaml                        Docker development service
Dockerfile                          Python 3.12 development image
```

## Local development with Docker Compose

Install Docker with Docker Compose support. From the repository root:

1. Create a local `.env` file. Compose expects this file even for tests; it can be empty when not running the bot. Supply the bot token locally when connecting to Discord. Never commit credentials.
2. Create the database parent directory and build the image:

   ```sh
   mkdir -p data
   docker compose build
   ```

3. Start the bot using the configured Discord application, installed in the intended server:

   ```sh
   docker compose run --rm dev kingmaker-bot
   ```

The client synchronizes its command tree on startup. The Compose service mounts the repository at `/workspace` and sets `PYTHONPATH=/workspace/src`, so local source edits are used in the container. Rebuild the image after changing dependencies.

For an interactive development shell:

```sh
docker compose run --rm dev bash
```

### Environment variables

| Variable | Requirement | Purpose |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | Required to run the bot; not needed for tests | Discord bot credential, supplied externally or through the ignored local `.env`. |
| `KINGMAKER_DATABASE_PATH` | Optional | SQLite path; defaults to `data/kingmaker.db`. |
| `PYTHONPATH` | Set by Compose | `/workspace/src` for local source imports. |

No token or other secret belongs in source control or documentation.

### Persistence

The default database is `/workspace/data/kingmaker.db` inside the container, corresponding to `data/kingmaker.db` in the repository directory on the host. The bind mount preserves it when the temporary container exits. For a custom path, ensure its parent directory exists and is writable; use a mounted location to retain data after container removal.

SQLite stores campaign state, canonical weather, and prediction attempts. Schema initialization is safe to repeat. Prediction records include internal check information and potentially hidden weather-derived data. Keep databases private and out of Git; `*.db` and `.env` are ignored. Exclude any custom database filename not covered by that pattern too. Tests use temporary databases.

### Running tests

Run all project tooling in Docker:

```sh
docker compose run --rm dev pytest
git diff --check
```

Tests cover domain boundaries, persistence, services, formatting, and command/modal callbacks with mocked Discord interactions. They do not connect to a live Discord server.

## Current limitations

- One configured campaign per guild; no character sheets, feat eligibility checks, or per-character attempt tracking.
- No application-enforced GM-only command permissions.
- Only `kingmaker_stolen_lands` is wired into the bot; there is no region/profile selection command or natural-weather mode.
- Ordinary wind and exact event timing are not modelled. Forecast and usage periods use campaign dates rather than a time-of-day clock.
- Only the final Survival total is collected; natural-die degree adjustments cannot be applied.
- Ambiguous hazard levels and successful linked secondary-event checks require GM resolution. Event rerolls have a safety limit that also flags GM resolution when exhausted.
- Terrain/location is not configured or automatically resolved; consult the published hazard rules for applicability and effects.
- Stored weather and prediction attempts have no Discord history browser, edit, reset, or reroll command.

## Planned / future features — not implemented

Future work may include weather-history and GM/admin interfaces, explicit reroll tools, optional natural-weather continuity, additional regional or climate profiles, and VTT/web integrations. These remain separate from the implemented RAW profile. Custom or derived models must be distinguished from published rules.

## Rules and copyright

This is an unofficial fan-made utility, not affiliated with or endorsed by Paizo. Pathfinder and Kingmaker belong to Paizo. Consult the appropriate rulebooks for complete rules and hazard descriptions; this project does not reproduce them.

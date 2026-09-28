# AGENTS.md

## Project Overview

This repository contains a Discord bot for Pathfinder 2e campaign
management.

The current target campaign is Kingmaker, with the stable core covering:

- Golarion calendar tracking
- Persistent campaign state
- Stolen Lands weather generation
- Predict Weather support

The v1.0 core behavior is stable. Preserve its established semantics unless
the current task explicitly requests a behavioral change:

- Canonical weather is generated once and reused.
- Generated weather is not automatically revealed.
- Predict Weather targets the current campaign date without revealing actual weather.
- The first actual-weather reveal is deliberate and requires confirmation.
- Public Discord output shows results/gameplay information, not generation machinery.
- Future history/reporting must never expose hidden or unrevealed weather.

Weather history and reporting are future work, not implemented core features.

The architecture should remain sufficiently generic that the calendar,
weather engine, and campaign services can later support other Pathfinder
2e campaigns, regions, climate profiles, and external interfaces.

Do not expand the implementation into future features unless they are
explicitly part of the current task.

---

## Development Environment

Development is performed using Docker.

Use the project's Docker development environment when running Python,
tests, or project tooling.

The project currently targets:

- Python 3.12
- discord.py
- pytest
- SQLite
- Docker / Docker Compose

The repository is mounted into the development container at:

    /workspace

The source package is located at:

    /workspace/src

Run tests using:

    docker compose run --rm dev pytest

Do not introduce additional dependencies unless they provide a clear
benefit and are required by the current task.

Prefer Python standard-library functionality where practical.

---

## Project Structure

The project separates external interfaces from application and game
logic.

Current and planned responsibilities are:

    src/kingmaker_bot/
        application/
            Application-level use cases and orchestration.

        calendar/
            Golarion calendar domain logic.

        database/
            Persistence implementations and database infrastructure.

        services/
            Coordination between domain logic, repositories, and
            external interfaces.

        weather/
            Weather domain models, weather profiles, and generation
            logic.

        discord_client.py
            Discord integration.

        main.py
            Application entry point.

Discord-specific code must not contain core calendar, weather, or
Pathfinder rules logic.

Domain logic should remain independently testable without connecting to
Discord.

---

## Development Principles

Prefer simple, explicit implementations over unnecessary abstraction.

However, maintain boundaries where they protect known future
requirements.

In particular:

- Keep Discord separate from game logic.
- Keep persistence separate from domain logic.
- Keep calendar logic independent of campaign-specific rules.
- Keep weather generation independent of Discord.
- Keep weather rules configurable through weather profiles.
- Keep external integrations outside the core domain.

Do not prematurely implement speculative features.

Future requirements documented in this file should influence
architecture where appropriate, but should not automatically become
part of the current implementation.

---

## Testing

Use pytest.

New domain, persistence, service, and application behaviour should have
automated tests.

Tests should cover normal behaviour as well as important boundaries and
invalid input.

Bug fixes should normally include a regression test.

Run the complete test suite before considering a task complete.

Do not modify existing tests merely to make an incorrect implementation
pass.

If a test expectation is discovered to be incorrect, explain why before
changing it.

---

## Git

Do not create Git commits unless explicitly instructed to do so.

Do not push changes unless explicitly instructed.

Do not commit:

- SQLite database files
- .env files
- Discord tokens
- credentials
- generated caches
- local virtual environments

Before completing a coding task, report:

- Files created
- Files modified
- Tests run
- Test results
- Any design decisions or unresolved issues

---

## Configuration and Secrets

Secrets must not be stored in source code.

The Discord bot token and any future credentials should be supplied
through environment variables or another external configuration
mechanism.

Local configuration containing credentials must remain excluded from
Git.

---

# Domain Requirements

## Golarion Calendar

The calendar domain represents the Golarion calendar using Absalom
Reckoning.

It is not a Kingmaker-specific calendar.

Calendar code must not depend on:

- Kingmaker
- The Stolen Lands
- Discord
- weather generation
- campaign persistence
- a specific campaign or guild

The calendar should be usable independently by other Pathfinder
campaigns and future interfaces.

### Months

The calendar uses the following months:

1. Abadius - 31 days
2. Calistril - 28 days normally, 29 in a leap year
3. Pharast - 31 days
4. Gozran - 30 days
5. Desnus - 31 days
6. Sarenith - 30 days
7. Erastus - 31 days
8. Arodus - 31 days
9. Rova - 30 days
10. Lamashan - 31 days
11. Neth - 30 days
12. Kuthona - 31 days

### Leap Years

The project uses an eight-year leap cycle.

A year is a leap year when it is evenly divisible by 8.

Examples:

    4704 - leap year
    4708 - not a leap year
    4710 - not a leap year
    4712 - leap year
    4720 - leap year

Do not substitute Gregorian leap-year rules.

### Weekdays

The weekdays are:

1. Moonday
2. Toilday
3. Wealday
4. Oathday
5. Fireday
6. Starday
7. Sunday

The weekday epoch used by this project is:

    1 Abadius, 1 AR = Moonday

### Seasons

Seasons are:

Spring:
- Pharast
- Gozran
- Desnus

Summer:
- Sarenith
- Erastus
- Arodus

Autumn:
- Rova
- Lamashan
- Neth

Winter:
- Kuthona
- Abadius
- Calistril

---

## Campaign State

Campaign state is scoped by Discord guild ID.

Different Discord guilds must have independent campaign state.

An unknown guild must not silently receive an arbitrary default
campaign date.

A campaign should be explicitly configured before campaign-dependent
commands operate on it.

Campaign state includes:

- Discord guild ID
- Current Golarion date
- Optional party level

Party level must be configured before weather generation and prediction.

Future campaign configuration may include:

- Region
- Weather profile
- Terrain or current location
- Weather mode

Do not implement future campaign fields merely because they are listed
here.

Region and weather profile are separate concepts.

For example:

    region_id = "stolen_lands"
    weather_profile_id = "kingmaker_stolen_lands"

This distinction should be preserved when those features are eventually
implemented.

---

## Persistence

SQLite is the initial persistence implementation.

Use Python's standard sqlite3 module unless a future requirement
provides a compelling reason to change this.

Database access should be isolated behind repository or persistence
interfaces so that application and domain code do not depend directly
on SQLite.

Database paths should be configurable.

Tests involving SQLite should use temporary test databases rather than
the development database.

Schema initialisation should be safe and idempotent.

Database files must not be committed to Git.

Do not introduce an ORM or migration framework unless explicitly
required.

---

# Weather

## Weather Architecture

Weather generation must be profile-driven.

Do not make the global weather engine synonymous with Kingmaker or the
Stolen Lands.

The current supported weather profile implements the published
Kingmaker Stolen Lands weather procedure.

Conceptually:

    WeatherService
        |
        +-- WeatherProfile
                |
                +-- KingmakerStolenLandsWeatherProfile
                |
                +-- future profiles

The exact class structure does not need to match this example if a
simpler implementation provides the same separation.

The important requirement is that Kingmaker-specific probabilities and
rules do not become global assumptions throughout the application.

---

## Weather Profiles

A weather profile defines how weather is generated for a particular
ruleset or climate model.

The initial profile is:

    kingmaker_stolen_lands

Future profiles may represent:

- Other published Pathfinder regions
- Cold climates
- Temperate climates
- Arid climates
- Tropical climates
- Custom campaign climates
- Derived climate models

Do not implement these future profiles until explicitly requested.

Official published rules and custom or derived weather models must
remain distinguishable.

The application must never represent a custom or statistically derived
weather profile as an official Pathfinder rule.

---

## Kingmaker Weather

The current weather implementation follows the Stolen Lands weather
procedure supplied for the project.

It includes:

- Seasonal precipitation checks
- Winter temperature checks
- Significant weather-event checks
- Weather-event selection
- Party-level restrictions for hazards
- Secondary events where applicable
- Terrain restrictions where applicable

Do not invent, reinterpret, or silently modify Pathfinder or Kingmaker
rules.

If a required rule is ambiguous or missing, stop and ask rather than
making up behaviour.

Avoid reproducing substantial copyrighted Pathfinder or Kingmaker rules
text in source files or public documentation.

Store only the rules data and descriptions necessary for the software
to function.

---

## Weather Generation

Weather generation should operate on an explicit date.

Conceptually:

    generate_weather(
        date,
        weather_profile,
        party_level,
        ...
    )

Do not design weather generation so that it can operate only on the
campaign's current date.

The engine remains date-independent even though the current Predict Weather
workflow targets the current campaign date.

Weather generation must remain deterministic with respect to a stored
weather result:

Once weather has been generated and persisted for a campaign and date,
normal application operations must retrieve that weather rather than
silently generating a different result.

Explicit GM/admin reroll functionality may be added later.

---

## Weather Persistence

Weather is persisted by guild, Golarion date, and weather profile.

A stored weather record should retain enough information to explain the
generated result and support future weather history.

Weather must be capable of existing in the database without having been
revealed to players.

A weather record distinguishes:

    generated weather
    created_at
    revealed_at

where `revealed_at` may be null.

This allows weather to be generated by forecasting without exposing the
actual result.

A forecast must never alter, replace, or reroll the actual stored
weather.

Generated is not revealed. Revealed means deliberately exposed through the
public `/calendar weather` reveal workflow. The first reveal requires an
ephemeral, invoking-user-only confirmation with Reveal Weather and Cancel.
Opening, cancelling, or timing out a confirmation must not generate weather,
reveal existing weather, or change prediction attempts. On confirmation,
reuse or generate canonical weather, mark it revealed once, and publicly
display its weather results and relevant gameplay information. Already-revealed weather is displayed without
confirmation, regeneration, or changing its first reveal timestamp.

Discord presentation must separate RESULT from GENERATION MECHANICS.
Public weather output shows weather results and required gameplay effects.
Raw generation rolls, generation DCs, event-table roll values, discarded candidates,
reroll machinery, and secret prediction mechanics remain internal. Preserve
all generation metadata in domain models and persistence.

Resolved hazard levels and forecast preparation bonuses may be displayed as
gameplay information. Unresolved hazard choices or additional weather effects
should use a minimal request for GM adjudication without exposing the internal
selection process. Do not invent GM-only permissions or a separate GM command.
Private confirmations and errors must also use natural player-facing language;
never forward raw exception text or database details to Discord.

---

## Weather History

Generated weather should eventually form a historical campaign weather
dataset.

Requesting weather for a previously generated campaign date should
return the stored result.

Historical data may later be used for:

- Campaign weather history
- GM review
- Statistical analysis
- Designing derived climate profiles

Do not introduce analytics or climate modelling until explicitly
requested.

Future player-facing history, summaries, and statistics must use revealed
weather only. Reporting must not disclose hidden weather or change generation.

---

## Natural Weather Mode

A possible future feature is an optional natural-weather mode.

This may introduce limited continuity between consecutive days so that
weather does not behave as a completely independent series of rolls.

This behaviour is not part of the initial RAW Kingmaker implementation.

Any mode that changes the published weather-generation procedure must be
clearly configurable and distinguishable from the RAW implementation.

Do not implement natural-weather behaviour until explicitly requested.

---

# Predict Weather

The project supports the Pathfinder 2e Predict Weather feat through a
day-level campaign abstraction.

The Discord command is:

    /calendar predict

The command should open an interaction asking the player for their
Survival check total.

The player performs the Survival roll themselves.

The bot uses the supplied result to determine the appropriate forecast.

Prediction rules should be implemented in application/domain services,
not directly inside the Discord command.

---

## Prediction Behaviour

A prediction must be based on the actual weather generated for the
forecast period.

New predictions target the current campaign date, normally near the start of
the campaign day. There is no time-of-day model. Preserve readability of
historical next-day attempts without migrating or rewriting them.

If required weather has not yet been generated:

1. Generate the actual weather.
2. Persist it without revealing it.
3. Generate the player's forecast from that stored weather.

If weather already exists:

1. Retrieve the existing weather.
2. Reject privately if it has already been revealed, creating no attempt.
3. Otherwise use it as the basis of the prediction without revealing it.

Prediction must never cause actual weather to be rerolled.

The player-facing forecast should reveal only the information permitted
by the prediction result.

A failed or misleading prediction must not expose the true weather or
the hidden degree of success.

The Survival-total modal is private. Resolved forecasts are public, including
failure and concealed critical failure. Submitted totals, Predict Weather DCs,
degree labels, and false-forecast markers must remain hidden. Validation,
duplicate-attempt, and revealed-weather errors remain private/ephemeral.
Keep one attempt per Discord user, guild, campaign date, and profile.

---

## Prediction Usage

The system persists one attempt per Discord user, guild, campaign date, and
profile. This approximates the usage restriction by campaign date rather than
elapsed hours; failure and critical failure both consume an attempt.

Stored attempts include:

- Campaign/guild
- Player or Discord user
- Date prediction was made
- Date or period being forecast
- Submitted Survival total
- Conditions, check DC, profile, and forecast
- Degree of success
- Creation timestamp

Do not add a prediction-history interface until explicitly requested.

Do not store character sheets or Survival modifiers merely to support
this feature unless a future requirement explicitly requires them.

---

# Discord Interface

Discord commands are an interface to the application.

Discord handlers should:

1. Validate Discord-specific input.
2. Call application/service functionality.
3. Format the returned result for Discord.

They should not implement core game rules.

Implemented calendar interactions include:

    /calendar date
    /calendar set
    /calendar advance
    /calendar level
    /calendar weather
    /calendar predict

Preserve established command behavior unless the current task requests changes.
Do not implement additional commands merely because they appear on a roadmap.

---

# Future External Integrations

The project may eventually support interfaces other than Discord,
including VTT or d20-related integrations.

Core services must therefore not require Discord objects to function.

The intended dependency direction is:

    Discord --------\
                     \
    Future VTT -------> Application Services
                     /         |
    Future Web -----/          +-- Calendar
                               +-- Campaign State
                               +-- Weather
                               +-- Prediction
                               +-- Persistence

External integrations should adapt their input into application-level
operations.

Do not add VTT, d20, web API, or other external integrations until
explicitly requested.

---

# Future Regional Support

The long-term architecture may support weather configuration by
Golarion region.

Region and climate/weather profile must remain separate.

A region may select a default weather profile, but the underlying
weather engine should not require a hard-coded relationship between the
two.

The current weather profile covers the Stolen Lands for the Kingmaker campaign;
configurable regional support is not implemented.

Future regional or climate profiles may be based on:

- Published Pathfinder rules
- General Pathfinder environmental rules
- Explicit campaign configuration
- Statistically derived models based on generated weather history

Derived or custom models must be clearly labelled as such.

Do not implement a global region database or climate system during the
initial Kingmaker development.

---

# Current Development Strategy

Develop incrementally.

Stages 1–7 below are implemented in the stable v1.0 core. Later stages remain
future work, subject to explicit task scope:

1. Project and Docker foundation
2. Golarion calendar domain
3. Campaign persistence
4. Basic Discord calendar commands
5. Kingmaker/Stolen Lands weather engine
6. Weather persistence
7. Predict Weather support
8. Weather history and GM/admin functionality
9. Optional future regional/climate support
10. Optional future external integrations

Complete and test each stage before expanding into the next.

The presence of a future feature in this document is not permission to
implement it during an earlier stage.

Avoid speculative abstractions that make the current implementation
harder to understand.

At the same time, do not knowingly couple current code to Kingmaker,
Discord, or SQLite where an established project requirement says that
component should remain independent.

---

# Coding Agent Behaviour

Before making changes:

1. Read this file.
2. Inspect the existing repository.
3. Understand the current implementation and tests.
4. Limit work to the requested task.

When implementing:

- Prefer small, understandable changes.
- Preserve existing working behaviour.
- Reuse existing domain models.
- Add tests alongside new behaviour.
- Do not silently change established game rules.
- Do not implement unrelated future features.
- Do not add unnecessary dependencies.
- Do not commit or push unless explicitly instructed.

If requirements conflict or a Pathfinder rule needed for implementation
is unclear, report the ambiguity rather than inventing an answer.

When finished:

1. Run the complete test suite in Docker.
2. Report test results.
3. List files created or modified.
4. Summarise important implementation decisions.
5. Report anything that remains unresolved.

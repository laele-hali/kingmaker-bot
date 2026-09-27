Kingmaker Discord Bot

A Discord bot for managing campaign utilities for a Pathfinder 2e
Kingmaker campaign.

The project is intended to automate some of the repetitive
campaign-management tasks that normally sit behind the GM screen,
beginning with the in-game calendar and the Stolen Lands weather system.

Planned Features

Campaign Calendar

The bot will maintain the current in-game Golarion date for the
campaign.

Planned commands include:

-   /calendar date - Show the current campaign date.
-   /calendar set - Set the current campaign date.
-   /calendar advance - Advance the campaign by a specified number of
    days.
-   /calendar weather - Generate or retrieve weather for the current
    campaign date.

The calendar will track Golarion months, years, and seasons.

Weather Generation

The weather system will implement the Pathfinder 2e Kingmaker Stolen
Lands weather procedure, including:

-   Seasonal precipitation checks.
-   Winter temperature checks.
-   Weather event checks.
-   Weather event selection.
-   Party-level checks for weather hazards.
-   Terrain restrictions where appropriate.
-   Secondary events where required.
-   Persistent weather records by campaign date.

The intention is to support both the rules-as-written weather procedure
and, later, an optional natural-weather mode that can introduce limited
continuity between consecutive days.

Weather History

Generated weather will be stored against the campaign date so that
requesting weather for the same day returns the existing result rather
than silently rerolling it.

This will also allow the campaign to maintain a historical weather log.

Campaign State

Campaign information will eventually include:

-   Current in-game date.
-   Party level.
-   Weather mode.
-   Weather history.
-   Relevant terrain or location information where required.

Project Structure

The project separates Discord-specific code from campaign and game
logic.

Current and planned modules include:

-   application/ - Application-level logic.
-   calendar/ - Golarion calendar and date handling.
-   weather/ - Kingmaker weather generation.
-   database/ - Persistent campaign storage.
-   services/ - Coordination between domain logic and external
    interfaces.
-   Discord client and command modules for interaction with Discord.

This separation is intended to keep the underlying campaign logic
independently testable.

Technology

The project currently uses:

-   Python 3.12
-   discord.py
-   pytest
-   Docker / Docker Compose
-   SQLite for initial persistence

Database access will be kept sufficiently isolated to allow the
persistence layer to be changed later if required.

Development Environment

Development is performed using Docker so that Python and project
dependencies remain isolated from the host system.

Build the development image with:

    docker compose build

Start a development shell with:

    docker compose run --rm dev bash

Run the test suite inside the container with:

    pytest

The repository source is mounted into the development container at
/workspace.

Configuration

Secrets such as the Discord bot token must not be committed to the
repository.

The bot will read its Discord token from an environment variable. Local
configuration files containing credentials should remain excluded from
Git.

Project Status

This project is currently in early development.

The initial Python and Docker development environment is working, along
with the basic Discord bot foundation. Calendar, persistence, and
Kingmaker weather functionality are being implemented incrementally with
automated tests added alongside the game logic.

Rules and Copyright

Pathfinder and Kingmaker are properties of Paizo Inc.

This is an unofficial fan-made campaign utility and is not affiliated
with or endorsed by Paizo.

The project is intended to implement campaign automation without
reproducing substantial copyrighted rules text. Users should refer to
the appropriate Pathfinder and Kingmaker rulebooks for the full game
rules.

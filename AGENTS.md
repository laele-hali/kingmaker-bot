# Kingmaker Bot Development Guidelines

## Environment

This project is developed using Docker.

Project dependencies should be installed inside the Docker development environment rather than directly onto the host.

Use:

    docker compose run --rm dev bash

for development commands.

## Python

Python 3.12 is the project target.

## Testing

Use pytest for automated tests.

Run tests with:

    pytest

Tests should be added alongside new application/game logic.

## Architecture

Keep Discord-specific command handling separate from application and game logic.

Game rules and campaign logic should live in services and data modules rather than directly inside Discord command modules.

Prefer small, testable functions over large command handlers.

## Database

The project currently uses SQLite.

Database access should be kept behind an appropriate abstraction so the storage implementation can be changed later if necessary.

Do not commit database files to Git.

## Pathfinder Rules

The weather and calendar systems implement the Pathfinder 2e Kingmaker rules supplied by the project owner.

Do not invent, silently alter, or simplify game rules.

If optional behaviour differs from the published rules, make it explicitly configurable.

## Git

Do not create commits unless explicitly instructed.

Do not modify Git configuration.

## General

Prefer simple solutions over unnecessary abstractions.

Do not add dependencies unless they are actually required.

Before making substantial changes, inspect the existing code and preserve the established project structure where practical.

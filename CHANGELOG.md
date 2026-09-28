# Changelog

## 1.0.0

Initial stable release of Kingmaker Bot.

### Added

- Persistent Golarion calendar using Absalom Reckoning, an eight-year leap cycle, weekdays, seasons, and date advancement.
- Independent campaign dates and party levels per Discord server.
- `/ping` and `/calendar date`, `set`, `advance`, `level`, `weather`, and `predict` commands.
- Docker Compose self-hosting with external token configuration and a configurable SQLite path.

### Weather and forecasting

- Profile-driven RAW Kingmaker Stolen Lands daily weather generation, including party-level hazard handling and notices for required GM adjudication.
- Canonical generate-once weather, with hidden generation distinct from deliberate public revelation.
- Predict Weather for the current campaign date as the day-level approximation of a 24-hour forecast; no time-of-day tracking.
- Accurate detailed/limited forecasts, no-useful-forecast results, and concealed false forecasts that do not alter actual weather.
- One persisted attempt per Discord user, guild, campaign date, and profile; predictions blocked after weather revelation.

### Persistence

- SQLite storage for campaign state, canonical weather, and prediction attempts.
- Retained generation rolls/DCs and prediction metadata for internal use.
- Stable first-reveal timestamps, repeat retrieval without rerolling, and compatibility with historical next-day prediction rows.

### Discord presentation

- Private, invoking-user-only Reveal Weather/Cancel confirmation before first revelation; cancellation and timeout leave gameplay state unchanged.
- Public actual-weather results and relevant gameplay information, with generation rolls/DCs and selection machinery hidden.
- Private Survival-total entry and public resolved forecasts, concealing submitted totals, check DCs, outcome labels, and false-forecast markers.
- Private validation, duplicate-attempt, and revealed-weather errors.

### Documentation

- [Repository overview](README.md), [self-hosted Discord setup](docs/DISCORD_SETUP_SELF_HOSTED.md), and [player/GM user guide](docs/USER_GUIDE.md).
- Explicitly separated planned v1.5 reporting and potential v2.0 directions.

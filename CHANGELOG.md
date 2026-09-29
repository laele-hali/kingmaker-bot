# Changelog

## 1.0.2

Small workflow release adding private GM inspection of canonical weather.

- `/calendar weather-gm` generates or reuses actual current-day weather and displays it only to the invoking user.
- GM inspection is not revelation: it never changes `revealed_at`, consumes a prediction attempt, or blocks Predict Weather. Later public revelation uses the same canonical weather.
- The existing `/calendar weather` confirmation and public reveal remain unchanged. Discord cannot make `weather` both executable and a group containing `gm`, so inspection is a separate command.
- Intended for GM use; no GM-only permission enforcement. Results hide generation machinery, including in the private view.
- No schema migration or history/reporting functionality.
- Predict Weather prioritizes the revealed-weather rejection even when the user already predicted that day; hidden-weather duplicate attempts retain their usual rejection.

## 1.0.1

Bugfix release for campaign-date rewinds.

- Backwards `/calendar set` now requires a private, invoking-user-only confirmation.
- Confirmed rewinds atomically discard weather and Predict Weather state on and after the target date, making the target day clean. This includes older next-day predictions targeting the abandoned timeline.
- Earlier weather and predictions wholly before the target date are preserved, along with other servers' data and party level.
- Forward and same-date setting remain non-destructive. Opening, cancelling, or timing out a rewind prompt changes nothing.
- Intervening campaign changes invalidate pending rewind confirmations. No schema migration is required.

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

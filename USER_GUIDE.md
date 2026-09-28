# Kingmaker Bot User Guide

Use these commands in your campaign's Discord server. Campaign dates and party level are configured separately for each server.

## PLAYER GUIDE

| Command | What to do |
| --- | --- |
| `/calendar date` | Check the campaign's current date, weekday, and season. |
| `/calendar predict` | Select the observation conditions, then enter your final Survival check total in the modal. The forecast concerns the next campaign day. |

Choose the conditions agreed with your GM:

| Choice | When to select it |
| --- | --- |
| Good visibility / commanding view | The GM confirms you have a suitable view. |
| Normal conditions | Ordinary observation conditions. |
| Poor visibility | Visibility is poor. |

Enter the **final Survival check total**, including your modifiers, as a whole number. Do not enter just the raw d20 roll. The bot does not roll Survival for you.

Your modal submission is private. The resolved forecast is posted publicly in the channel, including a result saying you cannot obtain a useful forecast. Your submitted total is not published. Predict Weather follows Secret-check behavior: its check mechanics, DC, and degree-of-success result are intentionally hidden. Treat the returned forecast as **what your character believes**.

Only one Predict Weather attempt is allowed per user per campaign date. For your character, this means using your Discord account's daily attempt: the bot tracks users, not separate characters. This approximates the 24-hour restriction using campaign dates. Failed attempts also count; changing conditions does not allow another attempt. Missing configuration, invalid input, and duplicate-attempt errors are private. Ask the GM to configure the calendar and party level if needed.

## GM GUIDE

### Command reference

| Command | Use at the table |
| --- | --- |
| `/calendar date` | Check the current campaign date. |
| `/calendar set day:19 month:3 year:4710` | Initialize or update the date, here to 19 Pharast 4710 AR. Use a numeric month from 1 to 12. |
| `/calendar advance days:1` | Move forward one campaign day. Any positive whole number of days is accepted. |
| `/calendar level` | View the configured party level. |
| `/calendar level level:4` | Set party level to 4; allowed levels are 1–20. Configure the calendar first. |
| `/calendar weather` | Reveal the current day's actual world weather and any GM-resolution notes. Requires party level. |
| `/calendar predict` | A player selects conditions and submits their final Survival total for a next-day forecast. Requires calendar and party-level configuration. |

Months 1–12 are Abadius, Calistril, Pharast, Gozran, Desnus, Sarenith, Erastus, Arodus, Rova, Lamashan, Neth, and Kuthona. Dates use Absalom Reckoning, with leap years every eight years. Party level is used for weather hazard handling; updating it does not reroll existing weather.

**Command access:** The bot does not enforce GM-only permissions. Agree who uses date, level, and weather commands. `/calendar weather` posts to the invoking channel; use a restricted GM channel if its contents should remain private.

### World weather versus character forecasts

| | `/calendar weather` | `/calendar predict` |
| --- | --- | --- |
| Information | GM/world information for the current day | Character-facing forecast for the next day |
| Mechanics shown | Weather-generation rolls and DCs, hazard information, GM decisions | No Predict Weather DC, submitted total, or degree labels |
| Visibility | Public within the invoking channel | Resolved forecasts public; validation and duplicate errors private |
| Effect on actual weather | Retrieves/generates and marks it revealed | Retrieves/generates without marking it revealed |

The bot treats generated weather as **canonical**. Once weather has been generated for a date, that result becomes the actual weather for that day and is not rerolled. A prediction may already have generated tomorrow's weather invisibly. When tomorrow arrives, `/calendar weather` reveals that same result rather than rerolling it. Advancing the date does not itself reveal or generate weather.

### Secret-check behavior

The player supplies a final total; the bot keeps the outcome classification hidden. It does not collect a raw die result, so natural-die degree adjustments are not applied.

| Internal outcome | Public response |
| --- | --- |
| Critical success | Accurate detailed forecast based on canonical weather. |
| Success | Accurate limited forecast based on canonical weather. |
| Failure | No useful forecast. |
| Critical failure | A plausible, confident false forecast, deliberately not identified as false. |

A false forecast never changes canonical weather. The current model deliberately includes a +2 preparation bonus in its confident false forecast, so that bonus alone does not indicate critical success. Do not disclose the hidden outcome to players.

Attempts are stored once per Discord user per campaign date. This is a campaign-date approximation of the 24-hour restriction, not a real-time cooldown. The bot does not track separate characters or verify feat eligibility. Ordinary wind and exact event timing are not modelled; resolve flagged hazards, secondary events, terrain applicability, and full hazard effects using the published rules.

### Example session

| Step | Action | Result |
| --- | --- | --- |
| 1 | GM runs `/calendar date`, or uses `/calendar advance days:1` when the session moves forward. | The table confirms it is 19 Pharast 4710 AR. Calendar and party level are already configured. |
| 2 | A player runs `/calendar predict`, selects Normal conditions, and submits their final Survival total. | The bot retrieves or generates hidden canonical weather for 20 Pharast. |
| 3 | The bot resolves the attempt. | Its character-facing forecast is posted in the channel; the total and outcome label remain hidden. |
| 4 | The next campaign day arrives; GM runs `/calendar advance days:1`. | The date becomes 20 Pharast. |
| 5 | GM runs `/calendar weather` in the appropriate channel. | The bot retrieves the previously generated weather. |
| 6 | The weather response appears. | The stored canonical weather is revealed without being rerolled. |

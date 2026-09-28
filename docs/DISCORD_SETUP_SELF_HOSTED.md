# Discord Setup: Self-Hosted

[Project overview](../README.md) · [User Guide](USER_GUIDE.md)

This guide is for running **your own Kingmaker Bot instance**. You create and configure your own Discord application and bot, supply your own token, and run the software on your own infrastructure. Its persistent campaign data belongs to that instance and stays in your configured database. There is currently no official/publicly hosted Kingmaker Bot service.

## 1. Prerequisites

- Git, Docker, and Docker Compose (`docker compose`), with Docker running and accessible to your user.
- A computer or server that can remain running while the bot is needed, with internet access to download dependencies and connect to Discord.
- A Discord account and a server where you own the server or have **Manage Server** (`MANAGE_GUILD`) permission to install an app. See Discord's [installation overview](https://docs.discord.com/developers/quick-start/getting-started).
- A writable local directory for the repository and database.

Python 3.12 and project dependencies are installed inside the Docker image; you do not need a host Python installation. This bot connects through Discord's Gateway, so this setup needs no public web server, inbound port, or Interactions Endpoint URL.

## 2. Clone the repository

```sh
git clone https://github.com/laele-hali/kingmaker-bot.git
cd kingmaker-bot
```

Run the following shell commands from this directory.

## 3. Create your Discord application and bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application. Choose a name you will recognize in your server.
2. In the application's **Bot** section, configure its bot user; create one if the portal prompts you to do so.
3. Use the Bot section's token controls to obtain or reset the **bot token**. Save it privately for the configuration step below. Use the bot token, not the application ID, public key, or OAuth client secret.
4. Find the **Application ID** in General Information. You can use it to identify the application when generating an installation link. Kingmaker Bot does not require this ID in its environment.

Portal wording and layout may change; Discord's [application setup guide](https://docs.discord.com/developers/quick-start/getting-started) describes the relevant sections. Leave privileged Gateway intents disabled: the current client uses default intents and does not need Message Content, Server Members, or Presence intents. Leave the OAuth2 code-grant requirement disabled for this direct bot installation.

## 4. Install the bot with the required scopes

In the application's Installation settings, enable **Guild Install** (server installation). Use its installation link settings or the OAuth2 URL Generator to select:

| Setting | Value for this implementation |
| --- | --- |
| OAuth scopes | `bot` and `applications.commands` |
| Additional bot permissions | None required by the current command handlers; leave the permission checklist empty (`permissions=0` if generating a URL). |
| Privileged intents | None |

All current messages are slash-command or modal interaction responses, not ordinary channel-send operations. Do not request Administrator, Manage Server, Manage Messages, Read Message History, or other extra bot privileges. Interaction responses do not use ordinary message permission checks; see Discord's [interaction-response permission explanation](https://github.com/discord/discord-api-docs/discussions/5097). The [application-command documentation](https://docs.discord.com/developers/interactions/application-commands) explains command authorization; `applications.commands` is also included with the `bot` scope.

Open the generated install URL while signed into Discord, select the intended server, and authorize the installation. Choose **Add to Server** if Discord offers multiple installation contexts. The bot should appear in the server's member list; it will remain offline until you start it.

Players need access to the intended channel and permission to **Use Application Commands**, and server integration settings must allow these commands. Those member/command permissions are separate from the bot's invite permissions. The code does not enforce GM-only roles: configure command access through Discord's server integration settings if needed. Weather results and resolved forecasts are visible in the channel where they are invoked.

## 5. Configure the local environment

Create a file named `.env` beside `compose.yaml` using a text editor. Enter your token locally in place of this placeholder:

```dotenv
DISCORD_BOT_TOKEN=your_bot_token_here
KINGMAKER_DATABASE_PATH=data/kingmaker.db
```

| Variable | Meaning |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Required to start the bot. Paste only the token value, without a `Bot ` prefix. |
| `KINGMAKER_DATABASE_PATH` | Optional; defaults to `data/kingmaker.db`. Relative paths resolve from `/workspace` in this Compose setup. |

There is **no `DISCORD_APPLICATION_ID` setting in the current code**. The client obtains the application identity through Discord authentication. Compose sets `PYTHONPATH=/workspace/src` itself; do not add it to `.env` for this setup.

Compose supplies `.env` values to the container; the application does not load an `.env` file itself. The file must exist for the current Compose service, even when running tests without a token.

**Never commit `.env`. Never commit or share the bot token. If a token is exposed, regenerate it through Discord's Bot settings, update your local `.env`, and restart the bot.** Both `.gitignore` and `.dockerignore` exclude `.env` and `*.db`; these exclusions are not a substitute for keeping credentials private.

## 6. Build and start

Create the database's parent directory, which the application does not create automatically, then build:

```sh
mkdir -p data
docker compose build
```

Start the bot in the foreground:

```sh
docker compose run --rm dev kingmaker-bot
```

Keep that terminal and host running during use. The `dev` service mounts this checkout at `/workspace`; the explicit `kingmaker-bot` command invokes the project's entry point. The image's default command is `bash`, so merely starting the default service does not start the bot. This repository currently supplies a development Compose workflow, not a production deployment or automatic restart service.

A successful connection normally produces discord.py login/Gateway logs. There is no project-specific “ready” banner. Confirm success by checking that the bot is online in Discord and that `/ping` responds.

To stop, press **Ctrl+C** in the foreground terminal. To restart, run the same `docker compose run --rm dev kingmaker-bot` command again. Restart after editing `.env`; existing processes do not reload it. Run one bot process for this instance.

## 7. Verify Discord commands

Confirm that the bot appears in the intended server and is online. In a server channel where your account can use application commands, type `/ping` or `/calendar date` and select your application's command.

The client calls `CommandTree.sync()` without a guild argument at startup, so registration is **global**. New or changed global commands may take some time to propagate to Discord clients; there is no guild-specific development synchronization setting. Allow time, reopen the command picker, and check the running terminal for synchronization errors. Discord describes global command updates in its [application-command documentation](https://docs.discord.com/developers/interactions/application-commands).

## 8. Configure the first campaign

Use the slash-command option fields shown below in your server:

| Step | Command | Expected result |
| --- | --- | --- |
| 1 | `/calendar date` | A new server reports that no campaign calendar is configured. |
| 2 | `/calendar set day:19 month:3 year:4710` | Sets 19 Pharast 4710 AR. Replace these values with your campaign date. |
| 3 | `/calendar level level:4` | Sets party level to 4; use your party's level from 1–20. |
| 4 | `/calendar weather` | Shows a private first-reveal confirmation. Select **Reveal Weather** to publicly display actual weather; **Cancel** changes nothing. Already-revealed weather displays directly. |

Calendar state is independent for each Discord server. Party level is required for weather hazard handling. Confirmed `/calendar weather` output includes world-weather rolls and DCs and is public within its channel. Choose the channel deliberately: any confirmed reveal prevents further predictions for that campaign date. For play, forecasting, and advancing the date, continue to the [User Guide](USER_GUIDE.md).

## 9. Persistence and backups

The default SQLite file is:

| Location | Path |
| --- | --- |
| Inside the container | `/workspace/data/kingmaker.db` |
| On your host | `data/kingmaker.db` inside this checkout |

The repository bind mount retains the file when the `--rm` container is removed. Campaign state, generated weather, reveal status, and prediction attempts survive bot restarts when the same database is reused. Restarting does not reroll canonical weather. Predict Weather generates or reuses hidden weather for the current campaign date. Confirming `/calendar weather` reveals that same record and blocks further predictions for that date; merely opening or cancelling the prompt does neither. Use Predict Weather before revealing weather when following the session workflow.

If you change `KINGMAKER_DATABASE_PATH`, create its parent directory and ensure it is writable. Keep it inside the mounted checkout for this unchanged Compose setup; a path elsewhere in a temporary container may be lost when that container is removed. A different checkout or database path refers to different data.

Stop the bot before copying the database for a backup. Store backups privately outside Git; the database contains internal prediction information and hidden weather. Custom filenames not matching `*.db` also need appropriate Git/build-context exclusions before use. Startup initializes supported schema structures, but there is no separate migration or backup command.

## 10. Update a self-hosted instance

1. Read the repository's change notes or relevant commits. Stop the running bot and make a private database backup.
2. Check your working tree. Preserve any intentional local changes before updating; do not discard them blindly.
3. From the checkout, update and rebuild:

   ```sh
   git status --short
   git pull --ff-only
   docker compose build
   docker compose run --rm dev kingmaker-bot
   ```

4. Check `/ping` and `/calendar date`. Keep the same database path and bind-mounted checkout to retain campaign data.

If the pull cannot fast-forward, resolve your local branch situation before proceeding. This is a manual update workflow, with no automatic deployment or general migration framework.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Invalid token / HTTP 401 | Use the bot token from the correct application's Bot section, not its ID or client secret. Replace an invalid/reset token locally and restart. Never paste it into a support request. |
| Missing environment variable | `DISCORD_BOT_TOKEN` must be nonempty. Ensure `.env` exists beside `compose.yaml` and uses the exact name. The application ID is not a replacement. |
| Bot not online | Installation alone does not run it. Keep the explicit foreground bot command running, check its terminal for startup errors, and verify Docker and outbound Discord connectivity. |
| Slash commands missing | Verify the correct app is installed with command authorization, startup sync completed, and your channel/member/integration permissions allow commands. Allow global updates time to appear. |
| Docker build/start fails | Check `docker --version`, `docker compose version`, Docker daemon access, the repository working directory, and build output. Dependency downloads need network access. A missing `.env` can prevent Compose from starting. |
| SQLite cannot open the database | Create the configured parent directory and check write access. Container-relative paths start at `/workspace`. |
| Data seems missing after restart | Verify you restarted from the same checkout with the same configured database path. The default data is a host bind-mounted file, not data stored in the image. Do not delete or replace it to troubleshoot. |

When seeking help, share only redacted errors. Do not post `.env`, bot tokens, or database files; avoid sharing expanded Compose configuration because it can contain credentials.

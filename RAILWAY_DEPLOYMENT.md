# JARVIS Ultimate — Railway Deployment

## 1. Upload the project

Upload the **contents of the `jarvis_ultimate` folder** to the root of your GitHub repository. The repository root should contain `main.py`, `config.py`, `database.py`, `requirements.txt`, and `Procfile`.

## 2. Required Railway variables

In Railway → your service → Variables, set:

- `DISCORD_TOKEN` — your bot token from the Discord Developer Portal. Keep it secret.
- `SYNC_COMMANDS_ON_START=true` — use this for the first deploy and whenever slash commands change.
- `DATABASE_PATH=/data/jarvis.sqlite3` — use this only after adding/mounting a Railway Volume at `/data`.
- `JARVIS_CREATOR=JARVIS Development Team` — optional help-panel creator text.
- `MESSAGE_CONTENT_INTENT=false` — set to `true` only if you enable Message Content Intent in the Developer Portal and require message content in logs.

`SECURITY_THRESHOLD` and `SECURITY_WINDOW_SECONDS` are optional; defaults are `5` and `12`.

## 3. Discord Developer Portal

Open your application → Bot and enable **Server Members Intent**. Enable **Message Content Intent** only if you set `MESSAGE_CONTENT_INTENT=true`. Reinvite the bot with the least permissions needed by your enabled features. Useful permissions include View Channels, Send Messages, Embed Links, View Audit Log, Manage Channels, Move Members, Ban Members, Kick Members, and Moderate Members. Do not grant Administrator unless you knowingly accept the elevated risk.

## 4. Deploy and verify

Railway installs dependencies from `requirements.txt` and starts the worker using `Procfile`. Check the deployment logs for a successful login, all cog extensions loading, and the slash-command sync count. In Discord, run `/help`, `/jarvis`, `/security health`, `/anti-nuke status`, `/bot-guard status`, `/welcome status`, and `/goodbye status`.

Global application-command changes can take time to appear in Discord. Leave `SYNC_COMMANDS_ON_START=true` during initial setup. After command sync has succeeded, you can disable startup sync and turn it back on when you update commands.

## 5. Persistent database

Attach one Railway Volume mounted at `/data` and set `DATABASE_PATH=/data/jarvis.sqlite3`. Without a persistent volume, SQLite data may be lost during redeploys/restarts. Run one service replica for this SQLite-based project; multiple replicas writing to one SQLite database are not a safe default.

## 6. Safety and validation

Keep anti-nuke and Bot Guard in `alert` mode during testing. Kick mode depends on Discord API availability, bot permissions, role hierarchy, and correct actor/event attribution. This project cannot guarantee that every destructive action is stopped before Discord processes it. Test in a private server before enabling automatic actions in your main server.

Local Python syntax compilation passed. This build environment could not install `discord.py` and `aiosqlite` due unavailable package-index connectivity, so database tests and live Discord/Railway integration were not run here. After dependencies are installed, run:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

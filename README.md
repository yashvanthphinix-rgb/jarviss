# JARVIS Ultimate

A modular Discord security and moderation bot starter using Python 3.11+, `discord.py` 2.x, and SQLite via `aiosqlite`.

## Implemented in this build

For exact security command names, options, permissions, and limitations, see [SECURITY_COMMANDS.md](SECURITY_COMMANDS.md).

- Modular startup and extension loading.
- SQLite persistence for settings, moderation cases, security events, Join-to-Create records, XP/invite tables, and structural backup snapshots.
- `/help` with a private interactive panel.
- The `/help` panel maps implemented slash commands to their exact categories; planned modules are labeled as not implemented and do not display unrelated active commands.
- `/jarvis` operational dashboard with live process metrics.
- `/ping` latency diagnostics for Discord gateway heartbeat, initial interaction acknowledgement, and follow-up HTTP timing in logs.
- Performance tuning: cached hot-path guild settings, SQLite WAL with NORMAL synchronous mode, in-memory temp storage, and a short busy timeout.
- `/help_config_creator`, `/help_config_introduction`, `/help_config_show` configuration commands.
- `/ban`, `/kick`, `/timeout`, `/untimeout`, `/warn`, and `/warnings`. `/timeout` duration is configured in seconds (1–50,000).
- `/security threshold` accepts a monitoring window of 1–50,000 seconds.
- Central moderation hierarchy checks, best-effort owner/member DMs, and stored moderation history.
- `/security status`, `/security threshold`, `/security lockdown`, `/security unlock`, `/security health`, `/security permission-audit`, and `/security events`.
- Owner-only `/security panic-lockdown` and `/security panic-unlock`, which save and restore the prior `@everyone` Send Messages overwrite for each text channel.
- `/bot-guard status`, `/bot-guard enable`, `/bot-guard mode`, `/bot-guard allow`, `/bot-guard remove`, `/bot-guard list`, and read-only `/bot-guard scan`. Bot Guard reports unapproved bot joins; optional kick mode is explicitly enabled by the server owner.
- `/anti-nuke enable`, `/anti-nuke status`, `/anti-nuke threshold`, `/anti-nuke response-mode`, `/anti-nuke incidents`, `/anti-nuke events`, and `/anti-nuke resolve`. Detection covers channel/role creation and deletion, selected channel/role changes, member bans, and webhook-change notifications where audit data is available.
- `/setup-logs` creates seven private log channels: `moderation-logs`, `message-logs`, `member-logs`, `channel-logs`, `voice-logs`, `security-logs`, and `bot-logs`.
- `/set-log-channel` changes the destination for any logging category.
- Event logging covers message edits/deletions/bulk deletions, member joins/leaves/nickname and role changes, channel and role changes, voice state changes, bans/unbans, webhook configuration updates, moderation commands, command errors, and channel/role deletion security alerts.
- Logging is best-effort; deleted content is only available if Discord supplies it in the cached event, and actor attribution may require audit-log access and can be delayed.
- `/welcome set-message`, `/welcome set-channel`, `/welcome clear-channel`, `/welcome reset-message`, and `/welcome status` for custom in-server welcome messages. When no channel is configured, the existing welcome DM remains the fallback.
- `/goodbye set-message`, `/goodbye set-channel`, `/goodbye clear-channel`, `/goodbye reset-message`, and `/goodbye status` for custom in-server departure messages.
- Welcome/goodbye templates support `{user}`, `{display_name}`, `{mention}`, `{server}`, `{member_count}`, `{user_id}`, and `{created_date}`. `{mention}` pings only the joining/leaving member if used; mass mentions remain disabled.
- Join-to-Create setup and status commands plus basic temporary voice channel creation.
- `/backup create`, `/backup list`, and `/backup inspect` for supported structural snapshots.
- Basic database tests.

## Not yet implemented (do not assume otherwise)

The project is a functional defensive baseline, not a complete production anti-nuke suite. Destructive backup restore, complete anti-nuke/anti-raid decision engine, full anti-nuke actor attribution and raid decision engine, timeout-expiration notification worker, farewell DMs, autoroles/reaction roles, leveling, invite attribution, `/fly`, and full JTC owner controls/empty-channel cleanup are not implemented. `/build`, `/setup-logs verify/repair`, invite attribution, and complete moderation command coverage are also not implemented. The help text only lists commands present in this build.

A channel-deletion listener detects the event after it occurs. It does not guarantee pre-emptive prevention, and it does not infer the actor without additional evidence.

## Setup

1. Install Python 3.11.
2. Create a Discord application and bot in the [Discord Developer Portal](https://discord.com/developers/applications).
3. Enable the **Server Members Intent** under Bot settings. Enable Message Content Intent in the Developer Portal and set `MESSAGE_CONTENT_INTENT=true` if you want message log entries to include content. With it disabled, content may be unavailable; message event logging still has limitations.
4. Invite the bot with only the permissions needed for the features you use. Moderation requires Ban Members, Kick Members, Moderate Members; JTC requires Manage Channels and Move Members; log setup requires Manage Channels; lockdown requires Manage Channels; backup snapshot commands need access to guild structure. Avoid Administrator unless you consciously accept the larger blast radius.
5. Copy `.env.example` to `.env` and set `DISCORD_TOKEN`.
6. Install dependencies: `python -m pip install -r requirements.txt`
7. Run: `python main.py`
8. Invite the bot to a test server first. Slash-command global synchronization may take time to propagate.

## Local tests

```bash
python -m unittest discover -s tests -v
```

Tests exercise database persistence only; they do not prove live Discord API behavior.

## Railway

- Deploy this repository as a worker/service.
- Set `DISCORD_TOKEN` and other environment variables in Railway Variables.
- Attach a persistent volume and set `DATABASE_PATH` to a path on that volume, for example `/data/jarvis.sqlite3`.
- Without persistent storage, SQLite data may be lost on redeploy/restart.
- Use one running replica for this SQLite-based build. Multiple replicas sharing a SQLite database are not a safe default.
- Test the Southeast Asia (Singapore) region first from India, then compare alternatives only if needed. A region change with a mounted volume can require migration and downtime.
- Keep `SYNC_COMMANDS_ON_START=true` for the first deployment so slash commands register; after successful sync, you can set it to `false` to avoid doing a global sync at every restart. Set it back to `true` when you change commands.
- `/ping` is a diagnostic, not a promise of 80 ms. Discord gateway latency and REST/action latency are different; the actual result depends on Discord and network routing.

## Replit

- Store `DISCORD_TOKEN` in Replit Secrets, not in source code.
- Confirm the workspace/runtime provides persistent storage for the chosen database path. Ephemeral storage can lose SQLite data.
- Run `python main.py` as a long-running process if your plan supports it.

## Time-based command ranges

- `/timeout`: `duration_seconds` accepts **1–50,000 seconds** (maximum 13 hours, 53 minutes, 20 seconds). Discord may enforce its own validation and API behaviour.
- `/security threshold`: `window_seconds` accepts **1–50,000 seconds**.
- Internal UI view timeouts are implementation details, not user-configurable command durations.

## Important Discord API limits

- The bot cannot intercept every action before Discord processes it.
- Audit-log attribution may be delayed or unavailable.
- Deleted message content cannot generally be fetched after deletion unless previously stored in a compliant archive.
- DMs can fail due to recipient privacy settings or API restrictions.
- Rate limits and network delays mean no guaranteed sub-20 ms end-to-end response.
- Restore operations can only reproduce supported data that was saved and that the API permits the bot to recreate.

## Anti-nuke detector update

This build includes `cogs/anti_nuke.py` with best-effort audit-log correlation for channel/role creation and deletion, member bans, webhook-change notifications, and selected role/channel permission/name changes. It counts attributed high-risk events from the persistent SQLite event log and writes security events/incidents to SQLite. Unknown or ambiguous actors are logged but never automatically punished. The default response is `alert`.

New commands:
- `/anti-nuke enable`, `/anti-nuke status`, and `/anti-nuke threshold` — configure detection, threshold, and rolling window. Configuration changes are server-owner-only.
- `/anti-nuke response-mode` — server-owner-only setting for `alert` (recommended) or `kick` after a configured threshold.
- `/anti-nuke events`, `/anti-nuke incidents`, and `/anti-nuke resolve` — review event evidence and mark incidents as reviewed.
- `/bot-guard status`, `/bot-guard enable`, `/bot-guard mode`, `/bot-guard allow`, `/bot-guard remove`, `/bot-guard list`, and `/bot-guard scan` — approve bots, review the allowlist, and detect unapproved bot joins.
- `/security health`, `/security permission-audit`, `/security events`, `/security panic-lockdown`, and `/security panic-unlock` — inspect prerequisites and privileged roles, review event records, and run/restore the owner-only server-wide lockdown.

Required bot permissions include View Audit Log, View Channels, Send Messages, Embed Links, and (only if choosing kick response) Kick Members. Keep the bot role above the roles it may need to act on. Enable Server Members Intent in the Developer Portal for member events.

Limitations: audit log delivery/correlation can be delayed or ambiguous; webhook update events do not identify whether a webhook was created, updated, or deleted; the event-count window is queried from SQLite, while short incident-notification cooldowns reset on restart; automatic kicking can have false positives and is disabled by default. This is a defensive baseline, not a guarantee against all attacks. 
# JARVIS Ultimate — Production Security Command Reference

All commands below are slash commands. The bot must have the required Discord permissions, and its highest role must be above users/bots it may need to moderate. Security actions can be rate-limited or rejected by Discord.

## `/help` category directory

The private interactive help panel assigns every currently implemented slash command to a single category. Select a category in `/help`; use **Refresh** after deployment or a command sync.

| Help category | Commands shown |
|---|---|
| Home Overview | `/help`, `/jarvis` |
| Help Configuration | `/help_config_creator`, `/help_config_introduction`, `/help_config_show` |
| Anti-Nuke & Incident Response | `/anti-nuke enable`, `/anti-nuke status`, `/anti-nuke threshold`, `/anti-nuke response-mode`, `/anti-nuke incidents`, `/anti-nuke events`, `/anti-nuke resolve` |
| Bot Guard & Approved Bots | `/bot-guard status`, `/bot-guard enable`, `/bot-guard mode`, `/bot-guard allow`, `/bot-guard remove`, `/bot-guard list`, `/bot-guard scan` |
| Admin Delegation & Access | `/security whitelist-add`, `/security whitelist-remove`, `/security whitelist-list`, `/security delegate-add`, `/security delegate-remove`, `/security delegate-list`, `/security health`, `/security permission-audit` |
| Server Security & Lockdown | `/security status`, `/security threshold`, `/security protection`, `/security events`, `/security lockdown`, `/security unlock`, `/security panic-lockdown`, `/security panic-unlock` |
| Moderation & Sanctions | `/ban`, `/kick`, `/timeout`, `/untimeout`, `/warn`, `/warnings` |
| Automated Logging | `/setup-logs`, `/set-log-channel` |
| Welcome & Goodbye Messages | `/welcome set-message`, `/welcome set-channel`, `/welcome clear-channel`, `/welcome reset-message`, `/welcome status`; `/goodbye set-message`, `/goodbye set-channel`, `/goodbye clear-channel`, `/goodbye reset-message`, `/goodbye status` |
| Voice & Join-to-Create | `/jtc-setup`, `/jtc-status` |
| Backups & Recovery | `/backup create`, `/backup list`, `/backup inspect` |
| Performance & Diagnostics | `/ping` |

The remaining legacy feature categories are kept visible in the help selector as **Not implemented yet** (or **Partially available** where a non-command feature exists). They intentionally do not list commands from unrelated categories. All displayed command entries are derived from the commands registered in the application's command tree, then matched to the category map.

## Anti-nuke detection

| Command | Purpose |
|---|---|
| `/anti-nuke status` | Show monitoring state, threshold, rolling window, response mode and coverage. |
| `/anti-nuke enable enabled:true/false` | Enable or disable high-risk event processing. Server owner only. |
| `/anti-nuke threshold count:<2-25> window_seconds:<1-50000>` | Set the number of attributed risky events and the rolling window. Server owner only. |
| `/anti-nuke response-mode mode:alert/kick` | Choose alert-only or optional kick response. Server owner only; alert is the default. |
| `/anti-nuke events limit:<1-15>` | Review recent high-risk event records. |
| `/anti-nuke incidents limit:<1-15>` | Review recent incident records. |
| `/anti-nuke resolve incident_id:<id>` | Mark an incident reviewed/resolved; it does not reverse a destructive action. |

Detection covers channel and role creation/deletion, selected channel and role changes, member bans, and webhook-change notifications where audit-log data is available. Actor attribution can be delayed or ambiguous. Unknown actors are recorded but never auto-punished. The detector is not a guarantee that Discord actions will be blocked before they happen.

## Bot Guard

| Command | Purpose |
|---|---|
| `/bot-guard status` | Show monitoring, response mode and approved bot count. |
| `/bot-guard enable enabled:true/false` | Enable or disable bot-join checks. Server owner only. |
| `/bot-guard mode mode:alert/kick` | Alert on unapproved bots, or opt in to trying to kick them. Server owner only. |
| `/bot-guard allow bot_member:<bot>` | Add a bot account to the approved list. Server owner only. |
| `/bot-guard remove bot_id:<id>` | Remove an approved bot ID. Server owner only. |
| `/bot-guard list` | List approved IDs and currently cached bot members. |
| `/bot-guard scan` | Read-only scan of current cached bot members; does not kick anyone. |

Bot Guard detects bot accounts when they join after the feature is loaded. It does not remove old bots automatically; use `/bot-guard scan` to review current members. Audit-log attribution for the inviter may not be available. Automatic kick mode is opt-in, can fail due to hierarchy/permissions, and should be tested on a private server.

## Server security and auditing

| Command | Purpose |
|---|---|
| `/security health` | Check relevant bot permissions and security-log destination. |
| `/security permission-audit` | List roles with high-impact server permissions. |
| `/security events limit:<1-15>` | Review recent recorded security events. |
| `/security status` | View the threshold, rolling window, log destination and recent events. |
| `/security threshold count:<2-25> window_seconds:<1-50000>` | Set detector threshold values. |
| `/security protection enabled:true/false` | Toggle anti-nuke event processing. |
| `/security whitelist-add member:<member>` | Add a trusted actor ID consulted by anti-nuke responses. |
| `/security whitelist-remove member:<member>` | Remove a trusted actor ID. |
| `/security whitelist-list` | Show trusted IDs. |
| `/security lockdown channel:<channel>` | Deny `@everyone` Send Messages in one text channel. |
| `/security unlock channel:<channel>` | Remove the explicit Send Messages denial from one text channel. |
| `/security panic-lockdown` | Owner-only; deny `@everyone` Send Messages in all server text channels and save their prior values. |
| `/security panic-unlock` | Owner-only; restore the saved prior `@everyone` Send Messages values from an active panic lockdown. |
| `/setup-logs` | Create the configured private logging channels. |
| `/set-log-channel category:<category> channel:<channel>` | Select the destination for a log category. |

The panic-lockdown pair changes only the `@everyone` Send Messages overwrite on standard text channels and saves/restores that one permission value. It does not lock every permission on every Discord channel type. Review the summary after each operation and verify the server manually.

## Welcome and goodbye messages

| Command | Purpose |
|---|---|
| `/welcome set-message message:<text>` | Set the custom welcome message posted in the configured server text channel. Message length: 1–1500 characters. Manage Server required. |
| `/welcome set-channel channel:<text-channel>` | Choose the in-server text channel for welcome messages. JARVIS checks View Channel and Send Messages permissions. |
| `/welcome clear-channel` | Disable in-server welcome posts; the existing welcome-DM fallback becomes active again. |
| `/welcome reset-message` | Restore the default server welcome template. |
| `/welcome status` | Show the configured destination and saved template. |
| `/goodbye set-message message:<text>` | Set the custom departure message posted when a member leaves. Message length: 1–1500 characters. Manage Server required. |
| `/goodbye set-channel channel:<text-channel>` | Choose the in-server text channel for departure messages. |
| `/goodbye clear-channel` | Disable departure messages in the server. |
| `/goodbye reset-message` | Restore the default server departure template. |
| `/goodbye status` | Show the configured destination and saved template. |

Both templates support `{user}`, `{display_name}`, `{mention}`, `{server}`, `{member_count}`, `{user_id}`, and `{created_date}`. Use `{mention}` when you want to mention the member being welcomed or departing; the bot suppresses role and everyone mentions. Messages are regular text/Markdown posts, not generated image cards. The welcome DM fallback is used only when no welcome channel is configured; goodbye messages need a configured channel. Enable Server Members Intent in the Discord Developer Portal for member join/leave events.

## Recommended initial setup

1. Run `/setup-logs` and `/security health`.
2. Keep `/anti-nuke response-mode mode:alert` and `/bot-guard mode mode:alert` while observing logs.
3. Add trusted bots with `/bot-guard allow` and trusted security actors with `/security whitelist-add`.
4. Use `/bot-guard scan`, `/security permission-audit`, `/anti-nuke events`, and `/anti-nuke incidents` for review.
5. Only enable automatic kick after testing, verifying the bot role hierarchy, and confirming the threshold matches the server's normal administration workflow.

## Operational limits

- The bot uses SQLite. On Railway, configure a persistent volume and set `DATABASE_PATH` to a path on that volume. Run a single replica for this SQLite-based build.
- Keep `VIEW_AUDIT_LOG` enabled for the bot if you expect actor attribution; even then Discord may deliver audit entries late.
- These controls are a defensive baseline, not an unbypassable shield. Discord permissions, API availability, gateway delivery, rate limits, role hierarchy, and network delays remain relevant.

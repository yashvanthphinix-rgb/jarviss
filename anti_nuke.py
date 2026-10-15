from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import panel, success, warning, error

log = logging.getLogger("jarvis.anti_nuke")

# Event types intentionally limited to destructive/high-risk operations.
AUDIT_ACTIONS = {
    "channel_create": discord.AuditLogAction.channel_create,
    "channel_delete": discord.AuditLogAction.channel_delete,
    "role_create": discord.AuditLogAction.role_create,
    "role_delete": discord.AuditLogAction.role_delete,
    "member_ban": discord.AuditLogAction.ban,
    "webhook_create": discord.AuditLogAction.webhook_create,
    "role_update": discord.AuditLogAction.role_update,
    "channel_update": discord.AuditLogAction.channel_update,
}

class AntiNuke(commands.Cog):
    """Best-effort anti-nuke detector. Safe default is alert-only; auto-kick is opt-in."""
    anti_nuke = app_commands.Group(name="anti-nuke", description="Configure anti-nuke detection and response.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.windows: dict[tuple[int, int], deque] = defaultdict(deque)
        self.incident_cooldown: dict[tuple[int, int], discord.utils.utcnow] = {}

    async def _require_manage_guild(self, interaction: discord.Interaction) -> bool:
        guild = interaction.guild
        perms = getattr(interaction.user, "guild_permissions", None)
        if guild and (guild.owner_id == interaction.user.id or (perms and (perms.administrator or perms.manage_guild))):
            return True
        await interaction.response.send_message(embed=error("Permission denied", "You need Manage Server permissions to review anti-nuke events and incidents."), ephemeral=True)
        return False

    async def _send_security_log(self, guild: discord.Guild, title: str, description: str, color: int = 0xED4245):
        channel_id = await self.bot.db.get_setting(guild.id, "log_channel_security", None)
        if not channel_id:
            channel_id = await self.bot.db.get_setting(guild.id, "security_log_channel", None)
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            try:
                await channel.send(embed=panel(title, description[:4000], color=color), allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                log.exception("Failed to send security log for guild %s", guild.id)

    async def _audit_actor(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int | None):
        """Correlate a gateway event with a recent audit entry; uncertain attribution returns None."""
        me = guild.me
        if me is None or not me.guild_permissions.view_audit_log:
            return None
        try:
            now = discord.utils.utcnow()
            async for entry in guild.audit_logs(limit=8, action=action):
                if entry.created_at and abs((now - entry.created_at).total_seconds()) > 12:
                    continue
                entry_target = getattr(entry.target, "id", None)
                if target_id is not None and (entry_target is None or int(entry_target) != int(target_id)):
                    continue
                if entry.user is None or entry.user.bot and entry.user.id == self.bot.user.id:
                    continue
                return entry.user
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Could not read audit logs for guild %s", guild.id)
        return None

    async def _process_risky_event(self, guild: discord.Guild, event_type: str, target_id: int | None, target_label: str):
        enabled = await self.bot.db.get_setting(guild.id, "security_protection_enabled", True)
        if not enabled:
            return
        action = AUDIT_ACTIONS[event_type]
        actor = await self._audit_actor(guild, action, target_id)
        now = discord.utils.utcnow()
        actor_id = actor.id if actor else None
        details = f"Event: {event_type}\nTarget: {target_label}\nActor: {actor} (`{actor_id}`)" if actor else f"Event: {event_type}\nTarget: {target_label}\nActor: unknown (audit-log attribution unavailable or ambiguous)."
        await self.bot.db.record_security_event(guild.id, f"risky:{event_type}", actor_id, details, now.isoformat())
        await self._send_security_log(guild, "Security event detected", details)
        # Unknown actors are never punished. Other bots are not inherently trusted:
        # the whitelist and response mode govern them just like human actors.
        if actor is None or actor.id == guild.owner_id or (self.bot.user and actor.id == self.bot.user.id):
            return
        trusted = await self.bot.db.get_setting(guild.id, "security_whitelist", [])
        if actor.id in {int(x) for x in trusted}:
            await self._send_security_log(guild, "Trusted actor activity", f"Whitelisted actor {actor} (`{actor.id}`) performed {event_type}. Event recorded; no automated punishment applied.", 0xFEE75C)
            return
        key = (guild.id, actor.id)
        window = max(1, min(50000, int(await self.bot.db.get_setting(guild.id, "security_window", self.bot.settings.default_security_window_seconds))))
        threshold = max(2, min(25, int(await self.bot.db.get_setting(guild.id, "security_threshold", self.bot.settings.default_security_threshold))))
        events = self.windows[key]
        # Keep a lightweight in-process queue for quick local state, but use the
        # SQLite event log for the authoritative count so a restart does not erase
        # the rolling detection window.
        events.append(now)
        cutoff = now - timedelta(seconds=window)
        while events and events[0] < cutoff:
            events.popleft()
        count = await self.bot.db.count_risky_events(guild.id, actor.id, cutoff.isoformat())
        if count < threshold:
            return
        cooldown_key = (guild.id, actor.id)
        last = self.incident_cooldown.get(cooldown_key)
        if last and (now - last).total_seconds() < 60:
            return
        self.incident_cooldown[cooldown_key] = now
        mode = await self.bot.db.get_setting(guild.id, "security_response_mode", "alert")
        outcome = "Alert only (default). No member was automatically punished."
        if mode == "kick":
            try:
                me = guild.me
                if me and me.guild_permissions.kick_members and actor.top_role < me.top_role and actor.id != guild.owner_id:
                    await guild.kick(actor, reason=f"JARVIS anti-nuke: {count} risky events within {window}s; incident requires owner review")
                    outcome = "Suspected actor kicked after threshold; review the incident and audit logs."
                else:
                    outcome = "Kick response requested but not possible due to permissions or role hierarchy."
            except discord.HTTPException as exc:
                outcome = f"Kick response failed ({exc.__class__.__name__}); manual review required."
        await self.bot.db.create_security_incident(guild.id, actor.id, "high", f"{count} risky events in {window}s. Latest: {event_type}.", count, outcome, now.isoformat())
        await self._send_security_log(guild, "ANTI-NUKE THRESHOLD REACHED", f"Actor: {actor} (`{actor.id}`)\nRisky events: **{count}** within **{window}s**\nResponse: {outcome}\nReview audit logs before taking further action.")

    @anti_nuke.command(name="enable", description="Enable or disable anti-nuke event monitoring (owner only).")
    @app_commands.default_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction, enabled: bool):
        if interaction.guild is None or interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message(embed=error("Server owner only", "Only the server owner can change anti-nuke monitoring."), ephemeral=True)
            return
        await self.bot.db.set_setting(interaction.guild_id, "security_protection_enabled", enabled)
        message = "High-risk event detection is enabled; audit-log matching remains best-effort." if enabled else "High-risk event processing is disabled until re-enabled."
        await interaction.response.send_message(embed=success(f"Anti-nuke {'enabled' if enabled else 'disabled'}", message), ephemeral=True)

    @anti_nuke.command(name="threshold", description="Configure high-risk event count and rolling window (owner only).")
    @app_commands.default_permissions(administrator=True)
    async def threshold(self, interaction: discord.Interaction,
                        count: app_commands.Range[int, 2, 25],
                        window_seconds: app_commands.Range[int, 1, 50000]):
        if interaction.guild is None or interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message(embed=error("Server owner only", "Only the server owner can change anti-nuke thresholds."), ephemeral=True)
            return
        await self.bot.db.set_setting(interaction.guild_id, "security_threshold", count)
        await self.bot.db.set_setting(interaction.guild_id, "security_window", window_seconds)
        await interaction.response.send_message(embed=success("Anti-nuke threshold saved", f"Threshold: **{count} attributed events** within **{window_seconds} seconds**."), ephemeral=True)

    @anti_nuke.command(name="incidents", description="List recent anti-nuke security incidents.")
    @app_commands.default_permissions(manage_guild=True)
    async def incidents(self, interaction: discord.Interaction,
                        limit: app_commands.Range[int, 1, 15] = 10):
        if not await self._require_manage_guild(interaction):
            return
        rows = await self.bot.db.recent_security_incidents(interaction.guild_id, limit)
        embed = panel("Anti-Nuke • Recent Incidents")
        if rows:
            lines = []
            for row in rows:
                actor = f"<@{row['actor_id']}>" if row['actor_id'] is not None else "Unknown actor"
                lines.append(f"**#{row['id']}** • `{row['status']}` • {row['severity']}\nActor: {actor} • Events: {row['event_count']}\n{row['summary'][:180]}")
            embed.description = "\n\n".join(lines)[:4000]
        else:
            embed.description = "No security incidents have been recorded yet."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @anti_nuke.command(name="resolve", description="Mark a recorded security incident as reviewed/resolved.")
    @app_commands.default_permissions(manage_guild=True)
    async def resolve(self, interaction: discord.Interaction, incident_id: app_commands.Range[int, 1, 2147483647]):
        if not await self._require_manage_guild(interaction):
            return
        resolved = await self.bot.db.resolve_security_incident(
            interaction.guild_id, incident_id, interaction.user.id, discord.utils.utcnow().isoformat()
        )
        if resolved:
            await interaction.response.send_message(embed=success("Incident resolved", f"Incident `#{incident_id}` is marked resolved. This records review status; it does not undo past actions."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=warning("Incident not found or already resolved", f"No open incident `#{incident_id}` was found in this server."), ephemeral=True)

    @anti_nuke.command(name="events", description="Show recent high-risk events recorded by the detector.")
    @app_commands.default_permissions(manage_guild=True)
    async def events(self, interaction: discord.Interaction,
                     limit: app_commands.Range[int, 1, 15] = 10):
        if not await self._require_manage_guild(interaction):
            return
        rows = await self.bot.db.recent_security_events(interaction.guild_id, max(limit * 3, 15))
        rows = [row for row in rows if str(row['event_type']).startswith("risky:")][:limit]
        embed = panel("Anti-Nuke • Recent Events")
        if rows:
            lines = []
            for row in rows:
                actor = f"<@{row['actor_id']}>" if row['actor_id'] is not None else "Unknown actor"
                details = str(row['details']).replace("\n", " ")
                lines.append(f"**{row['event_type']}** • {actor}\n{details[:180]}\n`{row['created_at']}`")
            embed.description = "\n\n".join(lines)[:4000]
        else:
            embed.description = "No high-risk events found in the recent event log."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @anti_nuke.command(name="response-mode", description="Set threshold response to alert-only or kick (owner only recommended).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(mode=[app_commands.Choice(name="Alert only (recommended)", value="alert"), app_commands.Choice(name="Kick suspected actor", value="kick")])
    async def response_mode(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        if interaction.guild is None or interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message(embed=error("Server owner only", "Only the server owner can change the anti-nuke response mode."), ephemeral=True)
            return
        await self.bot.db.set_setting(interaction.guild_id, "security_response_mode", mode.value)
        description = "Incidents will be logged and alerted; no automatic punishment." if mode.value == "alert" else "A suspected actor may be kicked after the configured threshold, only when attribution is available and the bot has permission. False positives remain possible."
        await interaction.response.send_message(embed=success("Response mode updated", f"Mode: **{mode.name}**\n{description}"), ephemeral=True)

    @anti_nuke.command(name="status", description="Show anti-nuke detector configuration.")
    @app_commands.default_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        if not await self._require_manage_guild(interaction):
            return
        guild_id = interaction.guild_id
        enabled = await self.bot.db.get_setting(guild_id, "security_protection_enabled", True)
        threshold = await self.bot.db.get_setting(guild_id, "security_threshold", self.bot.settings.default_security_threshold)
        window = await self.bot.db.get_setting(guild_id, "security_window", self.bot.settings.default_security_window_seconds)
        mode = await self.bot.db.get_setting(guild_id, "security_response_mode", "alert")
        embed = panel("Anti-Nuke Status")
        embed.add_field(name="Monitoring", value="Enabled" if enabled else "Disabled", inline=True)
        embed.add_field(name="Threshold", value=f"{threshold} events / {window}s", inline=True)
        embed.add_field(name="Response", value=mode, inline=True)
        embed.add_field(name="Coverage", value="Channel/role creation and deletion, selected role/channel updates, bans and webhook-change notifications. Audit attribution is best-effort; unknown actors are logged but never automatically punished.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await self._process_risky_event(channel.guild, "channel_create", channel.id, f"{channel.name} ({channel.id})")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await self._process_risky_event(role.guild, "role_create", role.id, f"{role.name} ({role.id})")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await self._process_risky_event(channel.guild, "channel_delete", channel.id, f"{channel.name} ({channel.id})")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self._process_risky_event(role.guild, "role_delete", role.id, f"{role.name} ({role.id})")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        await self._process_risky_event(guild, "member_ban", user.id, f"{user} ({user.id})")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        await self._process_risky_event(channel.guild, "webhook_create", None, f"webhook changes in {channel.name} ({channel.id})")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.permissions != after.permissions or before.name != after.name:
            await self._process_risky_event(after.guild, "role_update", after.id, f"{before.name} -> {after.name}; permission change={before.permissions != after.permissions}")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        if before.overwrites != after.overwrites or before.name != after.name:
            await self._process_risky_event(after.guild, "channel_update", after.id, f"{before.name} -> {after.name}; permission overwrite/name changed")

async def setup(bot: commands.Bot):
    await bot.add_cog(AntiNuke(bot))

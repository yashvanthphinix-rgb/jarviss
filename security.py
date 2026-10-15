from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import panel, success, warning, error

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _require_manage_guild(self, interaction: discord.Interaction) -> bool:
        guild = interaction.guild
        perms = getattr(interaction.user, "guild_permissions", None)
        if guild and (guild.owner_id == interaction.user.id or (perms and (perms.administrator or perms.manage_guild))):
            return True
        await interaction.response.send_message(embed=error("Permission denied", "You need Manage Server permissions to use this security command."), ephemeral=True)
        return False

    async def _require_manage_channels(self, interaction: discord.Interaction) -> bool:
        guild = interaction.guild
        perms = getattr(interaction.user, "guild_permissions", None)
        if guild and (guild.owner_id == interaction.user.id or (perms and (perms.administrator or perms.manage_channels))):
            return True
        await interaction.response.send_message(embed=error("Permission denied", "You need Manage Channels permissions to use this lockdown command."), ephemeral=True)
        return False

    security = app_commands.Group(name="security", description="Configure and inspect server security.")

    @security.command(name="status", description="Show security configuration and recent incidents.")
    @app_commands.default_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        if not await self._require_manage_guild(interaction):
            return
        threshold = await self.bot.db.get_setting(interaction.guild_id, "security_threshold", self.bot.settings.default_security_threshold)
        window = await self.bot.db.get_setting(interaction.guild_id, "security_window", self.bot.settings.default_security_window_seconds)
        log_channel = await self.bot.db.get_setting(interaction.guild_id, "security_log_channel", None)
        events = await self.bot.db.recent_security_events(interaction.guild_id, 5)
        embed = panel("Security Status")
        embed.add_field(name="Event threshold", value=str(threshold), inline=True)
        embed.add_field(name="Window", value=f"{window}s", inline=True)
        embed.add_field(name="Security log channel", value=f"<#{log_channel}>" if log_channel else "Not configured", inline=True)
        embed.add_field(name="Recent events", value=str(len(events)), inline=True)
        embed.add_field(name="Protection note", value="Monitoring records events; this starter does not claim to block every destructive action before Discord processes it.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @security.command(name="threshold", description="Set the event threshold for security monitoring.")
    @app_commands.default_permissions(administrator=True)
    async def threshold(self, interaction: discord.Interaction,
                        count: app_commands.Range[int, 2, 25],
                        window_seconds: app_commands.Range[int, 1, 50000]):
        if not await self._require_manage_guild(interaction):
            return
        await self.bot.db.set_setting(interaction.guild_id, "security_threshold", count)
        await self.bot.db.set_setting(interaction.guild_id, "security_window", window_seconds)
        await interaction.response.send_message(embed=success("Security threshold saved", f"Threshold: **{count} events** within **{window_seconds} seconds**."), ephemeral=True)

    @security.command(name="lockdown", description="Restrict @everyone from sending messages in a text channel.")
    @app_commands.default_permissions(manage_channels=True)
    async def lockdown(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not await self._require_manage_channels(interaction):
            return
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        if overwrite.send_messages is False:
            await interaction.response.send_message(embed=warning("Already locked", f"{channel.mention} already denies Send Messages to @everyone."), ephemeral=True); return
        overwrite.send_messages = False
        try:
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"JARVIS lockdown requested by {interaction.user}")
        except discord.HTTPException as exc:
            await interaction.response.send_message(embed=error("Lockdown failed", f"Discord rejected the change: {exc.__class__.__name__}."), ephemeral=True); return
        await interaction.response.send_message(embed=success("Channel locked", f"@everyone can no longer send messages in {channel.mention}."), ephemeral=True)

    @security.command(name="unlock", description="Remove the @everyone Send Messages denial from a text channel.")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not await self._require_manage_channels(interaction):
            return
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        if overwrite.send_messages is not False:
            await interaction.response.send_message(embed=warning("No lockdown overwrite", f"{channel.mention} does not have an explicit @everyone Send Messages denial to remove."), ephemeral=True); return
        overwrite.send_messages = None
        try:
            await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"JARVIS unlock requested by {interaction.user}")
        except discord.HTTPException as exc:
            await interaction.response.send_message(embed=error("Unlock failed", f"Discord rejected the change: {exc.__class__.__name__}."), ephemeral=True); return
        await interaction.response.send_message(embed=success("Channel unlocked", f"Removed the explicit @everyone Send Messages denial from {channel.mention}."), ephemeral=True)

    @security.command(name="health", description="Check JARVIS security prerequisites and logging configuration.")
    @app_commands.default_permissions(manage_guild=True)
    async def health(self, interaction: discord.Interaction):
        if not await self._require_manage_guild(interaction):
            return
        guild = interaction.guild
        if guild is None or guild.me is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        me = guild.me
        checks = [
            ("View Audit Log", me.guild_permissions.view_audit_log, "Required for anti-nuke actor attribution"),
            ("Kick Members", me.guild_permissions.kick_members, "Required only for optional kick responses"),
            ("Manage Channels", me.guild_permissions.manage_channels, "Required for setup/lockdown operations"),
            ("Manage Roles", me.guild_permissions.manage_roles, "Required by role-management operations"),
            ("Ban Members", me.guild_permissions.ban_members, "Required for /ban"),
            ("Moderate Members", me.guild_permissions.moderate_members, "Required for /timeout"),
        ]
        lines = [f"{'[OK]' if good else '[MISSING]'} **{label}:** {'available' if good else 'missing'} — {hint}" for label, good, hint in checks]
        channel_id = await self.bot.db.get_setting(guild.id, "security_log_channel", None)
        if not channel_id:
            channel_id = await self.bot.db.get_setting(guild.id, "log_channel_security", None)
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            perms = channel.permissions_for(me)
            log_ok = perms.view_channel and perms.send_messages and perms.embed_links
            lines.append(f"{'[OK]' if log_ok else '[MISSING]'} **Security log channel:** {'configured and usable' if log_ok else 'configured but permissions are incomplete'} — {channel.mention}")
        else:
            lines.append("[MISSING] **Security log channel:** not configured; run `/setup-logs` and verify the security destination.")
        lines.append("[INFO] Gateway event detection and audit-log attribution remain best-effort; this health check cannot certify real-time protection.")
        await interaction.response.send_message(embed=panel("Security Health Check", "\n".join(lines)[:4000]), ephemeral=True)

    @security.command(name="permission-audit", description="List roles with high-impact server permissions.")
    @app_commands.default_permissions(manage_guild=True)
    async def permission_audit(self, interaction: discord.Interaction):
        if not await self._require_manage_guild(interaction):
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        sensitive = {
            "administrator": "Administrator",
            "manage_guild": "Manage Server",
            "manage_roles": "Manage Roles",
            "manage_channels": "Manage Channels",
            "ban_members": "Ban Members",
            "kick_members": "Kick Members",
            "manage_webhooks": "Manage Webhooks",
        }
        lines = []
        for role in sorted(guild.roles, key=lambda item: item.position, reverse=True):
            grants = [label for attr, label in sensitive.items() if getattr(role.permissions, attr, False)]
            if grants:
                holders = len(role.members)
                lines.append(f"**{role.name}** (`{role.id}`) — {', '.join(grants)}; holders: {holders}")
        embed = panel("Security • Privileged Role Audit")
        embed.description = "\n".join(lines[:25])[:4000] if lines else "No roles with the scanned high-impact permissions were found."
        embed.set_footer(text="This is a permission review, not a vulnerability verdict. Review role assignments and hierarchy manually.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @security.command(name="events", description="Show the latest recorded security events.")
    @app_commands.default_permissions(manage_guild=True)
    async def security_events(self, interaction: discord.Interaction,
                              limit: app_commands.Range[int, 1, 15] = 10):
        if not await self._require_manage_guild(interaction):
            return
        rows = await self.bot.db.recent_security_events(interaction.guild_id, limit)
        lines = []
        for row in rows:
            actor = f"<@{row['actor_id']}>" if row['actor_id'] is not None else "Unknown actor"
            details = str(row['details']).replace("\n", " ")
            lines.append(f"**{row['event_type']}** • {actor}\n{details[:160]}\n`{row['created_at']}`")
        embed = panel("Security • Recent Events")
        embed.description = "\n\n".join(lines)[:4000] if lines else "No security events have been recorded yet."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _server_owner_only(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None or interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message(embed=error("Server owner only", "Only the server owner can use panic lockdown controls."), ephemeral=True)
            return False
        return True

    @security.command(name="panic-lockdown", description="Lock @everyone sending in all text channels and save prior settings (owner only).")
    @app_commands.default_permissions(administrator=True)
    async def panic_lockdown(self, interaction: discord.Interaction):
        if not await self._server_owner_only(interaction):
            return
        guild = interaction.guild
        if guild is None:
            return
        active = await self.bot.db.get_setting(guild.id, "panic_lockdown_active", False)
        if active:
            await interaction.response.send_message(embed=warning("Panic lockdown already active", "Use `/security panic-unlock` to restore the saved @everyone Send Messages settings."), ephemeral=True)
            return
        if guild.me is None or not guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message(embed=error("Missing permission", "JARVIS needs Manage Channels to apply panic lockdown."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        snapshot = {}
        channels = list(guild.text_channels)
        for channel in channels:
            snapshot[str(channel.id)] = channel.overwrites_for(guild.default_role).send_messages
        await self.bot.db.set_setting(guild.id, "panic_lockdown_snapshot", snapshot)
        await self.bot.db.set_setting(guild.id, "panic_lockdown_active", True)
        succeeded, failed = 0, []
        for channel in channels:
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = False
            try:
                await channel.set_permissions(guild.default_role, overwrite=overwrite, reason=f"JARVIS emergency lockdown requested by server owner {interaction.user}")
                succeeded += 1
            except discord.HTTPException:
                failed.append(channel.name)
        await self.bot.db.record_security_event(guild.id, "security:panic_lockdown", interaction.user.id,
            f"Locked {succeeded}/{len(channels)} text channels; failed: {', '.join(failed[:20]) or 'none'}", discord.utils.utcnow().isoformat())
        note = f"Locked **{succeeded}/{len(channels)}** text channels. Prior @everyone Send Messages states were saved."
        if failed:
            note += f"\nFailed channels: {', '.join(failed[:10])}. Fix permissions and retry/unlock as needed."
        await interaction.followup.send(embed=warning("PANIC LOCKDOWN APPLIED", note), ephemeral=True)

    @security.command(name="panic-unlock", description="Restore the saved @everyone Send Messages settings (owner only).")
    @app_commands.default_permissions(administrator=True)
    async def panic_unlock(self, interaction: discord.Interaction):
        if not await self._server_owner_only(interaction):
            return
        guild = interaction.guild
        if guild is None:
            return
        active = await self.bot.db.get_setting(guild.id, "panic_lockdown_active", False)
        if not active:
            await interaction.response.send_message(embed=warning("Panic lockdown is not active", "There is no active panic lockdown to restore. This avoids applying an old permission snapshot unexpectedly."), ephemeral=True)
            return
        snapshot = await self.bot.db.get_setting(guild.id, "panic_lockdown_snapshot", None)
        if not isinstance(snapshot, dict):
            await interaction.response.send_message(embed=warning("No snapshot found", "JARVIS has no saved panic-lockdown permission snapshot to restore."), ephemeral=True)
            return
        if guild.me is None or not guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message(embed=error("Missing permission", "JARVIS needs Manage Channels to restore permission settings."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        restored, failed, missing = 0, [], 0
        for raw_id, previous_value in snapshot.items():
            try:
                channel = guild.get_channel(int(raw_id))
            except (TypeError, ValueError):
                channel = None
            if not isinstance(channel, discord.TextChannel):
                missing += 1
                continue
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = previous_value if previous_value in (True, False, None) else None
            try:
                await channel.set_permissions(guild.default_role, overwrite=overwrite, reason=f"JARVIS panic-lockdown restoration requested by server owner {interaction.user}")
                restored += 1
            except discord.HTTPException:
                failed.append(channel.name)
        if not failed:
            await self.bot.db.set_setting(guild.id, "panic_lockdown_active", False)
        await self.bot.db.record_security_event(guild.id, "security:panic_unlock", interaction.user.id,
            f"Restored {restored} text channels; failed: {', '.join(failed[:20]) or 'none'}; missing/deleted: {missing}", discord.utils.utcnow().isoformat())
        note = f"Restored **{restored}** channel(s) to their saved @everyone Send Messages values."
        if failed:
            note += f"\nFailed channels: {', '.join(failed[:10])}. The snapshot is retained so you can retry."
        if missing:
            note += f"\nSkipped {missing} deleted or non-text channel(s)."
        await interaction.followup.send(embed=success("Panic lockdown restoration", note), ephemeral=True)

    @security.command(name="protection", description="Enable or disable security event monitoring.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(enabled="Turn security monitoring on or off")
    async def protection(self, interaction: discord.Interaction, enabled: bool):
        if not await self._require_manage_guild(interaction):
            return
        await self.bot.db.set_setting(interaction.guild_id, "security_protection_enabled", enabled)
        state = "enabled" if enabled else "disabled"
        note = "Monitoring is enabled; this does not guarantee pre-emptive blocking of every destructive action."
        if not enabled:
            note = "Security event monitoring is disabled. Other bot features may still operate."
        await interaction.response.send_message(
            embed=success(f"Security monitoring {state}", note), ephemeral=True
        )

    @security.command(name="whitelist-add", description="Trust a member or bot for configured security responses.")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_add(self, interaction: discord.Interaction, member: discord.Member):
        if not await self._require_manage_guild(interaction):
            return
        ids = await self.bot.db.get_setting(interaction.guild_id, "security_whitelist", [])
        ids = list(dict.fromkeys(int(x) for x in ids))
        if member.id in ids:
            await interaction.response.send_message(embed=warning("Already trusted", f"{member.mention} is already on the security whitelist."), ephemeral=True)
            return
        ids.append(member.id)
        await self.bot.db.set_setting(interaction.guild_id, "security_whitelist", ids)
        await interaction.response.send_message(embed=success("Whitelist updated", f"Added {member.mention} to the trusted list. The anti-nuke handler checks this list before applying an automatic threshold response."), ephemeral=True)

    @security.command(name="whitelist-remove", description="Remove a member or bot from the security whitelist.")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_remove(self, interaction: discord.Interaction, member: discord.Member):
        if not await self._require_manage_guild(interaction):
            return
        ids = await self.bot.db.get_setting(interaction.guild_id, "security_whitelist", [])
        ids = [int(x) for x in ids if int(x) != member.id]
        await self.bot.db.set_setting(interaction.guild_id, "security_whitelist", ids)
        await interaction.response.send_message(embed=success("Whitelist updated", f"Removed {member.mention} from the trusted list if present."), ephemeral=True)

    @security.command(name="whitelist-list", description="Show members and bots on the security whitelist.")
    @app_commands.default_permissions(manage_guild=True)
    async def whitelist_list(self, interaction: discord.Interaction):
        if not await self._require_manage_guild(interaction):
            return
        ids = await self.bot.db.get_setting(interaction.guild_id, "security_whitelist", [])
        lines = [f"• <@{int(uid)}> (`{int(uid)}`)" for uid in ids]
        embed = panel("Security Whitelist")
        embed.description = "\n".join(lines) if lines else "No members or bots are whitelisted."
        embed.set_footer(text="Anti-nuke detection consults this list; unrelated modules may not.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @security.command(name="delegate-add", description="Grant a trusted member access to selected bot administration tasks.")
    async def delegate_add(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message(embed=error("Server owner only", "Only the server owner can add delegated bot administrators."), ephemeral=True)
            return
        ids = await self.bot.db.get_setting(interaction.guild_id, "security_delegates", [])
        ids = list(dict.fromkeys(int(x) for x in ids))
        if member.id not in ids:
            ids.append(member.id)
            await self.bot.db.set_setting(interaction.guild_id, "security_delegates", ids)
        await interaction.response.send_message(embed=success("Delegation saved", f"{member.mention} is listed as a delegated administrator. This does not grant Discord permissions or override command-specific checks."), ephemeral=True)

    @security.command(name="delegate-remove", description="Remove a delegated bot administrator.")
    async def delegate_remove(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message(embed=error("Server owner only", "Only the server owner can remove delegated bot administrators."), ephemeral=True)
            return
        ids = await self.bot.db.get_setting(interaction.guild_id, "security_delegates", [])
        ids = [int(x) for x in ids if int(x) != member.id]
        await self.bot.db.set_setting(interaction.guild_id, "security_delegates", ids)
        await interaction.response.send_message(embed=success("Delegation updated", f"Removed {member.mention} from the delegated list if present."), ephemeral=True)

    @security.command(name="delegate-list", description="List delegated bot administrators.")
    @app_commands.default_permissions(manage_guild=True)
    async def delegate_list(self, interaction: discord.Interaction):
        ids = await self.bot.db.get_setting(interaction.guild_id, "security_delegates", [])
        embed = panel("Delegated Administrators")
        embed.description = "\n".join(f"• <@{int(uid)}> (`{int(uid)}`)" for uid in ids) if ids else "No delegated administrators configured."
        embed.set_footer(text="Delegation is informational until a command's permission check uses it.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        # This is detection/logging, not a guarantee of pre-emptive prevention.
        try:
            await self.bot.db.record_security_event(
                channel.guild.id, "channel_deleted", None,
                f"Channel deleted: {channel.name} ({channel.id}); actor attribution not yet verified.",
                discord.utils.utcnow().isoformat(),
            )
            channel_id = await self.bot.db.get_setting(channel.guild.id, "security_log_channel", None)
            if channel_id:
                destination = channel.guild.get_channel(int(channel_id))
                if isinstance(destination, discord.TextChannel):
                    await destination.send(embed=warning("Channel deletion detected", f"Deleted channel: **{channel.name}** (`{channel.id}`).\nActor: unknown from this event alone."))
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Failed to process channel deletion event")

async def setup(bot):
    await bot.add_cog(Security(bot))

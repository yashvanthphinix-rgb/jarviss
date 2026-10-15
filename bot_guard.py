from __future__ import annotations

import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import panel, success, warning, error

log = logging.getLogger("jarvis.bot_guard")


class BotGuard(commands.Cog):
    """Owner-configured bot admission guard. Safe default is alert-only."""

    bot_guard = app_commands.Group(name="bot-guard", description="Guard bot joins and manage approved bot IDs.")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _owner_only(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None or interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message(
                embed=error("Server owner only", "Only the server owner can change Bot Guard settings."),
                ephemeral=True,
            )
            return False
        return True

    async def _security_log(self, guild: discord.Guild, title: str, description: str, color: int = 0xED4245) -> None:
        channel_id = await self.bot.db.get_setting(guild.id, "security_log_channel", None)
        if not channel_id:
            channel_id = await self.bot.db.get_setting(guild.id, "log_channel_security", None)
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            try:
                await channel.send(
                    embed=panel(title, description[:4000], color=color),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                log.exception("Failed to send Bot Guard log for guild %s", guild.id)

    async def _find_bot_inviter(self, guild: discord.Guild, target_id: int):
        me = guild.me
        if me is None or not me.guild_permissions.view_audit_log:
            return None
        try:
            now = discord.utils.utcnow()
            async for entry in guild.audit_logs(limit=8, action=discord.AuditLogAction.bot_add):
                if entry.created_at and (now - entry.created_at) > timedelta(seconds=20):
                    continue
                if getattr(entry.target, "id", None) == target_id:
                    return entry.user
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Could not inspect bot-add audit log in guild %s", guild.id)
        return None

    @bot_guard.command(name="status", description="Show Bot Guard settings and approved bot count.")
    @app_commands.default_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        enabled = await self.bot.db.get_setting(guild.id, "bot_guard_enabled", True)
        mode = await self.bot.db.get_setting(guild.id, "bot_guard_mode", "alert")
        approved = await self.bot.db.get_setting(guild.id, "bot_guard_allowlist", [])
        bots = sum(1 for member in guild.members if member.bot)
        embed = panel("JARVIS • Bot Guard")
        embed.add_field(name="Monitoring", value="Enabled" if enabled else "Disabled", inline=True)
        embed.add_field(name="Response mode", value=str(mode).upper(), inline=True)
        embed.add_field(name="Approved bot IDs", value=str(len(approved)), inline=True)
        embed.add_field(name="Cached server bots", value=str(bots), inline=True)
        embed.add_field(name="Default behavior", value="Unapproved bot joins are logged. Automatic kicking is off unless the owner selects `kick` mode.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot_guard.command(name="enable", description="Enable or disable Bot Guard monitoring (owner only).")
    @app_commands.default_permissions(administrator=True)
    async def enable(self, interaction: discord.Interaction, enabled: bool):
        if not await self._owner_only(interaction):
            return
        await self.bot.db.set_setting(interaction.guild_id, "bot_guard_enabled", enabled)
        state = "enabled" if enabled else "disabled"
        detail = "Join checks are active; response mode remains separately configured." if enabled else "Bot-join checks are disabled until re-enabled."
        await interaction.response.send_message(embed=success(f"Bot Guard {state}", detail), ephemeral=True)

    @bot_guard.command(name="mode", description="Choose alert-only or automatic kick for unapproved bot joins (owner only).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(mode=[
        app_commands.Choice(name="Alert only (recommended)", value="alert"),
        app_commands.Choice(name="Kick unapproved bot", value="kick"),
    ])
    async def mode(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        if not await self._owner_only(interaction):
            return
        await self.bot.db.set_setting(interaction.guild_id, "bot_guard_mode", mode.value)
        detail = (
            "Unapproved bot joins will be logged only."
            if mode.value == "alert"
            else "JARVIS will attempt to kick newly joined bots that are not on the allowlist. A bot can still join if Discord permissions or role hierarchy prevent the kick."
        )
        await interaction.response.send_message(embed=success("Bot Guard mode updated", f"Mode: **{mode.name}**\n{detail}"), ephemeral=True)

    @bot_guard.command(name="allow", description="Approve a bot account by adding it to the allowlist (owner only).")
    @app_commands.default_permissions(administrator=True)
    async def allow(self, interaction: discord.Interaction, bot_member: discord.Member):
        if not await self._owner_only(interaction):
            return
        if not bot_member.bot:
            await interaction.response.send_message(embed=warning("Not a bot", "Select a bot member to approve."), ephemeral=True)
            return
        ids = [int(x) for x in await self.bot.db.get_setting(interaction.guild_id, "bot_guard_allowlist", [])]
        if bot_member.id not in ids:
            ids.append(bot_member.id)
        await self.bot.db.set_setting(interaction.guild_id, "bot_guard_allowlist", ids)
        await interaction.response.send_message(embed=success("Bot approved", f"{bot_member.mention} (`{bot_member.id}`) is now allowlisted."), ephemeral=True)

    @bot_guard.command(name="remove", description="Remove a bot ID from the allowlist (owner only).")
    @app_commands.default_permissions(administrator=True)
    async def remove(self, interaction: discord.Interaction, bot_id: str):
        if not await self._owner_only(interaction):
            return
        try:
            target_id = int(bot_id.strip())
            if target_id <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(embed=error("Invalid bot ID", "Enter the numeric Discord user ID shown by `/bot-guard list`."), ephemeral=True)
            return
        ids = [int(x) for x in await self.bot.db.get_setting(interaction.guild_id, "bot_guard_allowlist", [])]
        ids = [uid for uid in ids if uid != target_id]
        await self.bot.db.set_setting(interaction.guild_id, "bot_guard_allowlist", ids)
        await interaction.response.send_message(embed=success("Allowlist updated", f"Bot ID `{target_id}` is no longer approved if it was present."), ephemeral=True)

    @bot_guard.command(name="list", description="List approved bot IDs and current server bot members.")
    @app_commands.default_permissions(manage_guild=True)
    async def list_bots(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        ids = [int(x) for x in await self.bot.db.get_setting(guild.id, "bot_guard_allowlist", [])]
        approved_lines = []
        for uid in ids[:20]:
            member = guild.get_member(uid)
            approved_lines.append(f"• {member} (`{uid}`)" if member else f"• Unknown/not cached bot (`{uid}`)")
        current_bots = [member for member in guild.members if member.bot and (self.bot.user is None or member.id != self.bot.user.id)]
        current_lines = [f"• {member} (`{member.id}`) — {'approved' if member.id in ids else 'not allowlisted'}" for member in current_bots[:20]]
        embed = panel("Bot Guard • Allowlist")
        embed.add_field(name=f"Approved IDs ({len(ids)})", value=("\n".join(approved_lines) or "None")[:1000], inline=False)
        embed.add_field(name=f"Cached bots ({len(current_bots)})", value=("\n".join(current_lines) or "No bots found in the current member cache")[:1000], inline=False)
        embed.set_footer(text="Lists show up to 20 entries per section.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot_guard.command(name="scan", description="Report unapproved bots currently in the server without taking action.")
    @app_commands.default_permissions(manage_guild=True)
    async def scan(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        ids = {int(x) for x in await self.bot.db.get_setting(guild.id, "bot_guard_allowlist", [])}
        unknown = [m for m in guild.members if m.bot and (self.bot.user is None or m.id != self.bot.user.id) and m.id not in ids]
        embed = panel("Bot Guard • Read-only scan")
        embed.description = "\n".join(f"• {m} (`{m.id}`)" for m in unknown[:20]) if unknown else "No unapproved bots found in the currently cached member list."
        embed.set_footer(text=f"Found {len(unknown)} unapproved bot(s). Scan does not kick or modify anything.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot or self.bot.user is None or member.id == self.bot.user.id:
            return
        enabled = await self.bot.db.get_setting(member.guild.id, "bot_guard_enabled", True)
        if not enabled:
            return
        approved = {int(x) for x in await self.bot.db.get_setting(member.guild.id, "bot_guard_allowlist", [])}
        if member.id in approved:
            return
        inviter = await self._find_bot_inviter(member.guild, member.id)
        inviter_text = f"{inviter} (`{inviter.id}`)" if inviter else "unknown (audit-log attribution unavailable or delayed)"
        mode = await self.bot.db.get_setting(member.guild.id, "bot_guard_mode", "alert")
        details = f"Bot: {member} (`{member.id}`)\nAdded by: {inviter_text}\nAction mode: {mode}"
        await self.bot.db.record_security_event(member.guild.id, "bot_guard:unapproved_join", inviter.id if inviter else None, details, discord.utils.utcnow().isoformat())
        outcome = "Alert only; no action was taken."
        if mode == "kick":
            try:
                me = member.guild.me
                if me and me.guild_permissions.kick_members and member.top_role < me.top_role:
                    await member.kick(reason="JARVIS Bot Guard: bot is not on the owner-approved allowlist")
                    outcome = "Unapproved bot kick attempted successfully."
                else:
                    outcome = "Could not kick the bot: check Kick Members permission and role hierarchy."
            except discord.HTTPException as exc:
                outcome = f"Kick failed ({exc.__class__.__name__}); manual review required."
        await self._security_log(member.guild, "BOT GUARD • UNAPPROVED BOT", f"{details}\nOutcome: {outcome}")


async def setup(bot: commands.Bot):
    await bot.add_cog(BotGuard(bot))

from __future__ import annotations
import datetime
import discord
from discord import app_commands
from discord.ext import commands
from services.permissions import PermissionService
from services.notifications import notify_owner, notify_member
from utils.embeds import panel, success, error, warning

def utcnow_iso() -> str:
    return discord.utils.utcnow().isoformat()

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    async def _target(self, interaction: discord.Interaction, user: discord.User, permission: str):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            return None, "This command must be used in a server."
        target = guild.get_member(user.id)
        if target is None:
            return None, "That user is not currently a member of this server."
        bot_member = guild.me
        if bot_member is None:
            return None, "Could not resolve JARVIS's member permissions."
        ok, reason = PermissionService.can_moderate(interaction.user, target, bot_member, require=permission)
        if not ok:
            return None, reason
        return target, ""

    async def _record_and_notify(self, interaction, target, action, reason, *, duration=None):
        guild = interaction.guild
        await self.bot.db.record_case(guild.id, target.id, interaction.user.id, action, reason, utcnow_iso())
        embed = panel(f"Moderation: {action.title()}", color=0xD4AF37)
        embed.add_field(name="Member", value=f"{target} (`{target.id}`)", inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Reason", value=reason[:1024], inline=False)
        if duration:
            embed.add_field(name="Duration", value=duration, inline=True)
        await notify_owner(guild, embed)
        logging_cog = self.bot.get_cog("LoggingSystem")
        if logging_cog is not None:
            details = f"Action: **{action.title()}**\nTarget: {target} (`{target.id}`)\nModerator: {interaction.user} (`{interaction.user.id}`)\nReason: {reason[:900]}"
            if duration:
                details += f"\nDuration: {duration}"
            await logging_cog._log(guild, "moderation", f"Moderation action: {action.title()}", details, 0xD4AF37)
        return embed

    @app_commands.command(name="ban", description="Ban a member from this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        target, err = await self._target(interaction, member, "ban_members")
        if err:
            await interaction.response.send_message(embed=error("Ban denied", err), ephemeral=True); return
        try:
            await interaction.guild.ban(target, reason=f"{interaction.user} ({interaction.user.id}): {reason}")
        except discord.HTTPException as exc:
            await interaction.response.send_message(embed=error("Ban failed", f"Discord rejected the action: {exc.__class__.__name__}."), ephemeral=True); return
        embed = await self._record_and_notify(interaction, target, "ban", reason)
        await notify_member(target, panel("You were banned", f"Server: **{interaction.guild.name}**\nReason: {reason}"))
        await interaction.response.send_message(embed=success("Member banned", f"{target.mention} was banned."), ephemeral=True)

    @app_commands.command(name="kick", description="Kick a member from this server.")
    @app_commands.guild_only()
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        target, err = await self._target(interaction, member, "kick_members")
        if err:
            await interaction.response.send_message(embed=error("Kick denied", err), ephemeral=True); return
        try:
            await target.kick(reason=f"{interaction.user} ({interaction.user.id}): {reason}")
        except discord.HTTPException as exc:
            await interaction.response.send_message(embed=error("Kick failed", f"Discord rejected the action: {exc.__class__.__name__}."), ephemeral=True); return
        await self._record_and_notify(interaction, target, "kick", reason)
        await notify_member(target, panel("You were kicked", f"Server: **{interaction.guild.name}**\nReason: {reason}"))
        await interaction.response.send_message(embed=success("Member kicked", f"{target} was kicked."), ephemeral=True)

    @app_commands.command(name="timeout", description="Timeout a member for 1 to 50000 seconds.")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member,
                      duration_seconds: app_commands.Range[int, 1, 50000], reason: str = "No reason provided"):
        target, err = await self._target(interaction, member, "moderate_members")
        if err:
            await interaction.response.send_message(embed=error("Timeout denied", err), ephemeral=True); return
        until = discord.utils.utcnow() + datetime.timedelta(seconds=duration_seconds)
        try:
            await target.timeout(until, reason=f"{interaction.user} ({interaction.user.id}): {reason}")
        except discord.HTTPException as exc:
            await interaction.response.send_message(embed=error("Timeout failed", f"Discord rejected the action: {exc.__class__.__name__}."), ephemeral=True); return
        duration_text = self._format_duration(duration_seconds)
        await self._record_and_notify(interaction, target, "timeout", reason, duration=duration_text)
        await notify_member(target, panel("You were timed out", f"Server: **{interaction.guild.name}**\nDuration: {duration_text} ({duration_seconds} seconds)\nReason: {reason}"))
        await interaction.response.send_message(embed=success("Timeout applied", f"{target.mention} was timed out for {duration_text} ({duration_seconds} seconds)."), ephemeral=True)

    @app_commands.command(name="untimeout", description="Remove a member's timeout.")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        target, err = await self._target(interaction, member, "moderate_members")
        if err:
            await interaction.response.send_message(embed=error("Untimeout denied", err), ephemeral=True); return
        try:
            await target.timeout(None, reason=f"{interaction.user} ({interaction.user.id}): {reason}")
        except discord.HTTPException as exc:
            await interaction.response.send_message(embed=error("Untimeout failed", f"Discord rejected the action: {exc.__class__.__name__}."), ephemeral=True); return
        await self._record_and_notify(interaction, target, "untimeout", reason)
        await notify_member(target, panel("Timeout removed", f"Server: **{interaction.guild.name}**\nReason: {reason}"))
        await interaction.response.send_message(embed=success("Timeout removed", f"Timeout removed for {target.mention}."), ephemeral=True)

    @app_commands.command(name="warn", description="Warn a member and store the case.")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        target, err = await self._target(interaction, member, "moderate_members")
        if err:
            await interaction.response.send_message(embed=error("Warning denied", err), ephemeral=True); return
        await self._record_and_notify(interaction, target, "warn", reason)
        await notify_member(target, panel("You received a warning", f"Server: **{interaction.guild.name}**\nReason: {reason}"))
        await interaction.response.send_message(embed=success("Warning recorded", f"Warning recorded for {target.mention}."), ephemeral=True)

    @app_commands.command(name="warnings", description="View a member's recent moderation history.")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        rows = await self.bot.db.get_cases(interaction.guild_id, member.id, 10)
        if not rows:
            await interaction.response.send_message(embed=panel("Moderation History", "No stored cases found."), ephemeral=True); return
        embed = panel(f"Recent Cases • {member}")
        for row in rows:
            embed.add_field(name=f"#{row['id']} • {row['action']} • {row['created_at'][:19]}",
                            value=f"Reason: {row['reason'][:800]}\nActor ID: `{row['actor_id']}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))

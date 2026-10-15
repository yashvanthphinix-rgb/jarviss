from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import panel, success, error, warning

log = logging.getLogger(__name__)

# These names are also used as database setting suffixes.
LOG_CHANNELS = {
    "moderation": "moderation-logs",
    "messages": "message-logs",
    "members": "member-logs",
    "channels": "channel-logs",
    "voice": "voice-logs",
    "security": "security-logs",
    "bot": "bot-logs",
}

class LoggingSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_log(self, guild: discord.Guild, category: str, embed: discord.Embed) -> None:
        """Best-effort delivery; logging failures must not break Discord events."""
        key = f"log_channel_{category}"
        try:
            channel_id = await self.bot.db.get_setting(guild.id, key, None)
            if not channel_id and category == "security":
                channel_id = await self.bot.db.get_setting(guild.id, "security_log_channel", None)
            channel = guild.get_channel(int(channel_id)) if channel_id else None
            if isinstance(channel, discord.TextChannel):
                await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except (discord.HTTPException, ValueError, TypeError):
            log.exception("Could not send %s log for guild %s", category, guild.id)

    async def _log(self, guild, category, title, description, color=0x9D4EDD):
        embed = panel(title, description[:4000], color=color)
        await self.send_log(guild, category, embed)

    @app_commands.command(name="setup-logs", description="Create private channels for all seven log categories.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def setup_logs(self, interaction: discord.Interaction):
        guild = interaction.guild
        me = guild.me if guild else None
        if guild is None or me is None or not me.guild_permissions.manage_channels:
            await interaction.response.send_message(embed=error("Missing permission", "The bot needs Manage Channels to configure logging."), ephemeral=True)
            return
        category_name = "「 PRIVATE LOGS 」"
        category = discord.utils.get(guild.categories, name=category_name)
        try:
            if category is None:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, read_message_history=True),
                }
                category = await guild.create_category(category_name, overwrites=overwrites, reason="Configure private event logs")
            created = []
            for key, channel_name in LOG_CHANNELS.items():
                channel = discord.utils.get(category.text_channels, name=channel_name)
                if channel is None:
                    channel = await guild.create_text_channel(channel_name, category=category, reason="Configure event logs")
                await self.bot.db.set_setting(guild.id, f"log_channel_{key}", channel.id)
                if key == "security":
                    await self.bot.db.set_setting(guild.id, "security_log_channel", channel.id)
                created.append(f"**{key.title()}:** {channel.mention}")
        except discord.HTTPException as exc:
            await interaction.response.send_message(embed=error("Setup failed", f"Discord rejected the setup ({exc.__class__.__name__}). Check the bot's channel permissions."), ephemeral=True)
            return
        await interaction.response.send_message(embed=success("Logging configured", f"Created or verified seven private log channels in {category.mention}.\n\n" + "\n".join(created)), ephemeral=True)

    @app_commands.command(name="set-log-channel", description="Choose the destination channel for one log category.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(category=[app_commands.Choice(name=k.title(), value=k) for k in LOG_CHANNELS])
    async def set_log_channel(self, interaction: discord.Interaction, category: app_commands.Choice[str], channel: discord.TextChannel):
        perms = channel.permissions_for(interaction.guild.me)
        if not perms.send_messages or not perms.embed_links:
            await interaction.response.send_message(embed=error("Cannot use channel", "The bot needs Send Messages and Embed Links in that channel."), ephemeral=True)
            return
        await self.bot.db.set_setting(interaction.guild_id, f"log_channel_{category.value}", channel.id)
        if category.value == "security":
            await self.bot.db.set_setting(interaction.guild_id, "security_log_channel", channel.id)
        await interaction.response.send_message(embed=success("Log channel updated", f"{category.name} events will be sent to {channel.mention}."), ephemeral=True)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild and not before.author.bot and before.content != after.content:
            await self._log(before.guild, "messages", "Message edited", f"Author: {before.author} (`{before.author.id}`)\nChannel: {before.channel.mention}\nMessage ID: `{before.id}`\nBefore: {(before.content or '[content unavailable]')[:900]}\nAfter: {(after.content or '[content unavailable]')[:900]}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild and not message.author.bot:
            await self._log(message.guild, "messages", "Message deleted", f"Author: {message.author} (`{message.author.id}`)\nChannel: {message.channel.mention}\nMessage ID: `{message.id}`\nContent captured before deletion: {(message.content or '[empty, unavailable, or Message Content Intent disabled]')[:1500]}", 0xED4245)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        messages = list(messages)
        if messages:
            guild = messages[0].guild
            if guild:
                await self._log(guild, "messages", "Bulk message deletion", f"Messages in batch: **{len(messages)}**\nChannel: {messages[0].channel.mention}\nIDs: " + ", ".join(str(m.id) for m in messages[:40]), 0xED4245)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._log(member.guild, "members", "Member joined", f"Member: {member} (`{member.id}`)\nAccount created: <t:{int(member.created_at.timestamp())}:R>")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._log(member.guild, "members", "Member left or was removed", f"Member: {member} (`{member.id}`)\nThis event alone cannot distinguish a voluntary leave from a kick or ban.", 0xD4AF37)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            await self._log(after.guild, "members", "Nickname changed", f"Member: {after.mention} (`{after.id}`)\nBefore: {before.nick or before.name}\nAfter: {after.nick or after.name}")
        before_roles = {r.id: r for r in before.roles if r.name != "@everyone"}
        after_roles = {r.id: r for r in after.roles if r.name != "@everyone"}
        added = [r.name for rid, r in after_roles.items() if rid not in before_roles]
        removed = [r.name for rid, r in before_roles.items() if rid not in after_roles]
        if added or removed:
            await self._log(after.guild, "members", "Member roles changed", f"Member: {after.mention} (`{after.id}`)\nAdded: {', '.join(added) or 'None'}\nRemoved: {', '.join(removed) or 'None'}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self._log(channel.guild, "channels", "Channel created", f"Channel: {channel.name} (`{channel.id}`)\nType: {channel.type}\nCategory: {getattr(channel.category, 'name', 'None')}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        details = f"Deleted channel: {channel.name} (`{channel.id}`)\nType: {channel.type}\nActor: unknown from this event alone; audit-log attribution may be delayed or unavailable."
        try:
            await self.bot.db.record_security_event(channel.guild.id, "channel_deleted", None, details, discord.utils.utcnow().isoformat())
        except Exception:
            log.exception("Could not store channel deletion event")
        await self._log(channel.guild, "channels", "Channel deleted", details, 0xED4245)
        await self._log(channel.guild, "security", "Channel deletion detected", details, 0xED4245)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        changes = []
        if before.name != after.name: changes.append(f"Name: {before.name} → {after.name}")
        if before.category_id != after.category_id: changes.append(f"Category: {getattr(before.category, 'name', 'None')} → {getattr(after.category, 'name', 'None')}")
        if before.overwrites != after.overwrites: changes.append("Permission overwrites changed")
        if changes:
            await self._log(after.guild, "channels", "Channel updated", f"Channel: {after.mention} (`{after.id}`)\n" + "\n".join(changes))

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self._log(role.guild, "channels", "Role created", f"Role: {role.name} (`{role.id}`)\nPermissions: `{role.permissions.value}`")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self._log(role.guild, "channels", "Role deleted", f"Role: {role.name} (`{role.id}`)", 0xED4245)
        await self._log(role.guild, "security", "Role deletion detected", f"Role: {role.name} (`{role.id}`); actor attribution not inferred from this event.", 0xED4245)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        changes = []
        if before.name != after.name: changes.append(f"Name: {before.name} → {after.name}")
        if before.permissions != after.permissions: changes.append(f"Permissions changed: `{before.permissions.value}` → `{after.permissions.value}`")
        if before.colour != after.colour: changes.append("Role colour changed")
        if changes:
            await self._log(after.guild, "channels", "Role updated", f"Role: {after.mention} (`{after.id}`)\n" + "\n".join(changes))
            if before.permissions != after.permissions:
                await self._log(after.guild, "security", "Role permissions changed", f"Role: {after.name} (`{after.id}`)\nPermissions changed: `{before.permissions.value}` → `{after.permissions.value}`", 0xD4AF37)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel and before.mute == after.mute and before.deaf == after.deaf and before.self_mute == after.self_mute and before.self_deaf == after.self_deaf and before.self_stream == after.self_stream and before.self_video == after.self_video:
            return
        old = before.channel.mention if before.channel else "Disconnected"
        new = after.channel.mention if after.channel else "Disconnected"
        await self._log(member.guild, "voice", "Voice state changed", f"Member: {member} (`{member.id}`)\nFrom: {old}\nTo: {new}\nServer mute/deaf: {after.mute}/{after.deaf}\nCamera/stream: {after.self_video}/{after.self_stream}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self._log(guild, "moderation", "Member banned", f"User: {user} (`{user.id}`)\nActor/reason may require audit-log lookup.", 0xED4245)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self._log(guild, "moderation", "Member unbanned", f"User: {user} (`{user.id}`)")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        await self._log(channel.guild, "security", "Webhook configuration changed", f"Channel: {channel.mention} (`{channel.id}`)\nDiscord reports a webhook update; identify the exact webhook/action through audit logs if available.", 0xD4AF37)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if interaction.guild:
            command_name = interaction.command.qualified_name if interaction.command else "unknown"
            await self._log(interaction.guild, "bot", "Application command error", f"Command: `/{command_name}`\nUser: {interaction.user} (`{interaction.user.id}`)\nError: `{type(error).__name__}` — {str(error)[:1200]}", 0xED4245)
        log.error("Application command error", exc_info=error)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if ctx.guild:
            await self._log(ctx.guild, "bot", "Command error", f"Command: `{ctx.command}`\nUser: {ctx.author} (`{ctx.author.id}`)\nError: `{type(error).__name__}` — {str(error)[:1200]}", 0xED4245)
        log.error("Prefix command error", exc_info=error)

async def setup(bot):
    await bot.add_cog(LoggingSystem(bot))

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import panel, success, error

log = logging.getLogger(__name__)

DEFAULT_WELCOME = "Welcome to {server}, {mention}! You are member #{member_count}."
DEFAULT_GOODBYE = "{user} has left {server}. We now have {member_count} members."


def render_member_template(template: Any, member: discord.Member) -> str:
    """Replace supported placeholders without letting unknown braces crash events."""
    guild = member.guild
    values = {
        "user": member.name,
        "display_name": member.display_name,
        "mention": member.mention,
        "server": guild.name,
        "member_count": str(guild.member_count if guild.member_count is not None else "unknown"),
        "user_id": str(member.id),
        "created_date": member.created_at.strftime("%Y-%m-%d"),
    }
    result = str(template)
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    return result[:2000]


async def send_to_configured_channel(
    bot: commands.Bot,
    guild: discord.Guild,
    setting_prefix: str,
    member: discord.Member,
    template: str,
) -> bool:
    channel_id = await bot.db.get_setting(guild.id, f"{setting_prefix}_channel_id", None)
    if not channel_id:
        return False

    try:
        channel = guild.get_channel(int(channel_id))
    except (TypeError, ValueError):
        channel = None

    if not isinstance(channel, discord.TextChannel):
        log.warning("Configured %s channel is missing or is not a text channel (guild=%s)", setting_prefix, guild.id)
        return True

    me = guild.me
    if me is None:
        log.warning("Cannot resolve the bot's guild member for %s (guild=%s)", setting_prefix, guild.id)
        return True
    permissions = channel.permissions_for(me)
    if not permissions.view_channel or not permissions.send_messages:
        log.warning("Missing channel permissions for %s (guild=%s, channel=%s)", setting_prefix, guild.id, channel.id)
        return True

    content = render_member_template(template, member)
    # A template only pings the joining/leaving member if {mention} is used.
    # Other user/role/everyone mentions remain suppressed.
    allowed = discord.AllowedMentions(
        users=[member] if "{mention}" in str(template) else [],
        roles=False,
        everyone=False,
        replied_user=False,
    )
    try:
        await channel.send(content, allowed_mentions=allowed)
    except (discord.Forbidden, discord.HTTPException):
        log.exception("Failed to send %s message (guild=%s, channel=%s)", setting_prefix, guild.id, channel.id)
    return True


class Community(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    welcome = app_commands.Group(
        name="welcome",
        description="Configure custom member welcome messages and destination channel.",
    )

    goodbye = app_commands.Group(
        name="goodbye",
        description="Configure custom member departure messages and destination channel.",
    )

    # ------------------------------- WELCOME -------------------------------
    @welcome.command(name="set-message", description="Set the welcome message sent in the configured server channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def welcome_set_message(
        self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, 1500],
    ):
        if not message.strip():
            await interaction.response.send_message(embed=error("Empty message", "Enter a welcome message."), ephemeral=True)
            return
        await self.bot.db.set_setting(interaction.guild_id, "welcome_message", message.strip())
        await interaction.response.send_message(
            embed=success("Welcome message updated", "The custom server welcome message has been saved."),
            ephemeral=True,
        )

    @welcome.command(name="set-channel", description="Choose the text channel where welcome messages are posted.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def welcome_set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None or channel.guild.id != interaction.guild.id:
            await interaction.response.send_message(embed=error("Invalid channel", "Choose a text channel in this server."), ephemeral=True)
            return
        me = interaction.guild.me
        if me is None:
            await interaction.response.send_message(embed=error("Cannot check permissions", "Try again after the bot is fully connected."), ephemeral=True)
            return
        permissions = channel.permissions_for(me)
        if not permissions.view_channel or not permissions.send_messages:
            await interaction.response.send_message(
                embed=error("Missing permissions", f"Give JARVIS View Channel and Send Messages in {channel.mention}."),
                ephemeral=True,
            )
            return
        await self.bot.db.set_setting(interaction.guild_id, "welcome_channel_id", channel.id)
        await interaction.response.send_message(
            embed=success("Welcome channel saved", f"Welcome messages will be posted in {channel.mention}."),
            ephemeral=True,
        )

    @welcome.command(name="clear-channel", description="Disable the server welcome channel and use the legacy welcome DM instead.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def welcome_clear_channel(self, interaction: discord.Interaction):
        await self.bot.db.set_setting(interaction.guild_id, "welcome_channel_id", None)
        await interaction.response.send_message(
            embed=success("Welcome channel cleared", "Server welcome posts are disabled. JARVIS will fall back to the existing welcome DM."),
            ephemeral=True,
        )

    @welcome.command(name="reset-message", description="Restore the default server welcome message.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def welcome_reset_message(self, interaction: discord.Interaction):
        await self.bot.db.set_setting(interaction.guild_id, "welcome_message", DEFAULT_WELCOME)
        await interaction.response.send_message(embed=success("Welcome message reset", f"Default template restored:\n{DEFAULT_WELCOME}"), ephemeral=True)

    @welcome.command(name="status", description="Show the current welcome channel and custom message.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def welcome_status(self, interaction: discord.Interaction):
        channel_id = await self.bot.db.get_setting(interaction.guild_id, "welcome_channel_id", None)
        template = await self.bot.db.get_setting(interaction.guild_id, "welcome_message", DEFAULT_WELCOME)
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id and interaction.guild else None
        channel_display = channel.mention if isinstance(channel, discord.TextChannel) else ("Not configured (legacy DM fallback is active)" if not channel_id else "Configured channel is missing or invalid")
        await interaction.response.send_message(
            embed=panel("Welcome Configuration", f"**Channel:** {channel_display}\n**Template:**\n```\n{str(template)[:900]}\n```\n**Placeholders:** `{{user}}`, `{{display_name}}`, `{{mention}}`, `{{server}}`, `{{member_count}}`, `{{user_id}}`, `{{created_date}}`"),
            ephemeral=True,
        )

    # ------------------------------- GOODBYE -------------------------------
    @goodbye.command(name="set-message", description="Set the custom message posted when a member leaves.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def goodbye_set_message(
        self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, 1500],
    ):
        if not message.strip():
            await interaction.response.send_message(embed=error("Empty message", "Enter a goodbye message."), ephemeral=True)
            return
        await self.bot.db.set_setting(interaction.guild_id, "goodbye_message", message.strip())
        await interaction.response.send_message(
            embed=success("Goodbye message updated", "The custom server departure message has been saved."),
            ephemeral=True,
        )

    @goodbye.command(name="set-channel", description="Choose the text channel where departure messages are posted.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def goodbye_set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None or channel.guild.id != interaction.guild.id:
            await interaction.response.send_message(embed=error("Invalid channel", "Choose a text channel in this server."), ephemeral=True)
            return
        me = interaction.guild.me
        if me is None:
            await interaction.response.send_message(embed=error("Cannot check permissions", "Try again after the bot is fully connected."), ephemeral=True)
            return
        permissions = channel.permissions_for(me)
        if not permissions.view_channel or not permissions.send_messages:
            await interaction.response.send_message(
                embed=error("Missing permissions", f"Give JARVIS View Channel and Send Messages in {channel.mention}."),
                ephemeral=True,
            )
            return
        await self.bot.db.set_setting(interaction.guild_id, "goodbye_channel_id", channel.id)
        await interaction.response.send_message(
            embed=success("Goodbye channel saved", f"Departure messages will be posted in {channel.mention}."),
            ephemeral=True,
        )

    @goodbye.command(name="clear-channel", description="Disable server departure messages.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def goodbye_clear_channel(self, interaction: discord.Interaction):
        await self.bot.db.set_setting(interaction.guild_id, "goodbye_channel_id", None)
        await interaction.response.send_message(
            embed=success("Goodbye channel cleared", "Server departure messages are now disabled."),
            ephemeral=True,
        )

    @goodbye.command(name="reset-message", description="Restore the default server departure message.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def goodbye_reset_message(self, interaction: discord.Interaction):
        await self.bot.db.set_setting(interaction.guild_id, "goodbye_message", DEFAULT_GOODBYE)
        await interaction.response.send_message(embed=success("Goodbye message reset", f"Default template restored:\n{DEFAULT_GOODBYE}"), ephemeral=True)

    @goodbye.command(name="status", description="Show the current goodbye channel and custom message.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def goodbye_status(self, interaction: discord.Interaction):
        channel_id = await self.bot.db.get_setting(interaction.guild_id, "goodbye_channel_id", None)
        template = await self.bot.db.get_setting(interaction.guild_id, "goodbye_message", DEFAULT_GOODBYE)
        channel = interaction.guild.get_channel(int(channel_id)) if channel_id and interaction.guild else None
        channel_display = channel.mention if isinstance(channel, discord.TextChannel) else ("Not configured" if not channel_id else "Configured channel is missing or invalid")
        await interaction.response.send_message(
            embed=panel("Goodbye Configuration", f"**Channel:** {channel_display}\n**Template:**\n```\n{str(template)[:900]}\n```\n**Placeholders:** `{{user}}`, `{{display_name}}`, `{{mention}}`, `{{server}}`, `{{member_count}}`, `{{user_id}}`, `{{created_date}}`"),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Server channel messages use the custom template; when no channel is set,
        # preserve the original welcome-DM behavior for existing deployments.
        configured_channel = await self.bot.db.get_setting(member.guild.id, "welcome_channel_id", None)
        if configured_channel:
            template = await self.bot.db.get_setting(member.guild.id, "welcome_message", DEFAULT_WELCOME)
            await send_to_configured_channel(self.bot, member.guild, "welcome", member, template)
            return

        legacy_template = await self.bot.db.get_setting(
            member.guild.id,
            "welcome_template",
            "Welcome to {server}, {user}! You are member #{member_count}.",
        )
        message = render_member_template(legacy_template, member)
        try:
            await member.send(embed=panel("Welcome", message))
            status = "sent"
        except (discord.Forbidden, discord.HTTPException):
            status = "failed"
        try:
            await self.bot.db.set_setting(member.guild.id, f"welcome_delivery:{member.id}", status)
        except Exception:
            log.exception("Could not store welcome delivery status")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel_id = await self.bot.db.get_setting(member.guild.id, "goodbye_channel_id", None)
        if not channel_id:
            return
        template = await self.bot.db.get_setting(member.guild.id, "goodbye_message", DEFAULT_GOODBYE)
        await send_to_configured_channel(self.bot, member.guild, "goodbye", member, template)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        # Message content intent is optional and disabled by default; XP is intentionally
        # not awarded here until a server has opted in via a future configuration command.


async def setup(bot):
    await bot.add_cog(Community(bot))

from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import success, error, panel

log = logging.getLogger(__name__)

class ChannelValueModal(discord.ui.Modal):
    def __init__(self, view: "JTCControlPanel", setting: str):
        self.control_view, self.setting = view, setting
        titles = {"rename": "Rename your voice channel", "limit": "Set member limit", "bitrate": "Set audio bitrate"}
        labels = {"rename": "Channel name", "limit": "Limit (0 = unlimited)", "bitrate": "Bitrate in kbps"}
        super().__init__(title=titles[setting], timeout=180)
        self.value = discord.ui.TextInput(label=labels[setting], placeholder={"rename": "My private room", "limit": "0", "bitrate": "64"}[setting], max_length=100 if setting == "rename" else 5)
        self.add_item(self.value)

    async def on_submit(self, interaction: discord.Interaction):
        if not await self.control_view.authorized(interaction): return
        channel = self.control_view.channel
        try:
            if self.setting == "rename":
                value = str(self.value.value).strip()
                if not value:
                    await interaction.response.send_message(embed=error("Invalid name", "Enter a channel name."), ephemeral=True); return
                await channel.edit(name=value[:100], reason=f"JTC owner control by {interaction.user.id}")
                message = f"Channel renamed to **{value[:100]}**."
            elif self.setting == "limit":
                limit = int(str(self.value.value).strip())
                if not 0 <= limit <= 99: raise ValueError
                await channel.edit(user_limit=limit, reason=f"JTC owner control by {interaction.user.id}")
                message = "Member limit removed." if limit == 0 else f"Member limit set to **{limit}**."
            else:
                bitrate = int(str(self.value.value).strip()) * 1000
                if not 8000 <= bitrate <= channel.guild.bitrate_limit:
                    await interaction.response.send_message(embed=error("Invalid bitrate", f"Choose between 8 and {channel.guild.bitrate_limit // 1000} kbps for this server."), ephemeral=True); return
                await channel.edit(bitrate=bitrate, reason=f"JTC owner control by {interaction.user.id}")
                message = f"Bitrate set to **{bitrate // 1000} kbps**."
        except ValueError:
            await interaction.response.send_message(embed=error("Invalid value", "Enter a valid number within the allowed range."), ephemeral=True); return
        except discord.Forbidden:
            await interaction.response.send_message(embed=error("Missing permissions", "I need Manage Channels permission to change this setting."), ephemeral=True); return
        except discord.HTTPException:
            log.exception("JTC setting update failed")
            await interaction.response.send_message(embed=error("Update failed", "Discord could not apply that setting."), ephemeral=True); return
        await interaction.response.send_message(embed=success("Channel updated", message), ephemeral=True)

class JTCControlPanel(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=None)
        self.bot, self.channel, self.owner_id = bot, channel, owner_id
        self.add_item(self.SettingsSelect(self)); self.add_item(self.PermissionsSelect(self))

    async def authorized(self, interaction: discord.Interaction) -> bool:
        admin = isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_channels
        if interaction.user.id != self.owner_id and not admin:
            await interaction.response.send_message(embed=error("Room owner only", "Only the room owner or a moderator with Manage Channels can use these controls."), ephemeral=True); return False
        if interaction.guild is None or interaction.guild.id != self.channel.guild.id:
            await interaction.response.send_message("This panel is only available in its original server.", ephemeral=True); return False
        return True

    def make_embed(self) -> discord.Embed:
        embed = panel("⚙ Temporary Channel Controls Interface", "Control your channel using the menus below.\n• Use the dropdowns to manage settings and permissions\n• Only the room owner or server moderators can use these controls\n• This panel is posted in your created voice channel's chat")
        embed.add_field(name="Channel Settings", value="Rename the room, set a member limit, or change audio bitrate.", inline=False)
        embed.add_field(name="Channel Permissions", value="Lock/unlock the room, hide/show it, or manage a member's access.", inline=False)
        embed.set_footer(text="Temporary Voice Room • Permission-checked controls")
        return embed

    class SettingsSelect(discord.ui.Select):
        def __init__(self, parent: "JTCControlPanel"):
            self.parent_view = parent
            super().__init__(placeholder="Change channel settings", min_values=1, max_values=1, options=[
                discord.SelectOption(label="Rename channel", value="rename", description="Change this room's name", emoji="✏️"),
                discord.SelectOption(label="Member limit", value="limit", description="Set 0–99 members; 0 means unlimited", emoji="👥"),
                discord.SelectOption(label="Audio bitrate", value="bitrate", description="Change voice audio quality", emoji="🎚️")])
        async def callback(self, interaction: discord.Interaction):
            if await self.parent_view.authorized(interaction): await interaction.response.send_modal(ChannelValueModal(self.parent_view, self.values[0]))

    class PermissionsSelect(discord.ui.Select):
        def __init__(self, parent: "JTCControlPanel"):
            self.parent_view = parent
            super().__init__(placeholder="Change channel permissions", min_values=1, max_values=1, options=[
                discord.SelectOption(label="Lock room", value="lock", description="Prevent everyone else connecting", emoji="🔒"),
                discord.SelectOption(label="Unlock room", value="unlock", description="Allow everyone to connect", emoji="🔓"),
                discord.SelectOption(label="Hide room", value="hide", description="Hide this room from @everyone", emoji="🙈"),
                discord.SelectOption(label="Show room", value="show", description="Make this room visible to @everyone", emoji="👁️")])
        async def callback(self, interaction: discord.Interaction):
            parent = self.parent_view
            if not await parent.authorized(interaction): return
            action = self.values[0]; role = interaction.guild.default_role
            overwrite = parent.channel.overwrites_for(role)
            if action == "lock": overwrite.connect = False
            elif action == "unlock": overwrite.connect = None
            elif action == "hide": overwrite.view_channel = False
            elif action == "show": overwrite.view_channel = None
            try: await parent.channel.set_permissions(role, overwrite=overwrite, reason=f"JTC room control by {interaction.user.id}")
            except discord.Forbidden:
                await interaction.response.send_message(embed=error("Missing permissions", "I need Manage Channels permission to update room permissions."), ephemeral=True); return
            except discord.HTTPException:
                await interaction.response.send_message(embed=error("Permission update failed", "Discord rejected the permission change."), ephemeral=True); return
            labels = {"lock": "locked", "unlock": "unlocked", "hide": "hidden", "show": "visible"}
            await interaction.response.send_message(embed=success("Room permissions updated", f"The room is now **{labels[action]}** for @everyone."), ephemeral=True)

    @discord.ui.button(label="Refresh panel", style=discord.ButtonStyle.primary, emoji="⚙️", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.authorized(interaction): await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Delete room", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def delete_room(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.authorized(interaction): return
        await interaction.response.send_message("Are you sure you want to delete this temporary room?", view=DeleteRoomConfirm(self), ephemeral=True)

class DeleteRoomConfirm(discord.ui.View):
    def __init__(self, parent: JTCControlPanel): super().__init__(timeout=30); self.parent = parent
    @discord.ui.button(label="Confirm delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.parent.authorized(interaction): return
        channel = self.parent.channel
        await interaction.response.send_message("Deleting the temporary voice room…", ephemeral=True)
        try:
            await channel.delete(reason=f"Temporary room deleted by {interaction.user.id}")
            await self.parent.bot.db._db().execute("DELETE FROM jtc_channels WHERE channel_id=?", (channel.id,)); await self.parent.bot.db._db().commit()
        except discord.HTTPException: log.exception("Could not delete JTC channel %s", channel.id)
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button): await interaction.response.edit_message(content="Cancelled.", view=None)

class Voice(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="jtc-setup", description="Configure the Join-to-Create generator voice channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    async def jtc_setup(self, interaction: discord.Interaction, generator: discord.VoiceChannel, category: discord.CategoryChannel):
        await self.bot.db.set_setting(interaction.guild_id, "jtc_generator_id", generator.id)
        await self.bot.db.set_setting(interaction.guild_id, "jtc_category_id", category.id)
        await interaction.response.send_message(embed=success("Join-to-Create configured", f"Generator: {generator.mention}\nCategory: {category.name}"), ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or after.channel is None or before.channel == after.channel: return
        generator_id = await self.bot.db.get_setting(member.guild.id, "jtc_generator_id", None)
        category_id = await self.bot.db.get_setting(member.guild.id, "jtc_category_id", None)
        if not generator_id or after.channel.id != int(generator_id): return
        category = member.guild.get_channel(int(category_id)) if category_id else None
        if not isinstance(category, discord.CategoryChannel): return
        try:
            created = await member.guild.create_voice_channel(name=f"{member.display_name}'s room"[:100], category=category, reason="Join-to-Create temporary room")
            await self.bot.db._db().execute("INSERT OR REPLACE INTO jtc_channels(channel_id,guild_id,owner_id,created_at) VALUES(?,?,?,?)", (created.id, member.guild.id, member.id, discord.utils.utcnow().isoformat()))
            await self.bot.db._db().commit()
            await member.move_to(created, reason="Join-to-Create temporary room")
            view = JTCControlPanel(self.bot, created, member.id)
            # Post the controls into the newly created voice channel's chat.
            await created.send(embed=view.make_embed(), view=view)
        except (discord.Forbidden, discord.HTTPException, AttributeError): log.exception("Join-to-Create or control panel delivery failed for member %s", member.id)

    @app_commands.command(name="jtc-status", description="Show Join-to-Create configuration.")
    @app_commands.guild_only()
    async def jtc_status(self, interaction: discord.Interaction):
        generator_id = await self.bot.db.get_setting(interaction.guild_id, "jtc_generator_id", None)
        category_id = await self.bot.db.get_setting(interaction.guild_id, "jtc_category_id", None)
        await interaction.response.send_message(embed=panel("Join-to-Create Status", f"Generator: {f'<#{generator_id}>' if generator_id else 'Not configured'}\nCategory: {f'<#{category_id}>' if category_id else 'Not configured'}"), ephemeral=True)

async def setup(bot): await bot.add_cog(Voice(bot))

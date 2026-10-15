from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import panel, success, error

HELP_CATEGORIES = {
    "Home Overview": {
        "description": "Main dashboard, bot status & how to use the command directory",
        "command_names": {"help", "jarvis"},
        "features": ["/help — open this interactive category menu", "/jarvis — view uptime, gateway latency and process status"],
        "status": "available",
    },
    "Help Configuration": {
        "description": "Customize the creator name and introductory text shown in /help",
        "command_names": {"help_config_creator", "help_config_introduction", "help_config_show"},
        "features": ["These settings customize the help panel only; they do not rename the Discord bot account."],
        "status": "available",
    },
    "Anti-Nuke & Incident Response": {
        "description": "High-risk event detection, threshold responses and incident review",
        "command_names": {
            "anti-nuke enable", "anti-nuke status", "anti-nuke threshold", "anti-nuke response-mode",
            "anti-nuke incidents", "anti-nuke events", "anti-nuke resolve",
        },
        "features": ["Default response is alert-only; kicking is optional and may fail due to permissions or role hierarchy.", "Audit-log actor matching is best-effort; Discord events cannot be guaranteed to be blocked before they occur."],
        "status": "partial",
    },
    "Bot Guard & Approved Bots": {
        "description": "Watch bot joins, approve trusted bot IDs and review unapproved bots",
        "command_names": {
            "bot-guard status", "bot-guard enable", "bot-guard mode", "bot-guard allow",
            "bot-guard remove", "bot-guard list", "bot-guard scan",
        },
        "features": ["/bot-guard scan is read-only.", "Alert-only is the safer default; auto-kick depends on Discord permissions and audit-log attribution."],
        "status": "partial",
    },
    "Admin Delegation & Access": {
        "description": "Trusted-user lists, delegated-admin records and security permission audits",
        "command_names": {
            "security whitelist-add", "security whitelist-remove", "security whitelist-list",
            "security delegate-add", "security delegate-remove", "security delegate-list",
            "security health", "security permission-audit",
        },
        "features": ["Whitelist entries are consulted by supported security responses.", "Delegate commands store and display the delegated list; this does not itself grant Discord permissions or automatically authorize every command."],
        "status": "partial",
    },
    "Server Security & Lockdown": {
        "description": "Security settings, event review and reversible send-message lockdown",
        "command_names": {
            "security status", "security threshold", "security protection", "security events",
            "security lockdown", "security unlock", "security panic-lockdown", "security panic-unlock",
        },
        "features": ["Panic lockdown saves the previous @everyone Send Messages values before changing them.", "Panic unlock restores saved values where the channels still exist; review the result after use."],
        "status": "partial",
    },
    "Moderation & Sanctions": {
        "description": "Member kick, ban, timeout, warning and recent case history",
        "command_names": {"ban", "kick", "timeout", "untimeout", "warn", "warnings"},
        "features": ["Actions are recorded when supported; DMs to affected users may fail.", "An /unban command and advanced appeals workflow are not implemented in this build."],
        "status": "partial",
    },
    "Message Cleanup": {
        "description": "Bulk message purges, clearv2 and snipe tools",
        "command_names": set(),
        "features": ["Bulk purge, clearv2 and snipe commands are not implemented in this build."],
        "status": "planned",
    },
    "Role Management": {
        "description": "Role editor, temporary roles and mass role actions",
        "command_names": set(),
        "features": ["Role editor, temporary-role scheduler and mass role actions are not implemented in this build."],
        "status": "planned",
    },
    "AutoRole & Vanity Status": {
        "description": "Automatic join roles and vanity status rewards",
        "command_names": set(),
        "features": ["Join autoroles and vanity rewards are not implemented in this build."],
        "status": "planned",
    },
    "Custom Moderations": {
        "description": "Custom moderation-role mappings and command access policies",
        "command_names": set(),
        "features": ["Custom role-to-command permission mappings are not implemented. Use Discord command permissions and the checks currently built into each command."],
        "status": "planned",
    },
    "Rogue Bot & Protection": {
        "description": "Advanced rogue-bot telemetry beyond the Bot Guard admission scanner",
        "command_names": set(),
        "features": ["Basic bot allowlisting and scanning are available under Bot Guard & Approved Bots.", "Additional rogue-bot behavior analytics and automatic containment are not implemented in this build."],
        "status": "planned",
    },
    "Quarantine Isolation": {
        "description": "Isolate disruptive members and track evasion",
        "command_names": set(),
        "features": ["Full quarantine workflow and evasion tracking are not implemented in this build."],
        "status": "planned",
    },
    "Ignore System & Filters": {
        "description": "Channel, role, user and category ignore rules",
        "command_names": set(),
        "features": ["Configurable command ignore lists and filters are not implemented in this build."],
        "status": "planned",
    },
    "Verification & Captcha": {
        "description": "Button verification, captcha and challenge flows",
        "command_names": set(),
        "features": ["Verification panels, captcha challenges and verification-role automation are not implemented in this build."],
        "status": "planned",
    },
    "Automods & Word Filters": {
        "description": "Spam, link, keyword and native AutoMod rules",
        "command_names": set(),
        "features": ["Advanced spam rules, custom word/link filters and native AutoMod management commands are not implemented in this build."],
        "status": "planned",
    },
    "Auto Responder System": {
        "description": "Custom keyword triggers and automated chat responses",
        "command_names": set(),
        "features": ["Configurable keyword triggers and auto-replies are not implemented in this build."],
        "status": "planned",
    },
    "Auto-React System": {
        "description": "Channel and keyword based automatic reactions",
        "command_names": set(),
        "features": ["Configurable keyword/channel auto-reactions are not implemented in this build."],
        "status": "planned",
    },
    "Automated Logging": {
        "description": "Private log channels for moderation, messages, members, channels, voice and security",
        "command_names": {"setup-logs", "set-log-channel"},
        "features": ["/setup-logs creates or verifies seven private log channels.", "/set-log-channel routes a category to a selected text channel.", "Event details depend on Discord intents, supplied event data and permissions."],
        "status": "partial",
    },
    "Welcome & Goodbye Messages": {
        "description": "Custom server welcome/departure messages, destination channels and template placeholders",
        "command_names": {
            "welcome set-message", "welcome set-channel", "welcome clear-channel",
            "welcome reset-message", "welcome status",
            "goodbye set-message", "goodbye set-channel", "goodbye clear-channel",
            "goodbye reset-message", "goodbye status",
        },
        "features": [
            "/welcome set-message and /goodbye set-message configure custom server messages.",
            "Set a destination with /welcome set-channel or /goodbye set-channel.",
            "Supported placeholders: {user}, {display_name}, {mention}, {server}, {member_count}, {user_id}, {created_date}.",
            "When no welcome channel is configured, the legacy welcome DM remains active. Goodbye messages require a configured channel.",
            "Custom messages are plain Discord message content; image cards and GIF rendering are not included.",
        ],
        "status": "available",
    },
    "Server Bumper (Dashboard)": {
        "description": "Bump reminders, timers and server bump leaderboards",
        "command_names": set(),
        "features": ["Bump reminders, timers and leaderboards are not implemented in this build."],
        "status": "planned",
    },
    "Voice & Join-to-Create": {
        "description": "Temporary voice rooms and in-room controls",
        "command_names": {"jtc-setup", "jtc-status"},
        "features": ["Joining the configured generator can create a temporary room and move the member into it.", "Available in-room controls depend on room ownership, Discord permissions and the current implementation."],
        "status": "partial",
    },
    "Backups & Recovery": {
        "description": "Create, list and inspect supported server-structure snapshots",
        "command_names": {"backup create", "backup list", "backup inspect"},
        "features": ["Snapshots cover selected server structure only.", "Automatic restore, complete permission-overwrite recovery and message-history restoration are not implemented."],
        "status": "partial",
    },
    "Performance & Diagnostics": {
        "description": "Gateway latency and interaction acknowledgement diagnostics",
        "command_names": {"ping"},
        "features": ["Gateway latency is not the same as end-to-end command completion time.", "The bot cannot guarantee a fixed response time such as 20 ms."],
        "status": "available",
    },
}

def _flatten_app_command(command, prefix=""):
    """Return every registered application command, including nested subcommands."""
    qualified = f"{prefix} {command.name}".strip()
    children = getattr(command, "commands", None)
    if children:
        for child in children:
            yield from _flatten_app_command(child, qualified)
    else:
        yield qualified, getattr(command, "description", "No description available.")


async def build_help_embed(bot, guild_id=None, category="Home Overview"):
    creator = bot.settings.creator_name
    introduction = "A modular Discord security and moderation assistant. Select a category below to browse commands and module status."
    if guild_id is not None and getattr(bot, "db", None):
        try:
            creator = await bot.db.get_setting(guild_id, "help_creator", creator)
            introduction = await bot.db.get_setting(guild_id, "help_introduction", introduction)
        except Exception:
            pass

    info = HELP_CATEGORIES.get(category, HELP_CATEGORIES["Home Overview"])
    embed = panel("⌘  Control Center  •  Command Directory", introduction[:1000], color=0x9D4EDD)
    embed.add_field(name=f"{category}", value=info["description"], inline=False)
    status = info["status"]
    status_label = {"available": "Available", "partial": "Partially available", "planned": "Not implemented yet"}.get(status, status)
    embed.add_field(name="Module status", value=status_label, inline=True)

    registered = []
    for root in bot.tree.get_commands():
        for command_name, description in _flatten_app_command(root):
            registered.append((command_name, description))
    matches = [(name, desc) for name, desc in registered if name in info["command_names"]]
    command_lines = [f"`/{name}` — {desc}" for name, desc in matches]
    feature_lines = list(info["features"])
    if command_lines:
        # Discord embed fields are capped at 1024 characters. Split long command
        # catalogs rather than silently truncating the security command list.
        chunks = []
        current = []
        current_len = 0
        for line in command_lines:
            needed = len(line) + (1 if current else 0)
            if current and current_len + needed > 950:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
                needed = len(line)
            current.append(line)
            current_len += needed
        if current:
            chunks.append("\n".join(current))
        for index, chunk in enumerate(chunks):
            label = "Registered commands" if index == 0 else f"Registered commands (continued {index + 1})"
            embed.add_field(name=label, value=chunk, inline=False)
    elif info["command_names"]:
        embed.add_field(name="Registered commands", value="Expected commands are not currently registered. Check extension-loading and command-sync logs.", inline=False)
    else:
        embed.add_field(name="Registered commands", value="No active slash commands in this category yet.", inline=False)
    embed.add_field(name="Features", value="\n".join(f"• {line}" for line in feature_lines)[:1000], inline=False)
    embed.set_footer(text=f"Creator: {creator} • Use / to invoke commands • Feature status is shown honestly")
    return embed


class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name[:100], description=info["description"][:100], value=name) for name, info in list(HELP_CATEGORIES.items())[:25]]
        super().__init__(placeholder="Choose a system category…", min_values=1, max_values=1, options=options, custom_id="help:category")

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        view.category = self.values[0]
        embed = await build_help_embed(interaction.client, interaction.guild_id, view.category)
        await interaction.response.edit_message(embed=embed, view=view)


class HelpView(discord.ui.View):
    def __init__(self, owner_id: int, category: str = "Home Overview"):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.category = category
        self.add_item(HelpCategorySelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This help panel belongs to another user.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Home", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.category = "Home Overview"
        self.children[0].placeholder = "Choose a system category…"
        await interaction.response.edit_message(embed=await build_help_embed(interaction.client, interaction.guild_id, self.category), view=self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=await build_help_embed(interaction.client, interaction.guild_id, self.category), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Help panel closed.", embed=None, view=None)

class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Open the interactive categorized control center.")
    async def help_command(self, interaction: discord.Interaction):
        embed = await build_help_embed(self.bot, interaction.guild_id, "Home Overview")
        await interaction.response.send_message(embed=embed, view=HelpView(interaction.user.id), ephemeral=True)

    @app_commands.command(name="jarvis", description="Show the JARVIS operational dashboard.")
    @app_commands.guild_only()
    async def dashboard(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        uptime = discord.utils.utcnow() - self.bot.started_at
        embed = panel("JARVIS Operations Dashboard", color=0x9D4EDD)
        embed.add_field(name="Status", value="Online", inline=True)
        embed.add_field(name="Gateway latency", value=f"{self.bot.latency * 1000:.0f} ms", inline=True)
        embed.add_field(name="Uptime", value=str(uptime).split(".")[0], inline=True)
        embed.add_field(name="Server", value=f"{guild.name}\n`{guild.id}`", inline=True)
        embed.add_field(name="Database", value="Connected" if self.bot.db.conn else "Not initialized", inline=True)
        embed.add_field(name="Command sync", value="Automatic on startup" if self.bot.settings.sync_commands_on_start else "Manual", inline=True)
        embed.set_footer(text=f"Creator: {self.bot.settings.creator_name} • Values reflect current process state")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="help_config_creator", description="Set the displayed JARVIS creator name.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def help_config_creator(self, interaction: discord.Interaction, creator: str):
        await self.bot.db.set_setting(interaction.guild_id, "help_creator", creator[:100])
        await interaction.response.send_message(embed=success("Creator updated", "The configured creator name has been saved."), ephemeral=True)

    @app_commands.command(name="help_config_introduction", description="Set the help introduction.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def help_config_introduction(self, interaction: discord.Interaction, introduction: str):
        await self.bot.db.set_setting(interaction.guild_id, "help_introduction", introduction[:1000])
        await interaction.response.send_message(embed=success("Introduction updated", "The help introduction has been saved."), ephemeral=True)

    @app_commands.command(name="help_config_show", description="Show the configured help creator and introduction.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def help_config_show(self, interaction: discord.Interaction):
        creator = await self.bot.db.get_setting(interaction.guild_id, "help_creator", self.bot.settings.creator_name)
        intro = await self.bot.db.get_setting(interaction.guild_id, "help_introduction", "JARVIS Ultimate server security assistant.")
        await interaction.response.send_message(embed=panel("Help Configuration", f"**Creator:** {creator}\n**Introduction:** {intro}"), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Core(bot))

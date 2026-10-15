import discord
from discord import app_commands

def guild_only():
    return app_commands.guild_only()

def has_guild_permissions(**perms: bool):
    return app_commands.checks.has_permissions(**perms)

async def ensure_bot_permissions(interaction: discord.Interaction, **perms: bool) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    me = interaction.guild.me
    if me is None:
        return False
    return all(getattr(me.guild_permissions, name, False) for name, needed in perms.items() if needed)

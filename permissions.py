from __future__ import annotations
import discord

class PermissionService:
    """Shared permission and hierarchy checks for privileged operations."""

    @staticmethod
    def can_moderate(actor: discord.Member, target: discord.Member, bot_member: discord.Member,
                     *, require: str) -> tuple[bool, str]:
        if not getattr(actor.guild_permissions, require, False):
            return False, f"You need the `{require}` permission."
        if target.id == actor.id:
            return False, "You cannot target yourself with this action."
        if target.id == actor.guild.owner_id:
            return False, "The server owner cannot be targeted by this command."
        if actor.id != actor.guild.owner_id and target.top_role >= actor.top_role:
            return False, "Your top role must be higher than the target's top role."
        if target.top_role >= bot_member.top_role:
            return False, "JARVIS's top role must be higher than the target's top role."
        return True, ""

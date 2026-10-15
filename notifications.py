from __future__ import annotations
import logging
import discord

log = logging.getLogger(__name__)

async def notify_owner(guild: discord.Guild, embed: discord.Embed) -> bool:
    """Try owner DM; return actual delivery success and never assume DMs are available."""
    try:
        owner = guild.owner or await guild.fetch_member(guild.owner_id)
        await owner.send(embed=embed)
        return True
    except (discord.HTTPException, discord.Forbidden, discord.NotFound):
        log.warning("Could not DM guild owner for guild %s", guild.id)
        return False

async def notify_member(member: discord.abc.User, embed: discord.Embed) -> bool:
    try:
        await member.send(embed=embed)
        return True
    except (discord.HTTPException, discord.Forbidden, discord.NotFound):
        return False

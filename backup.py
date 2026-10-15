from __future__ import annotations
import json
import discord
from discord import app_commands
from discord.ext import commands
from utils.embeds import panel, success, error, warning

class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    backup = app_commands.Group(name="backup", description="Create and inspect supported server-structure snapshots.")

    @backup.command(name="create", description="Create a database snapshot of supported server structure.")
    @app_commands.default_permissions(administrator=True)
    async def create(self, interaction: discord.Interaction, name: str = "manual"):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True); return
        payload = {
            "schema": 1,
            "guild_id": guild.id,
            "guild_name": guild.name,
            "created_at": discord.utils.utcnow().isoformat(),
            "roles": [
                {"id": r.id, "name": r.name, "permissions": r.permissions.value,
                 "colour": r.colour.value, "hoist": r.hoist, "mentionable": r.mentionable,
                 "position": r.position}
                for r in guild.roles if not r.is_default() and not r.managed
            ],
            "categories": [
                {"id": c.id, "name": c.name, "position": c.position}
                for c in guild.categories
            ],
            "channels": [
                {"id": c.id, "name": c.name, "type": str(c.type),
                 "position": c.position, "category_id": c.category_id,
                 "topic": getattr(c, "topic", None),
                 "nsfw": getattr(c, "nsfw", False)}
                for c in guild.channels if not isinstance(c, discord.CategoryChannel)
            ],
            "note": "Snapshot records supported structure only. This initial build does not implement destructive restore.",
        }
        encoded = json.dumps(payload, ensure_ascii=False)
        cur = await self.bot.db._db().execute(
            "INSERT INTO backups(guild_id,name,created_at,payload) VALUES(?,?,?,?)",
            (guild.id, name[:80], payload["created_at"], encoded),
        )
        await self.bot.db._db().commit()
        await interaction.response.send_message(embed=success("Backup created",
            f"Backup ID: `{cur.lastrowid}`\nRoles: {len(payload['roles'])}\nCategories: {len(payload['categories'])}\nChannels: {len(payload['channels'])}\nThis is a structural snapshot; restoration is not yet enabled."), ephemeral=True)

    @backup.command(name="list", description="List recent backups.")
    @app_commands.default_permissions(administrator=True)
    async def list_backups(self, interaction: discord.Interaction):
        async with self.bot.db._db().execute(
            "SELECT id,name,created_at FROM backups WHERE guild_id=? ORDER BY id DESC LIMIT 10",
            (interaction.guild_id,),
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message(embed=panel("Backups", "No backups found."), ephemeral=True); return
        embed = panel("Recent Backups")
        for row in rows:
            embed.add_field(name=f"#{row['id']} • {row['name']}", value=row["created_at"], inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @backup.command(name="inspect", description="Inspect a backup by its ID.")
    @app_commands.default_permissions(administrator=True)
    async def inspect(self, interaction: discord.Interaction, backup_id: int):
        async with self.bot.db._db().execute(
            "SELECT name,created_at,payload FROM backups WHERE guild_id=? AND id=?",
            (interaction.guild_id, backup_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            await interaction.response.send_message(embed=error("Backup not found", "No backup with that ID exists in this server."), ephemeral=True); return
        payload = json.loads(row["payload"])
        await interaction.response.send_message(embed=panel(
            f"Backup #{backup_id} • {row['name']}",
            f"Created: {row['created_at']}\nRoles: {len(payload.get('roles', []))}\n"
            f"Categories: {len(payload.get('categories', []))}\nChannels: {len(payload.get('channels', []))}\n"
            "Restore is intentionally not implemented in this initial build; no destructive action was performed."
        ), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Backup(bot))

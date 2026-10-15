from __future__ import annotations

import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import Settings
from database import Database

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("jarvis")

EXTENSIONS = (
    "cogs.core",
    "cogs.moderation",
    "cogs.security",
    "cogs.anti_nuke",
    "cogs.bot_guard",
    "cogs.logging_system",
    "cogs.community",
    "cogs.voice",
    "cogs.backup",
    "cogs.performance",
)

class JarvisBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.members = True
        intents.voice_states = True
        intents.guilds = True
        intents.message_content = settings.message_content_intent
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.settings = settings
        self.db = Database(settings.database_path)
        self.started_at = discord.utils.utcnow()

    async def setup_hook(self) -> None:
        await self.db.initialize()
        for extension in EXTENSIONS:
            await self.load_extension(extension)
            log.info("Loaded extension %s", extension)
        if self.settings.sync_commands_on_start:
            synced = await self.tree.sync()
            log.info("Synced %d application commands", len(synced))

    async def close(self) -> None:
        try:
            await self.db.close()
        finally:
            await super().close()

    async def on_ready(self) -> None:
        if self.user:
            log.info("Logged in as %s (%s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="server security | /help",
            )
        )

def main() -> None:
    settings = Settings.from_env()
    if not settings.discord_token:
        raise SystemExit("Missing DISCORD_TOKEN. Copy .env.example to .env and configure it.")
    JarvisBot(settings).run(settings.discord_token, log_handler=None)

if __name__ == "__main__":
    main()

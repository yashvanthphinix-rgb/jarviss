from __future__ import annotations

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import panel

log = logging.getLogger("jarvis.performance")


class Performance(commands.Cog):
    """Lightweight latency diagnostics; does not promise a fixed network RTT."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Measure JARVIS gateway and interaction acknowledgement latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        started = time.perf_counter()
        # Defer immediately to acknowledge the interaction before doing extra work.
        await interaction.response.defer(ephemeral=True, thinking=True)
        ack_ms = (time.perf_counter() - started) * 1000
        gateway_ms = self.bot.latency * 1000

        embed = panel("JARVIS | Latency Diagnostics",
                      "These measurements are different; neither guarantees the total time for a moderation action.",
                      color=0x9D4EDD)
        embed.add_field(name="Gateway heartbeat", value=f"`{gateway_ms:.1f} ms`", inline=True)
        embed.add_field(name="Initial interaction ACK", value=f"`{ack_ms:.1f} ms`", inline=True)
        embed.add_field(name="Target", value="`~80 ms` goal; network/API latency is outside the bot's control", inline=False)
        embed.set_footer(text="Compare several runs; a single reading can fluctuate.")

        followup_started = time.perf_counter()
        await interaction.followup.send(embed=embed, ephemeral=True)
        followup_ms = (time.perf_counter() - followup_started) * 1000
        log.info("/ping guild=%s gateway_ms=%.1f ack_ms=%.1f followup_http_ms=%.1f",
                 interaction.guild_id, gateway_ms, ack_ms, followup_ms)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Performance(bot))

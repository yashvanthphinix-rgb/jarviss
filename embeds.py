import discord

BLACK = 0x1C1C1E
LAVENDER = 0x9D4EDD
GOLD = 0xD4AF37
WHITE = 0xF8F9FA

def panel(title: str, description: str = "", *, color: int = LAVENDER) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
    embed.set_footer(text="Security Operations")
    return embed

def success(title: str, description: str = "") -> discord.Embed:
    return panel(title, description, color=0x3BA55D)

def warning(title: str, description: str = "") -> discord.Embed:
    return panel(title, description, color=GOLD)

def error(title: str, description: str = "") -> discord.Embed:
    return panel(title, description, color=0xED4245)

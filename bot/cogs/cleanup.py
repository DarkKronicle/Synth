from discord.ext import commands


class Cleanup(commands.Cog):
    """Clean's up old unused data."""

    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(Cleanup(bot))

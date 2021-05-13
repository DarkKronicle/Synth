from discord.ext import commands

from bot import synth_bot


class Owner(commands.Cog):

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot
        self.degrees = 0

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)


def setup(bot):
    bot.add_cog(Owner(bot))

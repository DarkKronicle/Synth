from discord.ext import commands


class Utility(commands.Cog):

    @commands.command(name="ping")
    async def ping(self, ctx):
        time0 = ctx.message.created_at
        sent = await ctx.send("Pinging")
        time1 = sent.created_at
        dif1 = round((time1 - time0).total_seconds() * 1000)
        await sent.edit(content=f"Pong! Pinging time was {dif1}ms")


def setup(bot):
    bot.add_cog(Utility())

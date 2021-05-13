import typing
from datetime import datetime

from dateutil.tz import gettz
from discord.ext import commands

from bot.util.context import Context
import bot.util.time_util as tutil


class ZoneConverter(commands.Converter):

    async def convert(self, ctx, argument):
        if len(argument) == 0:
            raise commands.BadArgument("Invalid time zone!")
        zone = gettz(argument)
        if zone is None:
            raise commands.BadArgument("Invalid time zone!")
        return zone


class Utility(commands.Cog):

    UTC = gettz('UTC')

    @commands.command(name="ping")
    async def ping(self, ctx):
        time0 = ctx.message.created_at
        sent = await ctx.send("Pinging")
        time1 = sent.created_at
        dif1 = round((time1 - time0).total_seconds() * 1000)
        await sent.edit(content=f"Pong! Pinging time was {dif1}ms")

    @commands.command(name="zoneconverter", aliases=["zone2zone", "z2z"])
    async def time_convert(self, ctx: Context, from_zone: typing.Optional[ZoneConverter],
                           to_zone: ZoneConverter = None):
        # Fixing converter optionals
        if to_zone is None:
            to_zone = from_zone
            from_zone = None
        if from_zone is None:
            from_zone = self.UTC
        f = datetime.now(from_zone)
        t = f.astimezone(to_zone)
        f_form = f.strftime("%H:%M:%S %z")
        t_form = t.strftime("%H:%M:%S %z")
        await ctx.send(embed=ctx.create_embed(description=f"From:\n `{f_form}`\n\nTo:\n `{t_form}`", title=f"{f.tzname()} -> {t.tzname()}"))


def setup(bot):
    bot.add_cog(Utility())

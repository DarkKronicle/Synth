import typing
from datetime import datetime

import discord
from bot.util.context import Context
from dateutil.tz import gettz
from discord.ext import commands


class ZoneConverter(commands.Converter):

    async def convert(self, ctx, argument):
        if len(argument) == 0:
            raise commands.BadArgument('Invalid time zone!')
        zone = gettz(argument)
        if zone is None:
            raise commands.BadArgument('Invalid time zone!')
        return zone


class Utility(commands.Cog):
    """Miscellaneous utility commands."""

    UTC = gettz('UTC')

    @commands.command(name='ping')
    async def ping(self, ctx):
        """
        Pings the bot and gets the millisecond delay.
        """
        time0 = ctx.message.created_at
        sent = await ctx.send('Pinging')
        time1 = sent.created_at
        dif1 = round((time1 - time0).total_seconds() * 1000)
        await sent.edit(content=f'Pong! Pinging time was {dif1}ms')

    @commands.command(name='zoneconverter', aliases=['zone2zone', 'z2z'])
    async def time_convert(self, ctx: Context, from_zone: typing.Optional[ZoneConverter],
                           to_zone: ZoneConverter = None):
        """
        Converts one time zone to another time zone. Default [from_zone] is UTC.

        Examples:
              z2z EST
              z2z EST MST
        """
        # Fixing converter optionals
        if to_zone is None:
            to_zone = from_zone
            from_zone = None
        if from_zone is None:
            from_zone = self.UTC
        f = datetime.now(from_zone)
        t = f.astimezone(to_zone)
        f_form = f.strftime('%H:%M:%S %z')
        t_form = t.strftime('%H:%M:%S %z')
        await ctx.send(embed=ctx.create_embed(description=f'From:\n `{f_form}`\n\nTo:\n `{t_form}`', title=f'{f.tzname()} -> {t.tzname()}'))

    @commands.command(name='user')
    async def user(self, ctx: Context, user: discord.Member = None):
        """
        Get's information about a user.

        Examples:
            user
            user DarkKronicle
        """
        if user is None:
            user = ctx.author
        pfp = user.avatar_url
        embed = ctx.create_embed(title=str(user))
        embed.set_image(url=pfp)
        description = f'Created: `{user.created_at}`'
        embed.description = description
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utility())

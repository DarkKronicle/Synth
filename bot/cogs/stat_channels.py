import bot.util.checks as checks
import bot.util.database as db
import discord
from discord.ext import commands


class StatChannels(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_loop('statchannels', self.channel_loop)

    def cog_unload(self):
        self.bot.remove_loop('statchannels')

    @commands.command(name='*refresh', hidden=True)
    @commands.is_owner()
    async def refresh(self, ctx):
        """Forces a refresh of the statistic channels"""
        await self.refresh_channels()
        await ctx.check(0)

    async def channel_loop(self, time):
        if time.minute % 30 == 0:
            await self.refresh_channels()

    async def refresh_channels(self):
        channel: discord.VoiceChannel = self.bot.get_guild(753693459369427044).get_channel(842214460701933639)
        command = "SELECT amount FROM messages WHERE guild_id = {0} AND time >= NOW() at time zone 'utc' - INTERVAL '24 HOURS';"
        command = command.format(753693459369427044)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()
        i = 0
        for e in entries:
            i += e['amount']
        await channel.edit(name=f'{i}')


def setup(bot):
    bot.add_cog(StatChannels(bot))

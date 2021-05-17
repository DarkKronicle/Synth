"""
Class for user's managing data that is maintained by the bot.
"""
import csv
from io import StringIO

import discord
from bot.util import checks
from bot.util import database as db
from bot.util.context import Context
from discord.ext import commands


def get_row(guild, entry):
    channel_id = entry['channel_id']
    user_id = entry['user_id']
    channel = guild.get_channel(channel_id) or channel_id
    user = guild.get_member(user_id) or user_id
    return [channel, user, entry['amount'], entry['time']]


class Data(commands.Cog):   # noqa: WPS110
    """Manage data stored in the bot."""

    def __init__(self, bot):
        """
        Initiates the Cog
        :param bot: SynthBot
        """
        self.bot = bot

    @commands.group(name='!export')
    @checks.is_mod()
    async def export(self, ctx: Context):
        """Export command for server information."""

    @export.command(name='all')
    async def export_all(self, ctx: Context):
        """Exports all message data in the form of a CSV."""
        await ctx.trigger_typing()

        buffer = StringIO()
        writer = csv.writer(buffer)
        entries = await self.get_all_guild_entries(ctx.guild.id)
        for entry in entries:
            writer.writerow(get_row(ctx.guild, entry))
        buffer.seek(0)
        export_content = "Here's the data for {0}! Total of `{1}` entries.".format(ctx.guild.name, len(entries))
        await ctx.send(
            export_content,
            file=discord.File(fp=buffer, filename='data.csv'),
        )

    async def get_all_guild_entries(self, guild_id):
        command = 'SELECT * FROM messages WHERE guild_id = {0};'
        async with db.MaybeAcquire() as con:
            con.execute(command.format(str(guild_id)))
            return con.fetchall()


def setup(bot):
    bot.add_cog(Data(bot))

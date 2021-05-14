import csv
from io import StringIO

import discord
from discord.ext import commands

from bot.util import checks
from bot.util.context import Context
import bot.util.database as db


class Data(commands.Cog):
    """Manage data stored in the bot."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="!export")
    @checks.is_mod()
    async def export(self, ctx: Context):
        """
        Export command for server information.
        """
        pass

    @export.command(name="all")
    async def export_all(self, ctx: Context):
        """
        Exports all message data in the form of a CSV.
        """
        await ctx.trigger_typing()
        command = "SELECT * FROM messages WHERE guild_id = {0};"
        command = command.format(str(ctx.guild.id))
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()
        buffer = StringIO()
        writer = csv.writer(buffer)
        i = 0
        id_to_name = {}
        for e in entries:
            i += 1
            channel_id = e["channel_id"]
            user_id = e["user_id"]
            if user_id not in id_to_name:
                user = ctx.guild.get_member(user_id)
                if user is not None:
                    id_to_name[user_id] = str(user)
                else:
                    id_to_name[user_id] = str(user_id)
            if channel_id not in id_to_name:
                channel = ctx.guild.get_channel(channel_id)
                if channel is not None:
                    id_to_name[channel_id] = channel.name
                else:
                    id_to_name[channel_id] = str(channel_id)
            writer.writerow([id_to_name[channel_id], id_to_name[user_id], e["amount"], e["time"]])
        buffer.seek(0)
        file = discord.File(fp=buffer, filename="data.csv")
        await ctx.send(f"Here's the data for {ctx.guild.name}! Total of `{i}` entries.", file=file)


def setup(bot):
    bot.add_cog(Data(bot))

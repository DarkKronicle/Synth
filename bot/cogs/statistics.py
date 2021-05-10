import datetime
from collections import Counter
from io import StringIO

from discord.ext import commands
import discord
import bot.util.database as db
import csv

from bot.util.context import Context


class Statistics(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="stats", aliases=["statistics", "stat"])
    @commands.guild_only()
    async def stats(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help("stats")

    @stats.group(name="export")
    async def export(self, ctx: Context):
        pass

    @export.command(name="all")
    async def export_all(self, ctx: Context):
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

    @stats.command(name="today")
    async def total_today(self, ctx: Context, type: str = None):
        if type is None:
            return await ctx.send("Please specify a type! `messages` `voice`")

        if type == "messages":
            embed = await self.get_message_embed(ctx.guild)
            return await ctx.send(embed=embed)

        if type == "voice":
            embed = await self.get_voice_embed(ctx.guild)
            return await ctx.send(embed=embed)

    async def get_message_embed(self, guild, *, interval="24 Hours"):
        command = "SELECT * FROM messages WHERE guild_id = {0} AND time >= NOW() at time zone 'utc' - INTERVAL '{1}';"
        command = command.format(str(guild.id), interval)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()

        formatted_people = []
        i = 0
        for p, amount in self.count(entries, "user_id", n=5):
            i += 1
            formatted_people.append(f"`{i}.` <@{p}> - `{amount} messages`")

        formatted_channels = []
        i = 0
        for c, amount in self.count(entries, "channel_id", n=5):
            i += 1
            formatted_channels.append(f"`{i}.` <#{c}> - `{amount} messages`")

        description = f"**Messages | Top 5 Users**\n" + "\n".join(formatted_people) + "\n\n **Messages | Top 5 Channels**\n" \
                      + "\n".join(formatted_channels)
        embed = discord.Embed(
            title=f"Past {interval} for {guild.name}",
            description=description,
            colour=discord.Colour(0x9d0df0)
        )
        return embed

    async def get_voice_embed(self, guild, *, interval="24 Hours"):
        command = "SELECT * FROM voice WHERE guild_id = {0} AND time + amount >= NOW() at time zone 'utc' - INTERVAL '{1}';"
        command = command.format(str(guild.id), interval)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()

        formatted_people = []
        i = 0
        for p, amount in self.time(entries, "user_id", n=5):
            i += 1
            formatted_people.append(f"`{i}.` <@{p}> - `{self.human(amount // 1)}`")

        formatted_channels = []
        i = 0
        for c, amount in self.time(entries, "channel_id", n=5):
            i += 1
            formatted_channels.append(f"`{i}.` <#{c}> - `{self.human(amount // 1)}`")

        description = f"**Messages | Top 5 Users**\n" + "\n".join(formatted_people) + "\n\n **Messages | Top 5 Channels**\n" \
                      + "\n".join(formatted_channels)
        embed = discord.Embed(
            title=f"Past {interval} for {guild.name}",
            description=description,
            colour=discord.Colour(0x9d0df0)
        )
        return embed

    def time(self, entries, key, *, n=10):
        time = Counter()
        for e in entries:
            time[e[key]] += e["amount"].total_seconds()
        return time.most_common(n)

    def count(self, entries, key, *, n=10):
        people = Counter()
        for e in entries:
            people[e[key]] += e["amount"]
        return people.most_common(n)

    def human(self, total_seconds):
        seconds = total_seconds % 60
        minutes = (total_seconds // 60) % 60
        hours = total_seconds // 60 // 60 % 24
        days = total_seconds // 60 // 60 // 24
        builder = []
        if days > 0:
            builder.append(f"{int(days)} days")
        if hours > 0:
            builder.append(f"{int(hours)} hours")
        if minutes > 0:
            builder.append(f"{int(minutes)} minutes")
        if seconds > 0:
            builder.append(f"{int(seconds)} seconds")
        return ", ".join(builder)

def setup(bot):
    bot.add_cog(Statistics(bot))

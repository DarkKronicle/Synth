from collections import Counter
from datetime import datetime, timedelta
from io import StringIO, BytesIO

from dateutil.tz import gettz

import bot.util.time_util as tutil
from discord.ext import commands
import discord
import matplotlib.pyplot as plt
import matplotlib.dates as md
import bot.util.database as db
import csv

from bot.util.context import Context


class StatisticType:

    def __init__(self, *, guild=None, channel=None, member=None):
        self.guild = guild
        self.channel = channel
        self.member = member

    def is_member(self):
        return self.member is not None

    def is_channel(self):
        return self.channel is not None and self.member is None

    def is_guild(self):
        return self.guild is not None and self.channel is None and self.member is None

    def data(self):
        if self.is_member():
            return self.member
        if self.is_channel():
            return self.channel
        if self.is_guild():
            return self.guild

    def get_condition(self):
        if self.is_member():
            return f"guild_id = {self.guild.id} AND user_id = {self.member.id}"
        if self.is_channel():
            return f"channel_id = {self.channel.id}"
        if self.is_guild():
            return f"guild_id = {self.guild.id}"

    def get_name(self):
        if self.is_member():
            return str(self.member)
        if self.is_channel():
            return self.channel.name
        if self.is_guild():
            return self.guild.name


class StatConverter(commands.Converter):

    async def convert(self, ctx: Context, argument):
        low = argument.lower()
        if low == "guild":
            return StatisticType(guild=ctx.guild, channel=ctx.channel)
        try:
            channel = await commands.GuildChannelConverter().convert(ctx, argument)
            return StatisticType(channel=channel, guild=ctx.guild)
        except commands.errors.ChannelNotFound:
            pass
        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            return StatisticType(channel=ctx.channel, guild=ctx.guild, member=member)
        except commands.errors.MemberNotFound:
            pass
        return None


class Statistics(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.main_color = discord.Colour(0x9d0df0)

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

    @stats.command(name="messages")
    async def messages(self, ctx: Context, selection: StatConverter = None):
        if selection is None:
            selection = StatisticType(guild=ctx.guild)

        command = "SELECT * FROM messages WHERE {0} AND time >= NOW() at time zone 'utc' - INTERVAL '{1}';"
        command = command.format(selection.get_condition(), '24 HOURS')
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()
        embed = await self.get_message_embed(selection, entries=entries)
        plot = await self.plot_24_hour_total(entries=entries)
        embed.set_image(url="attachment://graph.png")
        return await ctx.send(embed=embed, file=discord.File(fp=plot, filename="graph.png"))

    async def get_message_embed(self, selection, *, interval="24 Hours", entries=None):
        if entries is None:
            command = "SELECT * FROM messages WHERE {0} AND time >= NOW() at time zone 'utc' - INTERVAL '{1}';"
            command = command.format(selection.get_condition(), interval)
            async with db.MaybeAcquire() as con:
                con.execute(command)
                entries = con.fetchall()

        description = ""
        if not selection.is_member():
            formatted_people = []
            i = 0
            for p, amount in self.count(entries, "user_id", n=5):
                i += 1
                formatted_people.append(f"`{i}.` <@{p}> - `{amount} messages`")
            description += f"**Messages | Top 5 Users**\n" + "\n".join(formatted_people)

        if not selection.is_channel():
            formatted_channels = []
            i = 0
            for c, amount in self.count(entries, "channel_id", n=5):
                i += 1
                formatted_channels.append(f"`{i}.` <#{c}> - `{amount} messages`")
            description += "\n\n **Messages | Top 5 Channels**\n" \
                           + "\n".join(formatted_channels)

        embed = discord.Embed(
            title=f"Past {interval} for {selection.get_name()}",
            description=description,
            colour=discord.Colour(0x9d0df0)
        )
        time = datetime.now(gettz('UTC'))
        time_str = time.strftime("%H:%M:%S UTC")

        embed.set_footer(text=time_str)
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
            formatted_people.append(f"`{i}.` <@{p}> - `{tutil.human(amount // 1)}`")

        formatted_channels = []
        i = 0
        for c, amount in self.time(entries, "channel_id", n=5):
            i += 1
            formatted_channels.append(f"`{i}.` <#{c}> - `{self.human(amount // 1)}`")

        description = f"**Messages | Top 5 Users**\n" + "\n".join(
            formatted_people) + "\n\n **Messages | Top 5 Channels**\n" \
                      + "\n".join(formatted_channels)
        embed = discord.Embed(
            title=f"Past {interval} for {guild.name}",
            description=description,
            colour=self.main_color
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

    async def plot_24_hour_total(self, entries):

        # Amount of messages per time
        data = Counter()
        data[datetime.now()] = 0
        data[datetime.now() - timedelta(days=1)] = 0
        for e in entries:
            data[e['time']] += e["amount"]

        plt.style.use('dark_background')
        fig, ax = plt.subplots(ncols=1, nrows=1)
        ax.xaxis.set_major_locator(md.HourLocator(interval=4))
        date_fm = md.DateFormatter('%H:%M')
        ax.xaxis.set_major_formatter(date_fm)
        ax.yaxis.grid(color="white", alpha=0.2)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

        ax.set_xlabel("Time (UTC)")
        ax.set_ylabel("Messages")
        _ = ax.bar(data.keys(), data.values(), width=1 / 48, alpha=1, align='edge', edgecolor=str(self.main_color),
                   color=str(self.main_color))
        fig.autofmt_xdate()

        buffer = BytesIO()
        fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight")
        buffer.seek(0)
        return buffer


def setup(bot):
    bot.add_cog(Statistics(bot))

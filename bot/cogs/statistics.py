from collections import Counter
from datetime import datetime, timedelta
from io import BytesIO

from dateutil.tz import gettz

import bot.util.time_util as tutil
from discord.ext import commands
import discord
import matplotlib.pyplot as plt
import matplotlib.dates as md
import bot.util.database as db
import re
import typing

from bot.util.context import Context
from bot.util.paginator import ImagePaginator


class StatisticType:

    def __init__(self, *, guild=None, channel=None, member=None, _global=False):
        self.guild = guild
        self.channel = channel
        self.member = member
        self._global = _global

    def is_member(self):
        return self.member is not None

    def is_channel(self):
        return self.channel is not None and self.member is None

    def is_guild(self):
        return self.guild is not None and self.channel is None and self.member is None

    def is_global(self):
        return self._global

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
        if self.is_global():
            return "time IS NOT NONE"

    def get_name(self):
        if self.is_member():
            return str(self.member)
        if self.is_channel():
            return self.channel.name
        if self.is_guild():
            return self.guild.name
        if self.is_global():
            return "global"


class StatConverter(commands.Converter):

    async def convert(self, ctx: Context, argument):
        low = argument.lower()
        if low == "global" and await ctx.bot.is_owner(ctx.author):
            return StatisticType(_global=True)
        if low == "guild" or low == "server":
            return StatisticType(guild=ctx.guild, channel=ctx.channel)
        try:
            channel = await commands.TextChannelConverter().convert(ctx, argument)
            return StatisticType(channel=channel, guild=ctx.guild)
        except commands.errors.ChannelNotFound:
            try:
                channel = await commands.VoiceChannelConverter().convert(ctx, argument)
                return StatisticType(channel=channel, guild=ctx.guild)
            except commands.errors.ChannelNotFound:
                pass
        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            return StatisticType(channel=ctx.channel, guild=ctx.guild, member=member)
        except commands.errors.MemberNotFound:
            pass
        raise commands.errors.BadArgument()


class IntervalConverter(commands.Converter):

    DAY_REGEX = re.compile(r"(\d{1,2}) day(s)?")
    WEEK_REGEX = re.compile(r"(\d{1,2}) week(s)?")
    MONTH_REGEX = re.compile(r"(\d{1,2}) month(s)?")

    async def convert(self, ctx: Context, argument):
        low = argument.lower()
        match: re.Match = self.DAY_REGEX.search(low)
        if match:
            days = int(match.group(1))
            if days <= 0:
                raise commands.errors.BadArgument("Days has to be greater than 0!")
            return f"{days} days"
        match: re.Match = self.WEEK_REGEX.search(low)
        if match:
            weeks = int(match.group(1))
            if weeks <= 0:
                raise commands.errors.BadArgument("Weeks has to be great than 0!")
            return f"{weeks} weeks"
        match: re.Match = self.MONTH_REGEX.search(low)
        if match:
            months = int(match.group(1))
            if months >= 24 or months <= 0:
                raise commands.errors.BadArgument("Months has to be above zero and below 24!")
            return f"{months} months"
        return None


class Statistics(commands.Cog):
    """Commands to view statistics about the server."""

    def __init__(self, bot):
        self.bot = bot
        self.main_color = discord.Colour(0x9d0df0)

    @commands.group(name="stats", aliases=["statistics", "stat"])
    @commands.guild_only()
    async def stats(self, ctx: Context):
        """
        View statistics about the server.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help("stats")

    @stats.command(name="messages", aliases=["msg", "message"])
    async def messages(self, ctx: Context, selection: typing.Optional[StatConverter] = None, *, interval: IntervalConverter = "1 day"):
        """
        Pulls up a menu with statistics containing chat information.

        An interval of days, weeks, or months can be specified and specific channel/user to grab from.

        Examples:
            messages DarkKronicle
            messages 1 month
            messages general 5 days
        """
        if selection is None:
            selection = StatisticType(guild=ctx.guild)
        if interval is None:
            interval = '1 day'

        command = "SELECT * FROM messages WHERE {0} AND time >= NOW() at time zone 'utc' - INTERVAL '{1}';"
        command = command.format(selection.get_condition(), interval)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()
        embed = await self.get_message_embed(ctx, selection, entries=entries, interval=interval)
        images = [await self.plot_24_hour_messages(entries=entries)]
        if not selection.is_channel():
            images.append(await self.plot_message_channel_pie(ctx, entries))
        if not selection.is_member():
            images.append(await self.plot_message_user_pie(ctx, entries))
        embed.set_image(url="attachment://graph.png")
        menu = ImagePaginator(embed, images)
        await menu.start(ctx)

    async def get_message_embed(self, ctx, selection, *, interval="24 Hours", entries=None):
        if entries is None:
            command = "SELECT * FROM messages WHERE {0} AND time >= NOW() at time zone 'utc' - INTERVAL '{1}';"
            command = command.format(selection.get_condition(), interval)
            async with db.MaybeAcquire() as con:
                con.execute(command)
                entries = con.fetchall()

        small, big = self.count_compressed(entries)
        description = f"Total of `{self.count_all(entries)} messages`\n\n\*{small} messages lost some data, {big} messages lost .\n\n"
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

        embed = ctx.create_embed(
            title=f"Past {interval} for {selection.get_name()}",
            description=description
        )
        time = datetime.utcnow()
        time_str = time.strftime("%H:%M:%S UTC")

        embed.set_footer(text=time_str)
        return embed

    @stats.command(name="voice")
    async def voice(self, ctx: Context, selection: typing.Optional[StatConverter] = None, *, interval: IntervalConverter = "1 day"):
        """
        Pulls up a menu with statistics containing voice chat information.

        An interval of days, weeks, or months can be specified and specific channel/user to grab from.

        Examples:
            voice DarkKronicle
            voice 1 month
            voice general 5 days
        """
        if selection is None:
            selection = StatisticType(guild=ctx.guild)
        if interval is None:
            interval = "1 day"
        command = "SELECT * FROM voice WHERE {0} AND time + amount >= NOW() at time zone 'utc' - INTERVAL '{1}';"
        command = command.format(selection.get_condition(), interval)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()
        embed = await self.get_voice_embed(ctx, selection, entries=entries, interval=interval)
        # plot = await self.plot_24_hour_voice(entries=entries)
        # embed.set_image(url="attachment://graph.png")
        return await ctx.send(embed=embed, file=discord.File(fp=plot, filename="graph.png"))

    async def get_voice_embed(self, ctx, selection, *, interval="24 Hours", entries=None):
        if entries is None:
            command = "SELECT * FROM voice WHERE guild_id = {0} AND time + amount >= NOW() at time zone 'utc' - INTERVAL '{1}';"
            command = command.format(selection.get_condition(), interval)
            async with db.MaybeAcquire() as con:
                con.execute(command)
                entries = con.fetchall()

        description = f"Total of `{tutil.human(self.time_all(entries))}`"
        if not selection.is_member():
            formatted_people = []
            i = 0
            for p, amount in self.time(entries, "user_id", n=5):
                i += 1
                formatted_people.append(f"`{i}.` <@{p}> - `{tutil.human(amount // 1)}`")
            description += "\n\n **Voice | Top 5 Users**\n" \
                            + "\n".join(formatted_people)

        if not selection.is_channel():
            formatted_channels = []
            i = 0
            for c, amount in self.time(entries, "channel_id", n=5):
                i += 1
                formatted_channels.append(f"`{i}.` <#{c}> - `{tutil.human(amount // 1)}`")
            description += f"\n\n**Voice | Top 5 Channels**\n" + "\n".join(formatted_channels)
        embed = ctx.create_embed(
            title=f"Past {interval} for {selection.get_name()}",
            description=description
        )
        return embed

    def time(self, entries, key, *, n=10):
        time = Counter()
        for e in entries:
            if e[key] is not None:
                time[e[key]] += e["amount"].total_seconds()
        return time.most_common(n)

    def time_all(self, entries):
        i = 0
        for e in entries:
            i += e["amount"].total_seconds()
        return i

    def count(self, entries, key, *, n=10):
        people = Counter()
        for e in entries:
            if e[key] is not None:
                people[e[key]] += e["amount"]
        return people.most_common(n)

    def count_all(self, entries):
        i = 0
        for e in entries:
            if e["channel_id"] is not None or (e["channel_id"] is None and e["user_id"] is None):
                i += e["amount"]
        return i

    def count_compressed(self, entries):
        small = 0
        big = 0
        for e in entries:
            if e["channel_id"] is None and e["user_id"] is None:
                big += e["amount"]
            elif e["channel_id"] is None or e["user_id"] is None:
                small += e["amount"]
        return small, big

    async def plot_24_hour_messages(self, entries):

        # Amount of messages per time
        data = Counter()
        min_date = datetime.now()
        max_date = datetime.now() - timedelta(hours=1)
        for e in entries:
            min_date = min(min_date, e['time'])
            max_date = max(max_date, e['time'])
            data[e['time']] += e["amount"]
        if (max_date - min_date).days > 0:
            keys = [k for k in data.keys()]
            for k in keys:
                data[k.replace(year=2020, month=1, day=1)] = data.pop(k)
            min_date = datetime(year=2020, month=1, day=1, minute=0, hour=0, second=0, microsecond=0)
            data[min_date] = 0
            max_date = datetime(year=2020, month=1, day=2, minute=0, hour=0, second=0, microsecond=0)
            data[max_date] = 0
        else:
            max_date = tutil.get_utc() + timedelta(minutes=30)
            min_date = max_date - timedelta(days=1, minutes=30)
            data[max_date] = 0
            data[min_date] = 0
        plt.style.use('dark_background')
        fig, ax = plt.subplots(ncols=1, nrows=1)
        ax.xaxis.set_major_locator(md.HourLocator(interval=2))
        ax.xaxis.set_minor_locator(md.HourLocator(interval=1))
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

        plt.xlim([min_date, max_date])

        buffer = BytesIO()
        fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight")
        buffer.seek(0)
        fig.clear()
        plt.close(fig)
        return buffer

    async def plot_message_channel_pie(self, ctx, entries):
        lost = 0
        channels = Counter()
        id_to_name = {}
        for e in entries:
            channel_id = e["channel_id"]
            if channel_id is None and e["user_id"] is None:
                lost += e["amount"]
            elif channel_id is not None:
                if channel_id not in id_to_name:
                    channel = ctx.guild.get_channel(channel_id)
                    if channel is not None:
                        id_to_name[channel_id] = channel.name
                    else:
                        id_to_name[channel_id] = str(channel_id)
                channels[id_to_name[channel_id]] += e["amount"]
        name = []
        amount = []
        for c, a in channels.items():
            name.append(c)
            amount.append(a)
        if lost > 0:
            labels = ["Lost", *name]
            sizes = [lost, *amount]
        else:
            labels = name
            sizes = amount
        plt.style.use('dark_background')
        fig, ax = plt.subplots()
        _, _, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        for text in autotexts:
            text.set_color("black")
        ax.axis('equal')
        buffer = BytesIO()
        fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight")
        buffer.seek(0)
        fig.clear()
        plt.close(fig)
        return buffer

    async def plot_message_user_pie(self, ctx, entries):
        lost = 0
        users = Counter()
        id_to_name = {}
        for e in entries:
            user_id = e["user_id"]
            if user_id is None and e["user_id"] is None:
                lost += e["amount"]
            elif user_id is not None:
                if user_id not in id_to_name:
                    user = ctx.guild.get_member(user_id)
                    if user is not None:
                        id_to_name[user_id] = user.name
                    else:
                        id_to_name[user_id] = str(user_id)
                users[id_to_name[user_id]] += e["amount"]
        name = []
        amount = []
        for c, a in users.items():
            name.append(c)
            amount.append(a)
        if lost > 0:
            labels = ["Lost", *name]
            sizes = [lost, *amount]
        else:
            labels = name
            sizes = amount
        plt.style.use('dark_background')
        fig, ax = plt.subplots()
        _, _, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        for text in autotexts:
            text.set_color("black")
        ax.axis('equal')
        buffer = BytesIO()
        fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight")
        buffer.seek(0)
        fig.clear()
        plt.close(fig)
        return buffer

    async def plot_24_hour_voice(self, entries):
        data = Counter()
        logged = {}
        min_date = datetime.now()
        max_date = datetime.now() - timedelta(hours=1)
        data[datetime.now()] = 0
        data[datetime.now() - timedelta(days=1)] = 0
        for e in entries:
            time = tutil.round_time(e['time'], 60 * 30)
            added = 0
            min_date = min(min_date, e['time'])
            while added < e['amount'].total_seconds():
                max_date = max(max_date, time)
                if time not in logged:
                    logged[time] = []
                if e['user_id'] not in logged[time]:
                    data[time] += 1
                    logged[time].append(e['user_id'])
                time = time + timedelta(minutes=30)
                added += 60 * 30
        if (max_date - min_date).days > 0:
            keys = [k for k in data.keys()]
            for k in keys:
                data[k.replace(year=2020, month=1, day=1)] = data.pop(k)
            min_date = datetime(year=2020, month=1, day=1, minute=0, hour=0, second=0, microsecond=0)
            data[min_date] = 0
            max_date = datetime(year=2020, month=1, day=2, minute=0, hour=0, second=0, microsecond=0)
            data[max_date] = 0
        else:
            max_date = tutil.get_utc() + timedelta(minutes=30)
            min_date = max_date - timedelta(days=1, minutes=30)
            data[max_date] = 0
            data[min_date] = 0
        plt.style.use('dark_background')
        fig, ax = plt.subplots(ncols=1, nrows=1)
        ax.xaxis.set_major_locator(md.HourLocator(interval=2))
        ax.xaxis.set_minor_locator(md.HourLocator(interval=1))
        date_fm = md.DateFormatter('%H:%M')
        ax.xaxis.set_major_formatter(date_fm)
        ax.yaxis.grid(color="white", alpha=0.2)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

        ax.set_xlabel("Time (UTC)")
        ax.set_ylabel("Amount in Voice Channel")
        _ = ax.bar(data.keys(), data.values(), width=1 / 48, alpha=1, align='edge', edgecolor=str(self.main_color),
                   color=str(self.main_color))
        fig.autofmt_xdate()

        plt.xlim([min_date, max_date])
        buffer = BytesIO()
        fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight")
        buffer.seek(0)
        fig.clear()
        plt.close(fig)
        return buffer


def setup(bot):
    bot.add_cog(Statistics(bot))

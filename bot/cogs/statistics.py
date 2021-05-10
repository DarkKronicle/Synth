from collections import Counter
from datetime import datetime, timedelta
from io import StringIO, BytesIO

from discord.ext import commands
import discord
import matplotlib.pyplot as plt
import matplotlib.dates as md
import bot.util.database as db
import csv

from bot.util.context import Context


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

    @stats.command(name="today")
    async def total_today(self, ctx: Context, type: str = None):
        if type is None:
            return await ctx.send("Please specify a type! `messages` `voice`")

        if type == "messages":
            embed = await self.get_message_embed(ctx.guild)
            plot = await self.plot_24_hour_total(f"guild_id = {ctx.guild.id}")
            embed.set_image(url="attachment://graph.png")
            return await ctx.send(embed=embed, file=discord.File(fp=plot, filename="graph.png"))

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

    async def plot_24_hour_total(self, condition):
        command = "SELECT * FROM messages WHERE {0} AND time >= NOW() at time zone 'utc' " \
                  "- INTERVAL '{1}' ORDER BY time; "
        command = command.format(condition, '24 HOURS')
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()

        # Amount of messages per time
        data = Counter()
        data[datetime.now()] = 0
        data[datetime.now() - timedelta(days=1)] = 0
        for e in entries:
            data[e['time']] += e["amount"]

        plt.style.use('dark_background')
        fig, ax = plt.subplots(ncols=1, nrows=1)
        ax.xaxis.set_major_locator(md.HourLocator(interval=3))
        date_fm = md.DateFormatter('%H:%M')
        ax.xaxis.set_major_formatter(date_fm)
        ax.yaxis.grid(color="white", alpha=0.2)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)

        ax.set_xlabel("Time (UTC)")
        ax.set_ylabel("Messages")
        _ = ax.bar(data.keys(), data.values(), width=1/48, alpha=1, align='edge', edgecolor=str(self.main_color), color=str(self.main_color))
        fig.autofmt_xdate()

        buffer = BytesIO()
        fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight")
        buffer.seek(0)
        return buffer


def setup(bot):
    bot.add_cog(Statistics(bot))

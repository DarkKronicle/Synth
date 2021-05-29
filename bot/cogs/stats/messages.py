import datetime
from collections import Counter

import bot.util.database as db
import bot.util.storage_cache as storage_cache
import bot.util.time_util as tutil
import discord

from bot.cogs import guild_config
from bot.cogs.stats import stat_config
from bot.util.context import Context
from discord.ext import commands


class MessagesTable(db.Table, table_name='messages'):
    guild_id = db.Column(db.Integer(big=True), nullable=False, index=True)
    channel_id = db.Column(db.Integer(big=True), nullable=True)
    user_id = db.Column(db.Integer(big=True), nullable=True)
    amount = db.Column(db.Integer(small=True), nullable=False, default='1')
    time = db.Column(db.Datetime(), default="date_trunc('hour', now()) at time zone 'utc'", index=True)
    interval = db.Column(db.Interval(), default="INTERVAL '30 MINUTES'")

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)

        # create the indexes
        sql = 'ALTER TABLE messages DROP CONSTRAINT IF EXISTS unique_message;' \
              'ALTER TABLE messages ADD CONSTRAINT unique_message UNIQUE (guild_id, channel_id, user_id, time);'

        return statement + '\n' + sql


class Messages(commands.Cog):
    """Tracks messages using the bot."""

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_loop('messagepush', self.update_loop)
        self.cache = Counter()
        self.cooldown = storage_cache.ExpiringDict(60)

    def cog_unload(self):
        self.bot.remove_loop('messagepush')

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        command = 'INSERT INTO guild_config(guild_id) VALUES ({0}) ON CONFLICT (guild_id) DO NOTHING;'
        command = command.format(guild.id)
        async with db.MaybeAcquire() as con:
            con.execute(command)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.channel is None or message.author.bot:
            return
        if (message.guild.id, message.author.id) in self.cooldown:
            return
        if not await stat_config.should_log(self.bot, message.guild, message.channel, message.author):
            return
        self.cache[(message.guild.id, message.channel.id, message.author.id)] += 1
        cool = await guild_config.get_guild_settings(self.bot, message.guild)
        if cool is None:
            wait = 60
        else:
            wait = cool.message_cooldown
        if wait > 0:
            self.cooldown.set((message.guild.id, message.author.id), 1, wait)

    async def update_loop(self, time: datetime.datetime):
        if time.minute % 5 == 0:
            await self.push()
        if time.minute == 0 and time.hour == 0:
            print('Updating flattening...')
            await self.push_flat()

    async def push_flat(self):
        g_settings = {}
        command = 'SELECT guild_id, specific_remove, time_remove, ' \
                  'detail_remove FROM guild_config;'
        async with db.MaybeAcquire() as con:
            con.execute(command)
            settings = con.fetchall()
        for e in settings:
            g_settings[e['guild_id']] = {
                'specific': e['specific_remove'],
                'time': e['time_remove'],
                'detail': e['detail_remove']
            }
        for g, setting in g_settings.items():
            async with db.MaybeAcquire() as con:
                await self.flat_specific(g, setting['specific'], con)
                await self.flat_time(g, setting['time'], con)
                await self.flat_details(g, setting['detail'], con)
        not_in = []
        command = 'INSERT INTO messages(guild_id) VALUES {0} ON CONFLICT ON CONSTRAINT unique_message DO NOTHING;'
        for guild in self.bot.guilds:
            if guild.id not in g_settings:
                not_in.append(f'({guild.id})')
        if len(not_in) == 0:
            return
        command = command.format(', '.join(not_in))
        async with db.MaybeAcquire() as con:
            con.execute(command)

    @commands.command(name='*messagepush', hidden=True)
    @commands.is_owner()
    async def message_push(self, ctx: Context):
        """Updates the messages in the database"""
        await self.push()
        await ctx.check(0)

    async def push(self):
        if len(self.cache) == 0:
            return
        insert = []
        time = tutil.floor_time(top=30)
        time_str = time.strftime("'%Y-%m-%d %H:%M:%S'")
        interval = "INTERVAL '30 MINUTES'"
        value = '({0}, {1}, {2}, {3}, {4}, {5})'
        for data, amount in self.cache.items():
            insert.append(value.format(str(data[0]), str(data[1]), str(data[2]), amount, time_str, interval))

        command = 'INSERT INTO messages(guild_id, channel_id, user_id, amount, time, interval) VALUES {0} ' \
                  'ON CONFLICT ON CONSTRAINT unique_message' \
                  ' DO UPDATE SET amount = messages.amount + EXCLUDED.amount;'
        command = command.format(', '.join(insert))
        async with db.MaybeAcquire() as con:
            con.execute(command)
        self.cache.clear()

    @commands.command(name='*flatspecific', hidden=True)
    @commands.is_owner()
    async def flat_specific_command(self, ctx: Context, guild_id: int, upper: int):
        if ctx.bot.get_guild(guild_id) is None:
            return await ctx.send('Not a guild!')
        async with db.MaybeAcquire() as con:
            await self.flat_specific(guild_id, upper, con)
        await ctx.check(0)

    @commands.command(name='*flattime', hidden=True)
    @commands.is_owner()
    async def flat_specific_command(self, ctx: Context, guild_id: int, upper: int):
        if ctx.bot.get_guild(guild_id) is None:
            return await ctx.send('Not a guild!')
        async with db.MaybeAcquire() as con:
            await self.flat_time(guild_id, upper, con)
        await ctx.check(0)

    @commands.command(name='*flatdetails', hidden=True)
    @commands.is_owner()
    async def flat_specific_command(self, ctx: Context, guild_id: int, upper: int):
        if ctx.bot.get_guild(guild_id) is None:
            return await ctx.send('Not a guild!')
        async with db.MaybeAcquire() as con:
            await self.flat_details(guild_id, upper, con)
        await ctx.check(0)

    async def flat_specific(self, guild_id, days, con):
        interval = f"INTERVAL '{days} DAYS'"
        command = f"DELETE FROM messages WHERE time <= NOW() at time zone 'utc' - {interval} AND guild_id = {guild_id} AND channel_id IS NOT NULL AND user_id IS NOT NULL RETURNING *;"
        con.execute(command)
        entries = con.fetchall()
        channels = Counter()
        users = Counter()
        for e in entries:
            channels[(e['channel_id'], e['time'], e['interval'])] += e['amount']
            users[(e['user_id'], e['time'], e['interval'])] += e['amount']
        value = '({0}, {1}, {2}, {3}, {4})'
        if len(channels) > 0:
            channel_values = []
            for channel_id, time, interval in channels.keys():
                amount = channels[(channel_id, time, interval)]
                channel_values.append(
                    value.format(str(guild_id), str(channel_id), str(amount), f"TIMESTAMP '{time}'", f"INTERVAL '{interval}'"))

            channel_command = 'INSERT INTO messages(guild_id, channel_id, amount, time, interval) VALUES {0} ' \
                              'ON CONFLICT ON CONSTRAINT unique_message' \
                              ' DO UPDATE SET amount = messages.amount + EXCLUDED.amount;'
            channel_command = channel_command.format(', '.join(channel_values))
            con.execute(channel_command)

        if len(users) > 0:
            user_values = []
            for user_id, time, interval in users.keys():
                amount = users[(user_id, time, interval)]
                user_values.append(
                    value.format(str(guild_id), str(user_id), str(amount), f"TIMESTAMP '{time}'",
                                 f"INTERVAL '{interval}'"))

            user_command = 'INSERT INTO messages(guild_id, user_id, amount, time, interval) VALUES {0} ' \
                           'ON CONFLICT ON CONSTRAINT unique_message' \
                           ' DO UPDATE SET amount = messages.amount + EXCLUDED.amount;'
            user_command = user_command.format(', '.join(user_values))
            con.execute(user_command)

    async def flat_time(self, guild_id, days, con):
        interval = f"INTERVAL '{days} DAYS'"
        command = f"DELETE FROM messages WHERE time <= NOW() at time zone 'utc' - {interval} AND guild_id = {guild_id} AND (channel_id IS NOT NULL or user_id IS NOT NULL) RETURNING *;"
        con.execute(command)
        entries = con.fetchall()
        channels = Counter()
        users = Counter()
        for e in entries:
            if e['channel_id'] is not None:
                channels[(e['channel_id'], e['time'].date(), e['interval'])] += e['amount']
            if e['user_id'] is not None:
                users[(e['user_id'], e['time'].date(), e['interval'])] += e['amount']
        value = '({0}, {1}, {2}, {3}, {4})'
        if len(channels) > 0:
            channel_values = []
            for channel_id, time, interval in channels.keys():
                amount = channels[(channel_id, time, interval)]
                channel_values.append(
                    value.format(str(guild_id), str(channel_id), str(amount), f"TIMESTAMP '{datetime.datetime.combine(time, datetime.datetime.min.time())}'",
                                 "INTERVAL '1 DAY'"))

            channel_command = 'INSERT INTO messages(guild_id, channel_id, amount, time, interval) VALUES {0} ' \
                              'ON CONFLICT ON CONSTRAINT unique_message' \
                              ' DO UPDATE SET amount = messages.amount + EXCLUDED.amount;'
            channel_command = channel_command.format(', '.join(channel_values))
            con.execute(channel_command)

        if len(users) > 0:
            user_values = []
            for user_id, time, interval in users.keys():
                amount = users[(user_id, time, interval)]
                user_values.append(
                    value.format(str(guild_id), str(user_id), str(amount), f"TIMESTAMP '{datetime.datetime.combine(time, datetime.datetime.min.time())}'",
                                 "INTERVAL '1 DAY'"))

            user_command = 'INSERT INTO messages(guild_id, user_id, amount, time, interval) VALUES {0} ' \
                           'ON CONFLICT ON CONSTRAINT unique_message' \
                           ' DO UPDATE SET amount = messages.amount + EXCLUDED.amount;'
            user_command = user_command.format(', '.join(user_values))
            con.execute(user_command)

    async def flat_details(self, guild_id, days, con):
        interval = f"INTERVAL '{days} DAYS'"
        command = f"DELETE FROM messages WHERE time <= NOW() at time zone 'utc' - {interval} AND guild_id = {guild_id} RETURNING *;"
        con.execute(command)
        entries = con.fetchall()
        channels = Counter()
        for e in entries:
            if e['channel_id'] is not None:
                channels[(e['time'], e['interval'])] += e['amount']
        if len(channels) > 0:
            value = '({0}, {1}, {2}, {3})'
            channel_values = []
            for time, interval in channels.keys():
                amount = channels[(time, interval)]
                channel_values.append(
                    value.format(str(guild_id), str(amount), f"TIMESTAMP '{time}'", f"INTERVAL '{interval}'"))

            channel_command = 'INSERT INTO messages(guild_id, amount, time, interval) VALUES {0} ' \
                              'ON CONFLICT ON CONSTRAINT unique_message' \
                              ' DO UPDATE SET amount = messages.amount + EXCLUDED.amount;'
            channel_command = channel_command.format(', '.join(channel_values))
            con.execute(channel_command)


def setup(bot):
    bot.add_cog(Messages(bot))

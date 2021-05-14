import datetime
from collections import Counter

from discord.ext import commands
import discord
import bot.util.database as db
from bot.util.context import Context
import bot.util.storage_cache as storage_cache

import bot.util.time_util as tutil


class MessagesTable(db.Table, table_name='messages'):
    guild_id = db.Column(db.Integer(big=True), nullable=False, index=True)
    channel_id = db.Column(db.Integer(big=True), nullable=False)
    user_id = db.Column(db.Integer(big=True), nullable=False)
    amount = db.Column(db.Integer(small=True), nullable=False, default="1")
    time = db.Column(db.Datetime(), default="date_trunc('hour', now()) at time zone 'utc'", index=True)

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)

        # create the indexes
        sql = "ALTER TABLE messages DROP CONSTRAINT IF EXISTS unique_message;" \
              "ALTER TABLE messages ADD CONSTRAINT unique_message UNIQUE (channel_id, user_id, time);"

        return statement + '\n' + sql


class Messages(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_loop("messagepush", self.update_loop)
        self.cache = Counter()
        self.cooldown = storage_cache.ExpiringDict(60)

    def cog_unload(self):
        self.bot.remove_loop("messagepush")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.channel is None or message.author.bot:
            return
        if message.author.id in self.cooldown:
            return
        self.cache[(message.guild.id, message.channel.id, message.author.id)] += 1
        self.cooldown[message.author.id] = 1

    async def update_loop(self, time: datetime.datetime):
        if time.minute % 5 == 0:
            await self.push()

    @commands.command(name="*messagepush", hidden=True)
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
        value = "({0}, {1}, {2}, {3}, {4})"
        for data, amount in self.cache.items():
            insert.append(value.format(str(data[0]), str(data[1]), str(data[2]), amount, time_str))

        command = "INSERT INTO messages(guild_id, channel_id, user_id, amount, time) VALUES {0} " \
                  "ON CONFLICT ON CONSTRAINT unique_message" \
                  " DO UPDATE SET amount = messages.amount + EXCLUDED.amount;"
        command = command.format(", ".join(insert))
        async with db.MaybeAcquire() as con:
            con.execute(command)
        self.cache.clear()


def setup(bot):
    bot.add_cog(Messages(bot))

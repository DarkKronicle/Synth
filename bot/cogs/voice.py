from dateutil.tz import gettz
from discord.ext import commands
import discord
import bot.util.database as db
from datetime import datetime
import bot.util.time_util as tutil


from bot import synth_bot


class VoiceTable(db.Table, table_name="voice"):
    guild_id = db.Column(db.Integer(big=True), index=True, nullable=False)
    channel_id = db.Column(db.Integer(big=True), nullable=False)
    user_id = db.Column(db.Integer(big=True), nullable=False)
    time = db.Column(db.Datetime(), nullable=False, default="now() at time zone 'utc'")
    amount = db.Column(db.Interval(), default="'1 minute'", nullable=False)

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)

        # create the indexes
        sql = "ALTER TABLE voice DROP CONSTRAINT IF EXISTS unique_voice;" \
              "ALTER TABLE voice ADD CONSTRAINT unique_voice UNIQUE (channel_id, user_id, time);"

        return statement + '\n' + sql


class VoiceLog:
    __slots__ = ('member_id', 'channel_id', 'guild_id', 'start', 'stop')

    def __init__(self, member_id, channel_id, guild_id):
        self.member_id = member_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.start = tutil.round_time(datetime.now(gettz('UTC')), 1)
        self.stop = None

    def has_stopped(self):
        if self.stop is None:
            return False
        return True

    def force_stop(self):
        self.stop = tutil.round_time(datetime.now(gettz('UTC')), 1)

    def stopped_or_now(self):
        if self.has_stopped():
            return self.stop
        return datetime.now(gettz('UTC'))


class Voice(commands.Cog):

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot
        self.cache = []
        self.setup = False
        self.bot.add_loop("voiceupdate", self.update_loop)

    async def update_loop(self, time):
        if not self.setup:
            self.setup = True
            self.setup_voice()
        if time.minute % 5 == 0:
            await self.push()

    def cog_unload(self):
        self.bot.remove_loop("voiceupdate")

    def setup_voice(self):
        for g in self.bot.guilds:
            g: discord.Guild
            for v in g.voice_channels:
                v: discord.VoiceChannel
                for m in v.members:
                    if self.should_member_log(m):
                        self.cache.append(VoiceLog(m.id, v.id, g.id))

    async def push(self):
        if len(self.cache) == 0:
            return
        elements = []
        element_format = "({0}, {1}, {2}, {3}, {4})"
        for c in self.cache:
            dif = c.stopped_or_now() - c.start
            minutes = dif.total_seconds() // 60
            if minutes < 1:
                continue
            time_str = c.start.strftime("'%Y-%m-%d %H:%M:%S'")
            elements.append(element_format.format(c.guild_id, c.channel_id, c.member_id, time_str, f"'{dif.total_seconds()} SECONDS'"))
        if len(elements) == 0:
            return
        command = "INSERT INTO voice(guild_id, channel_id, user_id, time, amount) VALUES {0} " \
                  "ON CONFLICT ON CONSTRAINT unique_voice" \
                  " DO UPDATE SET amount = EXCLUDED.amount;"
        command = command.format(', '.join(elements))
        async with db.MaybeAcquire() as con:
            con.execute(command)
        self.cache = [c for c in self.cache if not c.has_stopped()]

    @commands.command(name="*voicepush")
    @commands.is_owner()
    async def voice_push(self, ctx):
        await self.push()
        await ctx.check(0)

    def should_member_log(self, member: discord.Member):
        if member.bot:
            return False
        return True

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not self.should_member_log(member):
            return

        if after.channel is None:
            for c in self.cache:
                if c.member_id == member.id and not c.has_stopped():
                    c.force_stop()
            return

        if after.afk:
            return

        if before.channel is None:
            self.cache.append(VoiceLog(member.id, after.channel.id, after.channel.guild.id))
            return

        if after.channel != before.channel:
            for c in self.cache:
                if c.member_id == member.id and not c.has_stopped():
                    c.force_stop()
            self.cache.append(VoiceLog(member.id, after.channel.id, after.channel.guild.id))
            return


def setup(bot):
    bot.add_cog(Voice(bot))

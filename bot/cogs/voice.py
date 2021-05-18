from bot.util import database as db
from bot.util import time_util as tutil
import discord
from bot import synth_bot
from discord.ext import commands


class VoiceTable(db.Table, table_name='voice'):
    guild_id = db.Column(db.Integer(big=True), index=True, nullable=False)
    channel_id = db.Column(db.Integer(big=True), nullable=False)
    user_id = db.Column(db.Integer(big=True), nullable=False)
    time = db.Column(db.Datetime(), nullable=False, default="now() at time zone 'utc'")
    amount = db.Column(db.Interval(), default="'1 minute'", nullable=False)

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)

        # create the constraints
        sql = 'ALTER TABLE voice DROP CONSTRAINT IF EXISTS unique_voice; ALTER TABLE voice ADD CONSTRAINT unique_voice UNIQUE (channel_id, user_id, time);'

        return '{0}\n{1}'.format(statement, sql)


class VoiceLog:
    __slots__ = ('member_id', 'channel_id', 'guild_id', 'start', 'stop')

    def __init__(self, member_id, channel_id, guild_id):
        self.member_id = member_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.start = tutil.round_time(tutil.get_utc(), 1)
        self.stop = None

    def has_stopped(self):
        return self.stop is not None

    def force_stop(self):
        self.stop = tutil.round_time(tutil.get_utc(), 1)

    def stopped_or_now(self):
        if self.has_stopped():
            return self.stop
        return tutil.get_utc()


class Voice(commands.Cog):

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot
        self.cache = []
        self.setup = False
        self.bot.add_loop('voiceupdate', self.update_loop)

    async def update_loop(self, time):
        if not self.setup:
            self.setup = True
            self.setup_voice()
        if time.minute % 5 == 0:
            await self.push()

    def cog_unload(self):
        self.bot.remove_loop('voiceupdate')

    async def push(self):
        if not self.cache:
            return
        elements = []
        element_format = '({0}, {1}, {2}, {3}, {4})'
        for cached in self.cache:
            dif = cached.stopped_or_now() - cached.start
            minutes = dif.total_seconds() // 60
            if minutes < 1:
                continue
            time_str = cached.start.strftime("'%Y-%m-%d %H:%M:%S'")
            elements.append(
                element_format.format(
                    cached.guild_id,
                    cached.channel_id,
                    cached.member_id,
                    time_str,
                    "{0} SECONDS'".format(dif.total_seconds()),
                ),
            )
        if not elements:
            return
        command = 'INSERT INTO voice(guild_id, channel_id, user_id, time, amount) VALUES {0} ON CONFLICT ON CONSTRAINT unique_voice DO UPDATE SET amount = EXCLUDED.amount;'
        command = command.format(', '.join(elements))
        async with db.MaybeAcquire() as con:
            con.execute(command)
        self.cache = [cached for cached in self.cache if not cached.has_stopped()]  # noqa: WPS441

    @commands.command(name='*voicepush', hidden=True)
    @commands.is_owner()
    async def voice_push(self, ctx):
        """Updates voice chat information in the database."""
        await self.push()
        await ctx.check(0)

    def should_member_log(self, member: discord.Member):
        return not member.bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not self.should_member_log(member):
            return

        if after.channel is None:
            self.update_disconnect(member, after, before)
            return

        if after.afk:
            return

        if before.channel is None:
            self.update_new(member, after, before)
            return

        if after.channel != before.channel:
            self.update_switch(member, after, after)
            return

    def update_disconnect(self, member, after, before):
        for cached in self.cache:
            if cached.member_id == member.id and not cached.has_stopped():
                cached.force_stop()

    def update_new(self, member, after, before):
        self.cache.append(VoiceLog(
            member.id,
            after.channel.id,
            after.channel.guild.id,
        ))

    def update_switch(self, member, after, before):
        for cached in self.cache:
            if cached.member_id == member.id and not cached.has_stopped():
                cached.force_stop()
        self.cache.append(VoiceLog(
            member.id,
            after.channel.id,
            after.channel.guild.id,
        ))

    def setup_voice(self):
        for guild in self.bot.guilds:
            for voice in guild.voice_channels:
                self._set_channel(voice)

    def _set_channel(self, voice):
        for member in voice.members:
            if self.should_member_log(member):
                self.cache.append(VoiceLog(member.id, voice.id, voice.guild.id))


def setup(bot):
    bot.add_cog(Voice(bot))

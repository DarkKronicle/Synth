import typing

from bot.util import database as db
import discord
from discord.ext import commands
from enum import Enum
from bot.cogs.channels import *
from bot.util.context import Context


class ChannelTypes(Enum):
    members = 0
    messages = 1
    voice = 2

    @classmethod
    def to_class(cls, number):
        if number == ChannelTypes.messages:
            return MessagesChannel()
        return None


class StatChannelsTable(db.Table, table_name='stat_channels'):
    guild_id = db.Column(db.Integer(big=True), unique=True, nullable=False)
    channel_id = db.Column(db.Integer(big=True), unique=True, nullable=False)
    type = db.Column(db.Integer(small=True), nullable=False)
    name = db.Column(db.String())
    arguments = db.Column(db.String())


class StatChannels(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_loop('statchannels', self.channel_loop)

    def cog_unload(self):
        self.bot.remove_loop('statchannels')

    @commands.command(name='*refresh', hidden=True)
    @commands.is_owner()
    async def refresh(self, ctx):
        """Forces a refresh of the statistic channels"""
        await self.refresh_channels()
        await ctx.check(0)

    async def channel_loop(self, time):
        if time.minute % 30 == 0:
            await self.refresh_channels()

    @commands.command(name="*create", hidden=True)
    @commands.is_owner()
    async def create_default(self, ctx: Context, channel: typing.Union[discord.VoiceChannel, discord.TextChannel], *, text: str = "{0}"):
        await ChannelTypes.to_class(ChannelTypes.members).create(ctx, channel, text)

    async def refresh_channels(self):
        to_edit = []
        async with db.MaybeAcquire() as con:
            command = "SELECT * FROM stat_channels;"
            con.execute(command)
            entries = con.fetchall()
            for entry in entries:
                guild_id = entry['guild_id']
                channel_id = entry['channel_id']
                channel_type = entry['type']
                name = entry['name']
                arguments = entry['arguments']
                try:
                    converter = ChannelTypes.to_class(
                        ChannelTypes(channel_type),
                    )
                except KeyError:
                    continue
                channel_name = await converter.name_from_sql(guild_id, channel_id, name, arguments, con)
                to_edit.append((guild_id, channel_id, channel_name))

        for guild_id, channel_id, new_name in to_edit:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            channel = guild.get_channel(channel_id)
            if channel is None:
                continue
            await channel.edit(name=new_name)


def setup(bot):
    bot.add_cog(StatChannels(bot))

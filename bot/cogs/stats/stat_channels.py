import typing

import discord

from bot.util import database as db, checks
from discord.ext import commands
from enum import Enum
from bot.cogs.stats.channels import *
from bot.util.context import Context
from bot.util.paginator import Prompt


class ChannelTypes(Enum):
    members = 0
    messages = 1
    voice = 2

    @classmethod
    def to_class(cls, number):
        if number == ChannelTypes.messages:
            return MessageStatChannel()
        if number == ChannelTypes.voice:
            return VoiceStatChannel()
        return None


class StatChannelsTable(db.Table, table_name='stat_channels'):
    id = db.Column(db.Integer(auto_increment=True), nullable=False)
    guild_id = db.Column(db.Integer(big=True), nullable=False)
    channel_id = db.Column(db.Integer(big=True), nullable=False)
    type = db.Column(db.Integer(small=True), nullable=False)
    name = db.Column(db.String())
    arguments = db.Column(db.String())

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)
        sql = 'ALTER TABLE stat_channels DROP CONSTRAINT IF EXISTS one_channel;' \
              'ALTER TABLE stat_channels ADD CONSTRAINT one_channel UNIQUE (guild_id, channel_id);'

        return statement + '\n' + sql


class StatChannels(commands.Cog):
    """Modifying and interacting with stat channels."""

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

    @commands.group(name='!channels', aliases=['!channel'])
    @checks.is_manager_or_perms()
    @commands.guild_only()
    async def channels(self, ctx: Context):
        """View and configure statistic channels."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help('!channels')

    @channels.command(name='list')
    async def list_channels(self, ctx: Context):
        """
        List's the current stat channels for the server.
        """
        command = 'SELECT * FROM stat_channels WHERE guild_id = {0};'
        async with db.MaybeAcquire() as con:
            con.execute(command.format(ctx.guild.id))
            entries = con.fetchall()
        message = []
        for e in entries:
            channel_type = e['type']
            try:
                converter = ChannelTypes.to_class(ChannelTypes(channel_type))
            except KeyError:
                message.append('Error on {0}'.format(e['guild_id']))
                continue
            message.append('{1} (id {0})'.format(
                e['id'],
                await converter.get_info(e['guild_id'], e['channel_id'], e['name'], e['arguments']),
            ))
        await ctx.send(embed=ctx.create_embed(description='\n'.join(message)))

    @channels.command(name="delete")
    @commands.cooldown(1, 10)
    async def delete_channel(self, ctx: Context, id: int):
        """
        Delete's a statistic channel.

        This will not delete the channel, just remove it from being updated. For ID use the ID from `!channels list`.

        Examples:
            delete 581
            delete 763
        """
        command = 'SELECT * FROM stat_channels WHERE guild_id = {0} AND id = {1};'
        async with db.MaybeAcquire() as con:
            con.execute(command.format(ctx.guild.id, id))
            entry = con.fetchone()
        if entry is None:
            return await ctx.send(embed=ctx.create_embed("That channel doesn't exist!", error=True))
        page = Prompt('Are you sure you want to stat channel <#{0}>?\n\n*This will not delete the channel'.format(entry['channel_id']))
        await page.start(ctx)
        result = page.result
        if not result:
            return await ctx.send(embed=ctx.create_embed('Cancelled!'))
        command = 'DELETE FROM stat_channels WHERE guild_id = {0} AND id = {1};'
        async with db.MaybeAcquire() as con:
            con.execute(command.format(ctx.guild.id, id))
        await ctx.send(embed=ctx.create_embed('Deleted!'))

    @channels.command(name="create")
    @commands.cooldown(1, 10)
    async def create(self, ctx: Context, channel: typing.Union[discord.VoiceChannel, discord.TextChannel, discord.StageChannel, discord.CategoryChannel]):
        """
        Opens a setup wizard to create a custom statistic channel.

        Specify the channel you want to turn into a stat channel by name, mention, or ID.

        Examples:
            create #general
            create 876862851543251438
            create general
        """
        if channel is None:
            return await ctx.send(embed=ctx.create_embed('You have to specify a channel to convert!', error=True))
        count_command = 'SELECT COUNT(id) FROM stat_channels WHERE guild_id = {0};'.format(ctx.guild.id)
        already_command = 'SELECT COUNT(id) FROM stat_channels WHERE guild_id = {0} AND channel_id = {1};'
        async with db.MaybeAcquire() as con:
            con.execute(already_command.format(ctx.guild.id, channel.id))
            already = con.fetchone()
            con.execute(count_command)
            entry = con.fetchone()
        if already['count'] != 0:
            return await ctx.send(embed=ctx.create_embed("You can't have multiple stat channels on one channel!", error=True))
        if entry['count'] > 7:
            return await ctx.send(embed=ctx.create_embed("You have too many stat channels set up!", error=True))
        descriptions = []
        for e in ChannelTypes:
            channel_type = ChannelTypes.to_class(e)
            if channel_type is not None:
                descriptions.append('`{0}.` {1}'.format(e.value, channel_type.get_standard_description()))
        result = await ctx.ask(embed=ctx.create_embed(
            'What channel type do you want to make? Send the number.\n\n{0}'.format('\n'.join(descriptions)),
        ))
        if result is None or result == '':
            return await ctx.send(embed=ctx.create_embed('Cancelled!'))
        try:
            type_num = int(result.split(' ')[0])
        except ValueError:
            return await ctx.send(embed=ctx.create_embed('`{0}` is not a number!'.format(result), error=True)),
        try:
            converter = ChannelTypes.to_class(ChannelTypes(type_num))
        except:
            return await ctx.send(embed=ctx.create_embed(
                '`{0}` is not a proper channel type!'.format(result), error=True),
            )
        await converter.create(ctx, channel)


def setup(bot):
    bot.add_cog(StatChannels(bot))

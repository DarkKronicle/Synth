"""
Class for user's managing data that is maintained by the bot.
"""
import csv
from io import StringIO

import discord
import typing

from bot.util import checks, paginator
from bot.util import database as db
from bot.util.context import Context
from discord.ext import commands

from bot.util.time_util import IntervalConverter


def get_row(guild, entry):
    channel_id = entry['channel_id']
    user_id = entry['user_id']
    channel = guild.get_channel(channel_id) or channel_id
    user = guild.get_member(user_id) or user_id
    return [channel, user, entry['amount'], entry['time']]


class Data(commands.Cog):   # noqa: WPS110
    """Manage data stored in the bot."""

    def __init__(self, bot):
        """
        Initiates the Cog
        :param bot: SynthBot
        """
        self.bot = bot

    @commands.group(name='@data')
    @checks.is_admin()
    async def data_command(self, ctx: Context):
        """
        Manage's what data is stored on Synth
        """
        if not ctx.invoked_subcommand:
            await ctx.send_help('@data')

    @data_command.command(name='purgein', aliases=['purgelast'])
    async def purge_last(
            self,
            ctx: Context,
            selection: typing.Optional[typing.Union[discord.User, discord.TextChannel, discord.VoiceChannel, discord.StageChannel]] = None,
            *,
            interval: typing.Optional[IntervalConverter] = None,
    ):
        """
        Delete's data from the database from the `selection` in the past `interval`.

        Selection can be a user, text channel, voice channel, or nothing (guild).

        Interval can be days, months, weeks, or years.

        Examples:
            purgein @DarkKronicle 1 day (delete's everything from DarkKronicle in one day)
            purgein #bots (delete's everything from bots)
        """
        if selection is None:
            format_selection = 'the whole guild'
        else:
            format_selection = selection.mention
        if interval is None:
            format_interval = 'all of time'
        else:
            format_interval = 'the past {0}'.format(interval)
        prompt = paginator.Prompt('Are you sure you want to delete all data from {0} for {1}?'.format(format_selection, format_interval))
        try:
            await prompt.start(ctx)
        except:
            pass
        if not prompt.result:
            return await ctx.send(embed=ctx.create_embed('Cancelled!', error=True))
        # Create messages command
        command = '{0}\n{1}'.format(
            self.purge_message(False, interval, ctx.guild.id, selection),
            self.purge_voice(False, interval, ctx.guild.id, selection),
        )

        # Create voice command
        async with db.MaybeAcquire(pool=self.bot.pool) as con:
            await con.execute(command)

        await ctx.send(embed=ctx.create_embed('Deleted all data from {0} for {1}'.format(format_selection, format_interval)))

    @data_command.command(name='purgebefore', aliases=['purgepast'])
    @commands.cooldown(1, 60, type=commands.BucketType.guild)
    async def purge_before(
            self,
            ctx: Context,
            selection: typing.Optional[
                typing.Union[discord.User, discord.TextChannel, discord.VoiceChannel, discord.StageChannel]] = None,
            *,
            interval: typing.Optional[IntervalConverter] = None,
    ):
        """
        Delete's data from the database from the `selection` after the past `interval`.

        Selection can be a user, text channel, voice channel, or nothing (guild).

        Interval can be days, months, weeks, or years.

        Examples:
            purgebefore 1 day (delete's everything before 1 day)
            purgebefore @DarkKronicle (delete's everything form DarkKronicle)
        """
        if selection is None:
            format_selection = 'the whole guild'
        else:
            format_selection = selection.mention
        if interval is None:
            format_interval = 'all of time'
        else:
            format_interval = 'before {0}'.format(interval)
        prompt = paginator.Prompt(
            'Are you sure you want to delete all data from {0} for {1}?'.format(format_selection, format_interval))
        try:
            await prompt.start(ctx)
        except:
            pass
        if not prompt.result:
            return await ctx.send(embed=ctx.create_embed('Cancelled!', error=True))

        command = '{0}\n{1}'.format(
            self.purge_message(True, interval, ctx.guild.id, selection),
            self.purge_voice(True, interval, ctx.guild.id, selection),
        )

        # Create voice command
        async with db.MaybeAcquire(pool=self.bot.pool) as con:
            await con.execute(command)

        await ctx.send(
            embed=ctx.create_embed('Deleted all data from {0} for {1}'.format(format_selection, format_interval)))

    @commands.group(name='!export')
    @checks.is_manager_or_perms()
    async def export(
            self,
            ctx: Context,
    ):
        """Export command for server information."""

    @export.command(name='all')
    @commands.cooldown(1, 60, type=commands.BucketType.guild)
    async def export_all(self, ctx: Context):
        """Exports all message data in the form of a CSV."""
        await ctx.trigger_typing()

        buffer = StringIO()
        writer = csv.writer(buffer)
        entries = await self.get_all_guild_entries(ctx.guild.id)
        for entry in entries:
            writer.writerow(get_row(ctx.guild, entry))
        buffer.seek(0)
        export_content = "Here's the data for {0}! Total of `{1}` entries.".format(ctx.guild.name, len(entries))
        await ctx.send(
            export_content,
            file=discord.File(fp=buffer, filename='data.csv'),
        )

    async def get_all_guild_entries(self, guild_id):
        command = 'SELECT * FROM messages WHERE guild_id = {0};'
        async with db.MaybeAcquire(pool=self.bot.pool) as con:
            return await con.fetch(command.format(str(guild_id)))

    def purge_message(self, before, interval, guild_id, selection):
        builder = ['DELETE FROM messages WHERE guild_id = {0}'.format(guild_id)]
        deliminator = '<' if before else '>='
        if interval is not None:
            builder.append("time {0} NOW() at time zone 'utc' - INTERVAL '{1}'".format(deliminator, interval))
        if selection is not None:
            if isinstance(selection, (discord.User,)):
                builder.append('user_id = {0}'.format(selection.id))
            else:
                builder.append('channel_id = {0}'.format(selection.id))

        return '{0};'.format(' AND '.join(builder))

    def purge_voice(self, before, interval, guild_id, selection):
        voice_builder = ['DELETE FROM voice WHERE guild_id = {0}'.format(guild_id)]
        deliminator = '<' if before else '>='
        if interval is not None:
            voice_builder.append("time + amount {0} NOW() at time zone 'utc' - INTERVAL '{1}'".format(deliminator, interval))
        if selection is not None:
            if isinstance(selection, (discord.User,)):
                voice_builder.append('user_id = {0}'.format(selection.id))
            else:
                voice_builder.append('channel_id = {0}'.format(selection.id))
        return '{0};'.format(' AND '.join(voice_builder))


def setup(bot):
    bot.add_cog(Data(bot))

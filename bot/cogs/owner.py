import copy
import datetime
import importlib
import os
import re
import subprocess
import sys
import textwrap
import traceback

import asyncio
import discord
import typing

from bot import synth_bot
from discord.ext import commands, menus

from bot.cogs import command_config
from bot.util.context import Context


class GlobalChannel(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            return await commands.TextChannelConverter().convert(ctx, argument)
        except commands.BadArgument:
            # Not found... so fall back to ID + global lookup
            try:
                channel_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f'Could not find a channel by ID {argument!r}.')
            else:
                channel = ctx.bot.get_channel(channel_id)
                if channel is None:
                    raise commands.BadArgument(f'Could not find a channel by ID {argument!r}.')
                return channel


class Owner(commands.Cog):
    """Settings for the bot owner."""
    # Created based off of https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/admin.py
    # MPL v2

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot
        self.degrees = 0

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    async def get_guild_embed(self, guild: discord.Guild, *, embed=None):
        if embed is None:
            embed = discord.Embed(title='Guild Information', colour=discord.Colour.purple())
        embed.add_field(
            name='Name/ID',
            value='{0} (ID: `{1}`'.format(guild.name, str(guild.id)),
        )
        embed.add_field(
            name='Owner',
            value='{0} (ID: `{1}`'.format(str(guild.owner), guild.owner.id),
        )
        total = guild.member_count
        bots = sum(member.bot for member in guild.members)
        text = 0
        voice = 0
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                text = text + 1
            elif isinstance(channel, discord.VoiceChannel):
                voice = voice + 1
        message = 'Text Channels: `{text}`\nVoice Channels: `{voice}`\nTotal Channels: `{all}`\n\nMembers: `{members}`\nBots: `{bots}`'
        message = message.format(
            text=text,
            voice=voice,
            all=text + voice,
            members=total,
            bots=bots,
        )
        embed.description = message
        if guild.icon:
            embed.set_thumbnail(url=guild.icon_url)

        if guild.me:
            embed.timestamp = guild.me.joined_at

        return embed

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        embed = await self.get_guild_embed(
            guild,
            embed=discord.Embed(title='New Guild!', colour=discord.Colour.green()),
        )
        await self.bot.log.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        embed = await self.get_guild_embed(
            guild,
            embed=discord.Embed(title='Left Guild', colour=discord.Colour.red()),
        )
        await self.bot.log.send(embed=embed)

    async def run_process(self, command):
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]

    @commands.command(hidden=True, name='load')
    async def load(self, ctx, *, module):
        """Loads a module."""
        try:
            self.bot.load_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.command(hidden=True, name='*unload')
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        try:
            self.bot.unload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @commands.group(name='*reload', hidden=True, invoke_without_command=True)
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        try:
            self.bot.reload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')

    _GIT_PULL_REGEX = re.compile(r'\s*(?P<filename>.+?)\s*\|\s*[0-9]+\s*[+-]+')

    def find_modules_from_git(self, output):
        files = self._GIT_PULL_REGEX.findall(output)
        ret = []
        for file in files:
            root, ext = os.path.splitext(file)
            if ext != '.py':
                continue

            if root.startswith('cogs/'):
                # A submodule is a directory inside the main cog directory for
                # my purposes
                ret.append((root.count('/') - 1, root.replace('/', '.')))

        # For reload order, the submodules should be reloaded first
        ret.sort(reverse=True)
        return ret

    def reload_or_load_extension(self, module):
        try:
            self.bot.reload_extension(module)
        except commands.ExtensionNotLoaded:
            self.bot.load_extension(module)

    @_reload.command(name='all', hidden=True)
    async def _reload_all(self, ctx):
        """Reloads all modules, while pulling from git."""

        async with ctx.typing():
            stdout, stderr = await self.run_process('git pull')

        # progress and stuff is redirected to stderr in git pull
        # however, things like "fast forward" and files
        # along with the text "already up-to-date" are in stdout

        if stdout.startswith('Already up-to-date.'):
            return await ctx.send(stdout)

        modules = self.find_modules_from_git(stdout)
        mods_text = '\n'.join(f'{index}. `{module}`' for index, (_, module) in enumerate(modules, start=1))
        prompt_text = f'This will update the following modules, are you sure?\n{mods_text}'
        confirm = await ctx.prompt(prompt_text, reacquire=False)
        if not confirm:
            return await ctx.send('Aborting.')

        statuses = []
        for is_submodule, module in modules:
            if is_submodule:
                try:
                    actual_module = sys.modules[module]
                except KeyError:
                    statuses.append((ctx.check(None), module))
                else:
                    try:
                        importlib.reload(actual_module)
                    except Exception as e:
                        statuses.append((ctx.check(False), module))
                    else:
                        statuses.append((ctx.check(True), module))
            else:
                try:
                    self.reload_or_load_extension(module)
                except commands.ExtensionError:
                    statuses.append((ctx.check(False), module))
                else:
                    statuses.append((ctx.check(True), module))

        await ctx.send(embed=ctx.create_embed('\n'.join(f'{status}: `{module}`' for status, module in statuses)))

    @commands.command(hidden=True, name='*sudo')
    async def sudo(self, ctx, channel: typing.Optional[GlobalChannel], who: typing.Union[discord.Member, discord.User], *, command: str):
        """Run a command as another user optionally in another channel."""
        msg = copy.copy(ctx.message)
        channel = channel or ctx.channel
        msg.channel = channel
        msg.author = who
        msg.content = ctx.prefix + command
        new_ctx: Context = await self.bot.get_context(msg, cls=type(ctx))
        new_ctx.permissions = await command_config.get_perms(self.bot, new_ctx)
        if not await new_ctx.is_allowed():
            return
        await self.bot.invoke(new_ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if not isinstance(error, (commands.CommandInvokeError, commands.ConversionError)):
            return

        error = error.original
        if isinstance(error, (discord.Forbidden, discord.NotFound, menus.MenuError)):
            return

        e = discord.Embed(title='Command Error', colour=0xcc3366)
        e.add_field(name='Name', value=ctx.command.qualified_name)
        e.add_field(name='Author', value=f'{ctx.author} (ID: {ctx.author.id})')

        fmt = f'Channel: {ctx.channel} (ID: {ctx.channel.id})'
        if ctx.guild:
            fmt = f'{fmt}\nGuild: {ctx.guild} (ID: {ctx.guild.id})'

        e.add_field(name='Location', value=fmt, inline=False)
        e.add_field(name='Content', value=textwrap.shorten(ctx.message.content, width=512))

        exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
        e.description = f'```py\n{exc}\n```'
        e.timestamp = datetime.datetime.utcnow()
        await self.bot.log.send(embed=e)


def setup(bot):
    bot.add_cog(Owner(bot))

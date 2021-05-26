import math
import traceback
from datetime import datetime

import bot
from bot.util import database as db
from bot.util import storage_cache as cache
from bot.util import time_util as tutil
import discord
from bot.cogs.help import HelpCommand
from bot.util.context import Context
from discord.ext import commands, tasks
import logging

cogs_dir = 'bot.cogs'
startup_extensions = [
    'utility', 'stats.messages', 'stats.statistics', 'stats.voice',
    'owner', 'guild_config', 'stats.stat_channels', 'data',
    'stats.members', 'reaction_roles',
]
description = 'The open source discord statistic bot.'
main_color = discord.Colour(0x9d0df0)

error_timeout = 15
settings_cache = 640
send_error = (
    commands.ArgumentParsingError,
    commands.BadArgument,
    commands.MemberNotFound,
    commands.ChannelNotFound,
    commands.BadUnionArgument,
    commands.MissingRequiredArgument,
)


async def get_prefix(bot_obj, message: discord.Message):
    user_id = bot_obj.user.id
    prefixes = ['s~', '<@{0}> '.format(user_id)]
    space = ['s~ ', '<@{0}> '.format(user_id)]
    if message.guild is None:
        prefix = '~'
    else:
        prefix = await bot_obj.get_guild_prefix(message.guild.id)
        if prefix is None:
            prefix = '~'
    message_content: str = message.content
    if message_content.startswith('s~ '):
        return space
    if message_content.startswith('{0} '.format(prefix)):
        space.append('{0} '.format(prefix))
        return space
    prefixes.append(prefix)
    return prefixes


class SynthBot(commands.Bot):

    def __init__(self):
        logging.info('Loading bot...')
        self.loops = {}
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)

        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            description=description,
            case_insensitive=True,
            owner_id=bot.config['owner_id'],
            allowed_mentions=allowed_mentions,
        )
        self.boot = datetime.now()
        self.help_command = HelpCommand()
        for extension in startup_extensions:
            try:
                self.load_extension('{0}.{1}'.format(cogs_dir, extension))

            except (discord.ClientException, ModuleNotFoundError):
                logging.warning('Failed to load extension {0}.'.format(extension))
                traceback.print_exc()
        self.add_loop("presence", self.presence_loop)

    def run(self):
        super().run(bot.config['bot_token'], reconnect=True)

    async def on_command_error(self, ctx: Context, error):  # noqa: WPS217
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CheckFailure):
            return
        if isinstance(error, commands.CommandOnCooldown):
            if await self.is_owner(ctx.author):
                # We don't want the owner to be on cooldown.
                await ctx.reinvoke()
                return
            # Let people know when they can retry
            embed = ctx.create_embed(
                title='Command On Cooldown!',
                description='This command is currently on cooldown. Try again in `{0}` seconds.'.format(math.ceil(error.retry_after)),
                error=True,
            )
            await ctx.delete()
            await ctx.send(embed=embed, delete_after=error_timeout)
            return
        if isinstance(error, send_error):
            await ctx.send(embed=ctx.create_embed(description=str(error), error=True), delete_after=error_timeout)
            await ctx.delete()
            return
        raise error

    @cache.cache(maxsize=settings_cache)
    async def get_guild_prefix(self, guild_id):
        command = 'SELECT prefix FROM guild_config WHERE guild_id = {0};'
        command = command.format(guild_id)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            row = con.fetchone()
        if row is None:
            return None
        return row['prefix']

    async def on_ready(self):
        self.setup_loop.start()
        await self.update_presence()
        logging.info('Bot up and running!')

    async def process_commands(self, message):
        if message.author.bot:
            return

        ctx: Context = await self.get_context(message, cls=Context)

        if ctx.command is None:
            return

        await self.invoke(ctx)
        ctx.release()

    def add_loop(self, name, function):
        """
        Adds a loop to the thirty minute loop. Needs to take in a function with a parameter time with async.
        """
        self.loops[name] = function

    def remove_loop(self, name):
        """
        Removes a loop based off of a time.
        """
        if name in self.loops:
            self.loops.pop(name)

    @tasks.loop(minutes=1)
    async def time_loop(self):
        time = tutil.round_time(round_to=60)
        for _, function in self.loops.items():
            try:
                await function(time)
            except Exception as error:
                if isinstance(error, (discord.Forbidden, discord.errors.Forbidden)):
                    return
                traceback.print_exc()

    first_loop = True

    @tasks.loop(seconds=tutil.get_time_until_minute())
    async def setup_loop(self):
        # Probably one of the most hacky ways to get a loop to run every thirty minutes based
        # off of starting on one of them.
        if SynthBot.first_loop:
            SynthBot.first_loop = False
            return
        self.time_loop.start()
        self.setup_loop.stop()

    def get_cog(self, name):
        lower = name.lower()
        for cog in self.cogs.keys():
            if cog.lower() == lower:
                return self.cogs[cog]
        return None

    @discord.utils.cached_property
    def log(self):
        return self.get_channel(bot.config['log_channel'])

    async def presence_loop(self, time):
        if time.minute == 0:
            await self.update_presence()

    async def update_presence(self):
        command = "SELECT SUM(amount) FROM messages WHERE time >= NOW() at time zone 'utc' - INTERVAL '24 HOURS';"
        amount = 0
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entry = con.fetchone()
        if entry['sum'] is None:
            amount = 0
        else:
            amount = entry['sum']
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="{0} messages".format(amount)))

import discord
import bot.util.time_util as tutil
from discord.ext import commands, tasks
import bot.util.storage_cache as cache
import bot.util.database as db

import bot

from datetime import datetime
import traceback

from bot.util.context import Context

cogs_dir = "bot.cogs"
startup_extensions = ["utility", "messages", "statistics", "voice", "owner", "guild_config"]
description = "Statistics incarnate"


async def get_prefix(bot_obj, message: discord.Message):
    user_id = bot_obj.user.id
    prefixes = ["s~", f"<@{user_id}> ", bot_obj.user.mention + " "]
    space = ["s~ ", f"<@{user_id}> ", bot_obj.user.mention + " "]
    if message.guild is None:
        prefix = "~"
    else:
        prefix = await bot_obj.get_guild_prefix(message.guild.id)
        if prefix is None:
            prefix = "~"
    content: str = message.content
    if content.startswith("s~ "):
        return space
    if content.startswith(prefix + " "):
        space.append(prefix + " ")
        return space
    prefixes.append(prefix)
    return prefixes


class SynthBot(commands.Bot):

    def __init__(self):
        print("Loading bot...")

        self.loops = {}
        allowed_mentions = discord.AllowedMentions(roles=False, everyone=False, users=True)

        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix=get_prefix, intents=intents, description=description,
                         case_insensitive=True, owner_id=bot.config['owner_id'], allowed_mentions=allowed_mentions)
        self.boot = datetime.now()

        for extension in startup_extensions:
            try:
                self.load_extension(cogs_dir + "." + extension)

            except (discord.ClientException, ModuleNotFoundError):
                print(f'Failed to load extension {extension}.')
                traceback.print_exc()

    def run(self):
        super().run(bot.config['bot_token'], reconnect=True)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CheckFailure):
            return
        raise error

    @cache.cache(maxsize=640)
    async def get_guild_prefix(self, guild_id):
        command = "SELECT prefix FROM guild_config WHERE guild_id = {0};"
        command = command.format(guild_id)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            row = con.fetchone()
        if row is None:
            return None
        return row['prefix']

    async def on_ready(self):
        self.setup_loop.start()
        print("Bot up and running!")

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
        for loop in self.loops:
            try:
                await self.loops[loop](time)
            except Exception as error:
                if isinstance(error, (discord.Forbidden, discord.errors.Forbidden)):
                    return
                traceback.print_exc(error)

    first_loop = True

    @tasks.loop(seconds=tutil.get_time_until_minute())
    async def setup_loop(self):
        # Probably one of the most hacky ways to get a loop to run every thirty minutes based
        # off of starting on one of them.
        if self.first_loop:
            self.first_loop = False
            return
        self.time_loop.start()
        self.setup_loop.stop()

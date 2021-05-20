"""
This class was heavily based off of https://github.com/Rapptz/RoboDanny/blob/7cd472ca021e9e166959e91a7ff64036474ea46c/cogs/utils/context.py#L23:1
Rapptz is amazing.
The code above was released under MIT license.
"""
import asyncio
import contextlib

from bot.util import database
import discord
from discord.ext import commands

MAIN_COLOR = discord.Colour(0x9D0DF0)   # noqa: WPS432


class Context(commands.Context):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connection = None

    async def timeout(self, *, delete_after=15):
        """
        Sends a timeout message.
        """
        await self.send(
            'This has been closed due to a timeout {0}.'.format(self.author.mention),
            delete_after=delete_after,
        )

    async def show_help(self, command=None):
        cmd = self.bot.get_command('help')
        command = command or self.command.qualified_name
        await self.invoke(cmd, command=command)

    async def get_dm(self, user=None):
        if user is None:
            user = self.author
        if user.dm_channel is None:
            await user.create_dm()
        return user.dm_channel

    async def delete(self, *, throw_error=False):
        """
        If throw error is false, it will send true/false if success.
        """
        if throw_error:
            await self.message.delete
        else:
            try:
                await self.message.delete()
            except discord.HTTPException:
                return False
        return True

    @property
    def db(self):
        if self.connection is None:
            self.acquire()
        return self.connection.cursor()

    def acquire(self):
        self.connection = database.MaybeAcquire()

    def release(self):
        if self.connection is not None:
            self.connection.release()

    async def check(self, action_result):
        if action_result == 0:
            em = '👍'
        elif action_result == 2:
            em = '<:eyee:840634640549281802>'
        elif action_result == 1:
            em = '😦'
        await self.message.add_reaction(em)

    def create_embed(self, description=discord.Embed.Empty, *, title=discord.Embed.Empty, error=False):
        cmd: commands.Command = self.command
        command_name = '{0} => '.format(cmd.cog_name)
        subs = cmd.qualified_name.split(' ')
        command_name += ' > '.join(subs)
        embed = discord.Embed(
            title=title,
            description=description,
            colour=discord.Colour.red() if error else MAIN_COLOR,
        )
        embed.set_author(name=command_name)
        embed.set_footer(text=str(self.author), icon_url=self.author.avatar_url)
        return embed

    async def ask(self, message=None, *, timeout=60, delete_after=True, author_id=None, allow_none=False, embed=None):
        """
        A function to ask a certain user for an answer using yes/no.
        :param embed: Another argument for the message.
        :param message: String for what the question is.
        :param timeout: How long the bot will wait for.
        :param delete_after: Should the message be deleted after?
        :param author_id: Who should respond. If None it will default to context author.
        :param allow_none: If they can respond with 'none'.
        :return: The author's answer. Returns None if timeout, and False if allow_none is on.
        """
        answer = None
        if message is None and embed is None:
            raise ValueError("Message and embed can't be NoneType!")

        message = await self.send(content=message, embed=embed)

        if author_id is None:
            author_id = self.author.id

        def check(msg):
            nonlocal answer
            if msg.author.id != author_id or msg.channel != message.channel:
                return False

            content = msg.content.lower()
            if "none" == content and allow_none:
                answer = False
                return True

            answer = msg.content
            return True

        try:
            answermsg = await self.bot.wait_for('message', timeout=timeout, check=check)
            if delete_after:
                await answermsg.delete()
        except asyncio.TimeoutError:
            answer = None

        if delete_after:
            with contextlib.suppress(discord.HTTPException):
                await message.delete()

        return answer

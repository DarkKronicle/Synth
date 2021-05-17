"""
This class was heavily based off of https://github.com/Rapptz/RoboDanny/blob/7cd472ca021e9e166959e91a7ff64036474ea46c/cogs/utils/context.py#L23:1
Rapptz is amazing.
The code above was released under MIT license.
"""
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

    def create_embed(self, *, description=discord.Embed.Empty, title=discord.Embed.Empty, error=False):
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

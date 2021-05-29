import discord
from discord.ext import commands


class Members(commands.Cog):
    """Tracks members using the bot."""

    def __init__(self, bot):
        self.bot = bot
        self.to_update = []
        self.bot.add_loop('members', self.update_loop)

    def cog_unload(self):
        self.bot.remove_loop('members')

    async def update_loop(self, time):
        if time.minute == 0:
            await self.update()

    async def update(self):
        self.to_update.clear()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        self.to_update.append(member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self.to_update.append(member.guild.id)


def setup(bot):
    bot.add_cog(Members(bot))

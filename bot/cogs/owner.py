import io

from PIL import Image
from discord.ext import commands

from bot import synth_bot
from bot.util.context import Context


class Owner(commands.Cog):

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot
        self.degrees = 0
        self.bot.add_loop("pfp", self.auto_pfp)

    def cog_unload(self):
        self.bot.remove_loop("pfp")

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    async def auto_pfp(self, time):
        if time.minute == 0:
            self.degrees += 1
            await self.set_pfp_degrees(self.degrees)

    @commands.command(name="*pfp")
    async def set_pfp(self, ctx: Context, degrees: int = 0):
        await self.set_pfp_degrees(degrees)
        await ctx.send("Set my profile pic boss!")

    async def set_pfp_degrees(self, degrees):
        image: Image.Image = Image.open("./resources/discord.png")
        rotated = image.rotate(degrees)

        buffer = io.BytesIO()
        rotated.save(buffer, "PNG")
        buffer.seek(0)
        byte = buffer.read()
        await self.bot.user.edit(avatar=byte)
        return byte


def setup(bot):
    bot.add_cog(Owner(bot))

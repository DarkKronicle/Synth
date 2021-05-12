import bot.util.database as db
from discord.ext import commands
import bot.util.checks as checks
from bot.util.context import Context
import bot.synth_bot as synth_bot


class GuildConfigTable(db.Table, table_name='guild_config'):
    guild_id = db.Column(db.Integer(big=True), unique=True, index=True)
    prefix = db.Column(db.String(length=12), default="s~")


class GuildConfig(commands.Cog):

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot

    @commands.command(name="!prefix")
    @checks.is_mod()
    async def prefix(self, ctx: Context, *, prefix: str = None):
        if prefix is None or len(prefix) > 6 or len(prefix) == 0:
            return await ctx.send("You need to specify a prefix of max length 6 and minimum length 1!")
        command = "INSERT INTO guild_config(guild_id, prefix) VALUES ({0}, %s)" \
                  " ON CONFLICT (guild_id) DO UPDATE SET prefix = EXCLUDED.prefix;"
        command = command.format(str(ctx.guild.id), db.random_key())
        async with db.MaybeAcquire() as con:
            con.execute(command, (prefix,))
        self.bot.get_guild_prefix.invalidate(ctx.guild.id)
        await ctx.send(f"Updated prefix to `{prefix}`")

    @commands.command(name="prefix")
    async def get_prefix(self, ctx: Context):
        prefix = await self.bot.get_guild_prefix(ctx.guild.id)
        if prefix is None:
            prefix = "s~"
        await ctx.send(embed=ctx.create_embed(description=f"Current prefix is: `{prefix}`"))


def setup(bot):
    bot.add_cog(GuildConfig(bot))

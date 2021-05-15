import bot.util.database as db
from discord.ext import commands
import bot.util.checks as checks
from bot.util.context import Context
import bot.synth_bot as synth_bot


class GuildConfigTable(db.Table, table_name='guild_config'):
    guild_id = db.Column(db.Integer(big=True), unique=True, index=True)
    prefix = db.Column(db.String(length=12), default="s~")
    specific_remove = db.Column(db.Integer(small=True), default="7")
    time_remove = db.Column(db.Integer(small=True), default="30")
    detail_remove = db.Column(db.Integer(small=True), default="90")


class GuildConfig(commands.Cog):
    """Configure and view server settings."""

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot

    @commands.command(name="!prefix")
    @checks.is_mod()
    async def prefix(self, ctx: Context, *, prefix: str = None):
        """
        Change's the server's prefix. The global prefix s~ will always be accessible.

        Examples:
              !prefix ~
              !prefix {}
        """
        if prefix is None or len(prefix) > 6 or len(prefix) == 0:
            return await ctx.send("You need to specify a prefix of max length 6 and minimum length 1!")
        command = "INSERT INTO guild_config(guild_id, prefix) VALUES ({0}, %s)" \
                  " ON CONFLICT (guild_id) DO UPDATE SET prefix = EXCLUDED.prefix;"
        command = command.format(str(ctx.guild.id))
        async with db.MaybeAcquire() as con:
            con.execute(command, (prefix,))
        self.bot.get_guild_prefix.invalidate(ctx.guild.id)
        await ctx.send(embed=ctx.create_embed(description=f"Updated prefix to `{prefix}`"))

    @commands.command(name="*flat", hidden=True)
    @commands.is_owner()
    async def prefix(self, ctx: Context, guild_id: int, new_val: int, column: str):
        """
        Change a guild's flattening time.
        """
        column = column.lower()
        if column == "time":
            column = "time_remove"
        elif column == "specific":
            column = "specific_remove"
        elif column == "detail":
            column = "detail_remove"
        else:
            return await ctx.send(embed=ctx.create_embed(description="Invalid column! specific, time, or detail.", error=True))
        if ctx.bot.get_guild(guild_id) is None:
            return await ctx.send(embed=ctx.create_embed(description="That guild doesn't exist!", error=True))
        command = "INSERT INTO guild_config(guild_id, {1}) VALUES ({0}, {2})" \
                  " ON CONFLICT (guild_id) DO UPDATE SET {1} = EXCLUDED.{1};"
        command = command.format(str(ctx.guild.id), str(column), str(new_val))
        async with db.MaybeAcquire() as con:
            con.execute(command)
        await ctx.send(embed=ctx.create_embed(description=f"Updated {column} to `{new_val}` days."))

    @commands.command(name="prefix")
    async def get_prefix(self, ctx: Context):
        """
        Displays the server's current prefix.
        """
        prefix = await self.bot.get_guild_prefix(ctx.guild.id)
        if prefix is None:
            prefix = "s~"
        await ctx.send(embed=ctx.create_embed(description=f"Current prefix is: `{prefix}`"))


def setup(bot):
    bot.add_cog(GuildConfig(bot))

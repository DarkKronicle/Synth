from bot import synth_bot
from bot.util import checks
from bot.util import database as db
from bot.util.context import Context
from discord.ext import commands


class GuildConfigTable(db.Table, table_name='guild_config'):
    guild_id = db.Column(db.Integer(big=True), unique=True, index=True)
    prefix = db.Column(db.String(length=12), default='s~')  # noqa: WPS432
    specific_remove = db.Column(db.Integer(small=True), default='7')
    time_remove = db.Column(db.Integer(small=True), default='30')
    detail_remove = db.Column(db.Integer(small=True), default='90')


class GuildConfig(commands.Cog):
    """Configure and view server settings."""

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot

    @commands.command(name='!prefix')
    @checks.is_mod()
    async def prefix(self, ctx: Context, *, prefix: str = None):
        """
        Change's the server's prefix. The global prefix s~ will always be accessible.

        Examples:
              !prefix ~
              !prefix {}
        """
        if prefix is None or 6 >= len(prefix) or len(prefix) < 0:
            return await ctx.send('You need to specify a prefix of max length 6 and minimum length 1!')
        command = 'INSERT INTO guild_config(guild_id, prefix) VALUES ({0}, %s) ON CONFLICT (guild_id) DO UPDATE SET prefix = EXCLUDED.prefix;'  # noqa: WPS323
        command = command.format(str(ctx.guild.id))
        async with db.MaybeAcquire() as con:
            con.execute(command, (prefix,))
        self.bot.get_guild_prefix.invalidate(ctx.guild.id)
        await ctx.send(embed=ctx.create_embed(description='Updated prefix to `{0}`'.format(prefix)))

    @commands.command(name='*flat', hidden=True)
    @commands.is_owner()
    async def flat(self, ctx: Context, guild_id: int, new_days: int, column: str):
        """
        Change a guild's flattening time.
        """
        column = column.lower()
        if column == 'time':
            column = 'time_remove'
        elif column == 'specific':
            column = 'specific_remove'
        elif column == 'detail':
            column = 'detail_remove'
        else:
            await ctx.send(embed=ctx.create_embed(description='Invalid column! specific, time, or detail.', error=True))
            return
        if ctx.bot.get_guild(guild_id) is None:
            await ctx.send(embed=ctx.create_embed(description="That guild doesn't exist!", error=True))
            return
        command = 'INSERT INTO guild_config(guild_id, {1}) VALUES ({0}, {2}) ON CONFLICT (guild_id) DO UPDATE SET {1} = EXCLUDED.{1};'
        command = command.format(str(ctx.guild.id), column, str(new_days))
        async with db.MaybeAcquire() as con:
            con.execute(command)
        await ctx.send(embed=ctx.create_embed(description='Updated {0} to `{1}` days.').format(column, new_days))

    @commands.command(name='prefix')
    async def _prefix(self, ctx: Context):
        """
        Displays the server's current prefix.
        """
        prefix = await self.bot.get_guild_prefix(ctx.guild.id)
        if prefix is None:
            prefix = 's~'
        await ctx.send(embed=ctx.create_embed(description='Current prefix is: `{0}`'.format(prefix)))


def setup(bot):
    bot.add_cog(GuildConfig(bot))

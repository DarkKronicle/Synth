from bot.util import checks
from bot.util import database as db
from bot.util.context import Context
from discord.ext import commands
from bot.util import storage_cache as cache


class GuildConfigTable(db.Table, table_name='guild_config'):
    guild_id = db.Column(db.Integer(big=True), unique=True, index=True)
    prefix = db.Column(db.String(length=12), default='s~')  # noqa: WPS432
    specific_remove = db.Column(db.Integer(small=True), default='7')
    time_remove = db.Column(db.Integer(small=True), default='30')
    detail_remove = db.Column(db.Integer(small=True), default='90')
    message_cooldown = db.Column(db.Integer(small=True), default='60')


class GuildSettings:
    __slots__ = ('guild', 'prefix', 'message_cooldown')

    def __init__(self, guild, prefix, message_cooldown):
        self.guild = guild
        self.prefix = prefix
        self.message_cooldown = message_cooldown

    @classmethod
    def get_default(cls, guild):
        return cls(guild, '~', 60)


async def get_guild_settings(bot, guild):
    """Get's basic guild settings information."""
    cog = bot.get_cog('GuildConfig')
    if cog is None:
        return GuildSettings.get_default(guild)
    return await cog.get_settings(guild.id)


class GuildConfig(commands.Cog):
    """Configure and view server settings."""

    def __init__(self, bot):
        self.bot = bot

    @cache.cache()
    async def get_settings(self, guild_id):
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return None
        command = 'SELECT prefix, message_cooldown FROM guild_config WHERE guild_id = {0};'
        command = command.format(guild_id)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entry = con.fetchone()
        if entry is None:
            return GuildSettings.get_default(guild)
        return GuildSettings(guild, entry['prefix'], entry['message_cooldown'])

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
        data = await self.get_settings(ctx.guild.id)
        if data is None:
            prefix = 's~'
        else:
            prefix = data.prefix
        await ctx.send(embed=ctx.create_embed(description='Current prefix is: `{0}`'.format(prefix)))


def setup(bot):
    bot.add_cog(GuildConfig(bot))

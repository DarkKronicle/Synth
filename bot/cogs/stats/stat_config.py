import enum

import discord
import typing
from discord.ext import commands
from bot.util import database as db, checks, paginator
from bot.util import storage_cache as cache
from bot.util.context import Context
from bot.util.format import human_bool


class StatConfig(db.Table, table_name='stat_config'):
    guild_id = db.Column(db.Integer(big=True), index=True, nullable=False)
    type = db.Column(db.Integer(small=True))
    object_id = db.Column(db.Integer(big=True))
    allow = db.Column(db.Boolean())

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)
        sql = 'ALTER TABLE stat_config DROP CONSTRAINT IF EXISTS one_object;' \
              'ALTER TABLE stat_config ADD CONSTRAINT one_object UNIQUE (guild_id, object_id);'

        return statement + '\n' + sql


class StatConfigType(enum.Enum):

    guild = 0
    channel = 1
    user = 2
    role = 3
    category = 4

    @classmethod
    def from_object(cls, obj):
        if isinstance(obj, (discord.Guild,)):
            return StatConfigType.guild
        if isinstance(obj, (discord.VoiceChannel, discord.TextChannel, discord.StageChannel)):
            return StatConfigType.channel
        if isinstance(obj, (discord.User, discord.Member)):
            return StatConfigType.user
        if isinstance(obj, (discord.Role,)):
            return StatConfigType.role
        if isinstance(obj, (discord.CategoryChannel,)):
            return StatConfigType.category

    @classmethod
    def format_type(cls, obj):
        stat_type = StatConfigType.from_object(obj)
        if stat_type == StatConfigType.guild:
            return 'Guild {0}'.format(obj.name)
        if stat_type == StatConfigType.channel:
            return 'Channel {0}'.format(obj.mention)
        if stat_type == StatConfigType.user:
            return 'User {0}'.format(obj.mention)
        if stat_type == StatConfigType.role:
            return 'Role {0}'.format(obj.mention)
        if stat_type == StatConfigType.category:
            return 'Category {0}'.format(obj.name)
        return str(object)


class StatPermissions:

    def __init__(self, guild_id, db_rows):
        self.guild_id = guild_id
        self.guild = True
        self.roles = {}
        self.categories = {}
        self.channels = {}
        self.users = {}
        for row in db_rows:
            object_id = row['object_id']
            allow = row['allow']
            try:
                stat_type = StatConfigType(row['type'])
            except ValueError:
                # Not a proper type...
                continue
            if stat_type == StatConfigType.guild:
                self.guild = allow
            elif stat_type == StatConfigType.channel:
                self.channels[object_id] = allow
            elif stat_type == StatConfigType.category:
                self.categories[object_id] = allow
            elif stat_type == StatConfigType.user:
                self.users[object_id] = allow
            elif stat_type == StatConfigType.role:
                self.roles[object_id] = allow

    def is_allowed(self, channel, user: discord.Member):
        allowed = self.guild

        category = channel.category
        if category:
            category_allowed = self.categories.get(category.id)
            if category_allowed is not None:
                allowed = category_allowed

        channel_allowed = self.channels.get(channel.id)
        if channel_allowed is not None:
            allowed = channel_allowed

        for role in user.roles:
            role_allowed = self.roles.get(role.id)
            if role_allowed is not None:
                allowed = role_allowed

        user_allowed = self.users.get(user.id)
        if user_allowed is not None:
            allowed = user_allowed

        return allowed


async def should_log(bot, guild, channel, user):
    stats_config = bot.get_cog('StatisticConfig')
    if not stats_config:
        return True
    return await stats_config.is_allowed(guild, channel, user)


class StatisticConfig(commands.Cog):
    """Configures how statistics are tracked."""

    def __init__(self, bot):
        self.bot = bot

    @cache.cache()
    async def get_stat_config(self, guild_id):
        command = 'SELECT type, object_id, allow FROM stat_config WHERE guild_id = {0};'
        command = command.format(guild_id)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()
        return StatPermissions(guild_id, entries)

    async def is_allowed(self, guild, channel, user):
        perms = await self.get_stat_config(guild.id)
        return perms.is_allowed(channel, user)

    @commands.group('!statconfig', aliases=['!sconfig', '!statc'])
    @checks.is_manager()
    @commands.guild_only()
    async def stat_config(self, ctx: Context):
        """
        Configures how statistics are logged.

        Whichever one is top disabled/enabled in the following determines whether it will be logged.
        Guild -> Channel -> Role -> User
        """
        if not ctx.invoked_subcommand:
            await ctx.send_help('!statconfig')

    @stat_config.command(name='list')
    async def list_config(self, ctx: Context):
        """List's the current stat config."""
        config = await self.get_stat_config(ctx.guild.id)
        entries = ['Guild {0}'.format(config.guild)]
        for category in config.categories:
            entries.append('{1} Category <#{0}>'.format(category, human_bool(config.categories[category])))
        for channel in config.channels:
            entries.append('{1} <#{0}>'.format(channel, human_bool(config.channels[channel])))
        for user in config.users:
            entries.append('{1} <@{0}>'.format(user, human_bool(config.users[user])))
        for role in config.roles:
            entries.append('{1} <@&{0}>'.format(role, human_bool(config.roles[role])))
        menu = paginator.SimplePages(
            entries, per_page=15,
            embed=ctx.create_embed(title='Settings for {0}'.format(ctx.guild.name)),
        )
        try:
            await menu.start(ctx)
        except:
            pass

    @stat_config.command(name='disable')
    async def stat_disable(
            self,
            ctx: Context,
            to_disable: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.Member, discord.Role, discord.CategoryChannel] = None,
    ):
        """
        Disables a specific channel, member, role, or guild.

        Leaving the `to_disable` blank disables the guild.

        Examples:
            disable #bot
            disable DarkKronicle
            disable
            disable 523605852557672449
        """
        if not to_disable:
            to_disable = ctx.guild
        await self.change_config(
            False,
            StatConfigType.from_object(to_disable),
            ctx.guild.id,
            to_disable.id,
        )
        await ctx.send(embed=ctx.create_embed('Disabled {0}'.format(StatConfigType.format_type(to_disable))))

    @stat_config.command(name='enable')
    async def stat_enable(
            self,
            ctx: Context,
            to_enable: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.Member, discord.Role, discord.CategoryChannel] = None,
    ):
        """
        Enables a specific channel, member, role, or guild.

        Leaving the `to_enable` blank enables the guild.

        Examples:
            enable #bot
            enable DarkKronicle
            enable
            enable 523605852557672449
        """
        if not to_enable:
            to_enable = ctx.guild
        await self.change_config(
            True,
            StatConfigType.from_object(to_enable),
            ctx.guild.id,
            to_enable.id,
        )
        await ctx.send(embed=ctx.create_embed('Enabled {0}'.format(StatConfigType.format_type(to_enable))))

    @stat_config.command(name='remove')
    async def stat_remove(
            self,
            ctx: Context,
            to_disable: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.Member, discord.Role, discord.CategoryChannel],
    ):
        """
        Removes a specific channel, member, or role from the config.

        Examples:
            remove #bot
            remove DarkKronicle
            remove 523605852557672449
        """
        if not to_disable:
            to_disable = ctx.guild
        await self.remove_config(
            ctx.guild.id,
            to_disable.id,
        )
        await ctx.send(embed=ctx.create_embed('Removed settings for {0}'.format(StatConfigType.format_type(to_disable))))

    async def change_config(self, allow, config_type, guild_id, object_id):
        command = ('INSERT INTO stat_config(guild_id, type, object_id, allow) '
                   'VALUES({0}, {1}, {2}, {3}) ON CONFLICT ON CONSTRAINT one_object '
                   'DO UPDATE SET allow = EXCLUDED.allow;')
        command = command.format(guild_id, config_type.value, object_id, allow)
        async with db.MaybeAcquire() as con:
            con.execute(command)
        self.get_stat_config.invalidate(self, guild_id)

    async def remove_config(self, guild_id, object_id):
        command = 'DELETE FROM stat_config WHERE guild_id = {0} AND object_id = {1};'
        command = command.format(guild_id, object_id)
        async with db.MaybeAcquire() as con:
            con.execute(command)
        self.get_stat_config.invalidate(self, guild_id)

    @stat_config.command(name='cooldown')
    @checks.is_manager()
    async def cooldown(self, ctx: Context, seconds: int = None):
        """
        Set's the cooldown before a user get's logged again.

        This is used to prevent spamming so users who send a lot of messages at once won't get logged.

        Leaving seconds blank shows the current cooldown.

        Examples:
            cooldown 60
            cooldown 0
            cooldown 180
            cooldown
        """
        if seconds is None:
            g_config = self.bot.get_cog('GuildConfig')
            if not g_config:
                return await ctx.send(embed=ctx.create_embed('Something went wrong!', error=True))
            data = await g_config.get_settings(ctx.guild.id)
            if data is None:
                cooldown = 60
            else:
                cooldown = data.message_cooldown
            await ctx.send(embed=ctx.create_embed(description='Current cooldown is `{0}` seconds'.format(cooldown)))
            return
        if seconds < 0:
            return await ctx.send(embed=ctx.create_embed('Seconds has to be greater than or equal to 0!', error=True))
        if seconds > 600:
            return await ctx.send(embed=ctx.create_embed("Seconds can't be greater than 600!", error=True))
        command = ('INSERT INTO guild_config(guild_id, message_cooldown) VALUES ({0}, {1}) '
                   'ON CONFLICT (guild_id) DO UPDATE SET message_cooldown = EXCLUDED.message_cooldown;')
        command = command.format(ctx.guild.id, seconds)
        async with db.MaybeAcquire() as con:
            con.execute(command)
        g_config = self.bot.get_cog('GuildConfig')
        if g_config:
            g_config.get_settings.invalidate(g_config, ctx.guild.id)
        await ctx.send(embed=ctx.create_embed('Message cooldown set to `{0}` seconds.'.format(seconds)))


def setup(bot):
    bot.add_cog(StatisticConfig(bot))

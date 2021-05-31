import enum

import discord
import typing
from discord.ext import commands
from bot.util import database as db, checks, paginator
from bot.util import storage_cache as cache
from bot.util.context import Context
from bot.util.format import human_bool


class CommandConfigTable(db.Table, table_name='command_config'):
    guild_id = db.Column(db.Integer(big=True), index=True, nullable=False)
    type = db.Column(db.Integer(small=True))
    object_id = db.Column(db.Integer(big=True))
    allow = db.Column(db.Boolean())
    name = db.Column(db.String())

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)
        sql = 'ALTER TABLE command_config DROP CONSTRAINT IF EXISTS one_command;' \
              'ALTER TABLE command_config ADD CONSTRAINT one_command UNIQUE (guild_id, object_id, name);'

        return statement + '\n' + sql


class RoleConfig(db.Table, table_name='role_config'):
    guild_id = db.Column(db.Integer(big=True), index=True, unique=True, nullable=False)
    # Access to everything, wherever
    admin_role = db.Column(db.Integer(big=True), nullable=True)
    # Access to almost everything
    manager_role = db.Column(db.Integer(big=True), nullable=True)


class CommandConfigType(enum.Enum):

    guild = 0
    channel = 1
    user = 2
    role = 3
    category = 4

    @classmethod
    def from_object(cls, obj):
        if isinstance(obj, (discord.Guild,)):
            return CommandConfigType.guild
        if isinstance(obj, (discord.VoiceChannel, discord.TextChannel, discord.StageChannel)):
            return CommandConfigType.channel
        if isinstance(obj, (discord.User, discord.Member)):
            return CommandConfigType.user
        if isinstance(obj, (discord.Role,)):
            return CommandConfigType.role
        if isinstance(obj, (discord.CategoryChannel,)):
            return CommandConfigType.category

    @classmethod
    def format_type(cls, obj):
        stat_type = CommandConfigType.from_object(obj)
        if stat_type == CommandConfigType.guild:
            return 'Guild {0}'.format(obj.name)
        if stat_type == CommandConfigType.channel:
            return 'Channel {0}'.format(obj.mention)
        if stat_type == CommandConfigType.user:
            return 'User {0}'.format(obj.mention)
        if stat_type == CommandConfigType.role:
            return 'Role {0}'.format(obj.mention)
        if stat_type == CommandConfigType.category:
            return 'Category {0}'.format(obj.name)
        return str(object)


class CommandPermissions:

    class PermissionData:

        def __init__(self):
            self.allowed = set()
            self.denied = set()

    def __init__(self, guild_id, role_row, db_rows):
        self.guild_id = guild_id
        self.manager_id = self._get_or_default(role_row, 'manager_role')
        self.admin_id = self._get_or_default(role_row, 'admin_role')
        self.guild = self.PermissionData()
        self.roles = {}
        self.categories = {}
        self.channels = {}
        self.users = {}
        for row in db_rows:
            object_id = row['object_id']
            allow = row['allow']
            name = row['name']
            try:
                stat_type = CommandConfigType(row['type'])
            except ValueError:
                # Not a proper type...
                continue
            if stat_type == CommandConfigType.guild:
                self._put_allow(self.guild, name, allow)
            elif stat_type == CommandConfigType.channel:
                self._put_allow_dict(self.channels, object_id, name, allow)
            elif stat_type == CommandConfigType.category:
                self._put_allow_dict(self.categories, object_id, name, allow)
            elif stat_type == CommandConfigType.user:
                self._put_allow_dict(self.users, object_id, name, allow)
            elif stat_type == CommandConfigType.role:
                self._put_allow_dict(self.roles, object_id, name, allow)

    @staticmethod
    def _get_or_default(row, key, *, default=None):
        if row is None:
            return default
        try:
            return row[key]
        except:
            return default

    @staticmethod
    def _get_or_create(dict_obj, key):
        if key in dict_obj:
            return dict_obj[key]
        dict_obj[key] = CommandPermissions.PermissionData()
        return dict_obj[key]

    @staticmethod
    def _put_allow_dict(dict_obj, key, name, allow):
        perms = CommandPermissions._get_or_create(dict_obj, key)
        CommandPermissions._put_allow(perms, name, allow)

    @staticmethod
    def _put_allow(obj, name, allow):
        if name is None:
            name = ''
        if allow:
            obj.allowed.add(name)
        else:
            obj.denied.add(name)

    @staticmethod
    def _split(obj):
        # "hello there world" -> ["hello", "hello there", "hello there world"]
        from itertools import accumulate
        return [''] + list(accumulate(obj.split(), lambda x, y: f'{x} {y}'))

    def is_command_allowed(self, channel, user: discord.Member, command):
        allowed = True
        modded = self.PermissionData()
        admin = False
        manager = False

        cmds = self._split(command)

        for cmd in cmds:
            if cmd in self.guild.allowed:
                modded.allowed.add((cmd, self.guild_id, CommandConfigType.guild))
                allowed = True
            elif cmd in self.guild.denied:
                modded.denied.add((cmd, self.guild_id, CommandConfigType.guild))
                allowed = False

        category = channel.category
        if category:
            category_allowed = self.categories.get(category.id)
            if category_allowed is not None:
                for cmd in cmds:
                    if cmd in category_allowed.allowed:
                        modded.allowed.add((cmd, category.id, CommandConfigType.category))
                        allowed = True
                    elif cmd in category_allowed.denied:
                        modded.denied.add((cmd, category.id, CommandConfigType.category))
                        allowed = False

        channel_allowed = self.channels.get(channel.id)
        if channel_allowed is not None:
            for cmd in cmds:
                if cmd in channel_allowed.allowed:
                    modded.allowed.add((cmd, channel.id, CommandConfigType.channel))
                    allowed = True
                elif cmd in channel_allowed.denied:
                    modded.denied.add((cmd, channel.id, CommandConfigType.channel))
                    allowed = False

        for role in user.roles:
            role_allowed = self.roles.get(role.id)
            if self.manager_id == role.id:
                manager = True
            if self.admin_id == role.id:
                admin = True
            if role_allowed is not None:
                for cmd in cmds:
                    if cmd in role_allowed.allowed:
                        modded.allowed.add((cmd, role.id, CommandConfigType.role))
                        allowed = True
                    elif cmd in role_allowed.denied:
                        modded.denied.add((cmd, role.id, CommandConfigType.role))
                        allowed = False

        user_allowed = self.users.get(user.id)
        if user_allowed is not None:
            for cmd in cmds:
                if cmd in user_allowed.allowed:
                    modded.allowed.add((cmd, user.id, CommandConfigType.user))
                    allowed = True
                elif cmd in user_allowed.denied:
                    modded.denied.add((cmd, user.id, CommandConfigType.user))
                    allowed = False

        return allowed, modded, admin, manager


class CommandName(commands.Converter):

    def __init__(self, *, block_settings=True):
        self.block_settings = block_settings

    async def convert(self, ctx, argument):
        if argument == '':
            return ''
        lowered = argument.lower()

        accessible_commands = []
        bot = ctx.bot

        for cmd in bot.walk_commands():
            # Don't block hidden commands or command config
            if (not self.block_settings or cmd.cog_name != 'CommandSettings') and not cmd.hidden:
                accessible_commands.append(cmd.qualified_name)

        if lowered not in accessible_commands:
            return None

        return lowered


class UserPerms:

    def __init__(self, ctx, command_perms):
        if command_perms is not None:
            allowed, modded, admin, manager = command_perms.is_command_allowed(ctx.channel, ctx.author, ctx.command.qualified_name.lower())
            self.allowed = allowed
            self.modded = modded
            self.admin = admin
            self.manager = manager
        else:
            self.allowed = True
            self.modded = CommandPermissions.PermissionData()
            self.admin = False
            self.manager = False


async def get_perms(bot, ctx: Context):
    cog = bot.get_cog('CommandSettings')
    if cog is not None:
        return await cog.is_command_allowed(ctx)
    return UserPerms(ctx, None)


class CommandSettings(commands.Cog):
    """Configures command permissions"""

    def __init__(self, bot):
        self.bot = bot

    async def is_command_allowed(self, ctx):
        config = await self.get_command_config(ctx.guild.id)
        return UserPerms(ctx, config)

    @cache.cache()
    async def get_command_config(self, guild_id):
        command = 'SELECT type, object_id, allow, name FROM command_config WHERE guild_id = {0};'
        command = command.format(guild_id)
        roles = 'SELECT * FROM role_config WHERE guild_id = {0};'
        roles = roles.format(guild_id)
        async with db.MaybeAcquire() as con:
            con.execute(command)
            entries = con.fetchall()
            con.execute(roles)
            role_entry = con.fetchone()
        return CommandPermissions(guild_id, role_entry, entries)

    async def is_allowed(self, guild, channel, user, command):
        perms = await self.get_command_config(guild.id)
        return perms.is_allowed(channel, user, command)

    @commands.group('!commandconfig', aliases=['!cconfig', '!cc'])
    @checks.is_manager()
    @commands.guild_only()
    async def command_config(self, ctx: Context):
        """
        Configures command permissions.

        Whichever one is top disabled/enabled in the following determines whether it will be allowed.
        Guild -> Channel -> Role -> User
        """
        if not ctx.invoked_subcommand:
            await ctx.send_help('!statconfig')

    @command_config.command(name='admin')
    @checks.is_admin()
    async def admin(self, ctx: Context, role: discord.Role = None):
        """
        Set's a role for complete synth access.

        Admin's get access to every command, regardless of block status.

        Examples:
            admin Admin
            admin @Owner
        """
        command = 'INSERT INTO role_config(guild_id, admin_role) VALUES ({0}, {1}) ON CONFLICT (guild_id) DO UPDATE SET admin_role = EXCLUDED.admin_role;'
        if role is None:
            command = command.format(ctx.guild.id, 'NULL')
        else:
            command = command.format(ctx.guild.id, role.id)
        async with db.MaybeAcquire() as con:
            print(command)
            con.execute(command)
        if role:
            description = 'Set Admin Role to {0}'.format(role.mention)
        else:
            description = 'Removed Admin Role'
        self.get_command_config.invalidate(self, ctx.guild.id)
        await ctx.send(embed=ctx.create_embed(description))

    @command_config.command(name='manager')
    @checks.is_admin()
    async def manager(self, ctx: Context, role: discord.Role = None):
        """
        Set's a role for moderate synth access.

        Manager's get access to configure bot options but don't bypass command config.

        Examples:
            manager Moderator
            manager @Developer
        """
        command = 'INSERT INTO role_config(guild_id, manager_role) VALUES ({0}, {1}) ON CONFLICT (guild_id) DO UPDATE SET manager_role = EXCLUDED.manager_role;'
        if role is None:
            command = command.format(ctx.guild.id, 'NULL')
        else:
            command = command.format(ctx.guild.id, role.id)
        async with db.MaybeAcquire() as con:
            con.execute(command)
        if role:
            description = 'Set Manager Role to {0}'.format(role.mention)
        else:
            description = 'Removed Manager Role'
        self.get_command_config.invalidate(self, ctx.guild.id)
        await ctx.send(embed=ctx.create_embed(description))

    @command_config.command(name='list')
    async def list_config(self, ctx: Context):
        """List's the current command config."""
        config = await self.get_command_config(ctx.guild.id)
        entries = []
        if len(config.guild.allowed) > 1 or len(config.guild.denied) > 1:
            entries.append('Guild')
            for c in config.guild.allowed:
                entries.append('{1}  {0}'.format(c, human_bool(True)))
            for c in config.guild.denied:
                entries.append('{1}  {0}'.format(c, human_bool(False)))
        for category, perms in config.categories.items():
            entries.append('Category <#{0}>'.format(category))
            for c in perms.allowed:
                entries.append('{1}  {0}'.format(c, human_bool(True)))
            for c in perms.denied:
                entries.append('{1}  {0}'.format(c, human_bool(False)))
        for channel, perms in config.channels.items():
            entries.append('Channel <#{0}>'.format(channel))
            for c in perms.allowed:
                entries.append('{1}  {0}'.format(c, human_bool(True)))
            for c in perms.denied:
                entries.append('{1}  {0}'.format(c, human_bool(False)))
        for user, perms in config.users.items():
            entries.append('User <@{0}>'.format(user))
            for c in perms.allowed:
                entries.append('{1}  {0}'.format(c, human_bool(True)))
            for c in perms.denied:
                entries.append('{1}  {0}'.format(c, human_bool(False)))
        for role, perms in config.roles.items():
            entries.append('Roles <@&{0}>'.format(role))
            for c in perms.allowed:
                entries.append('{1}  {0}'.format(c, human_bool(True)))
            for c in perms.denied:
                entries.append('{1}  {0}'.format(c, human_bool(False)))
        embed = ctx.create_embed(title='Settings for {0}'.format(ctx.guild.name))
        if config.admin_id:
            admin = '<@&{0}>'.format(config.admin_id)
        else:
            admin = 'None'
        if config.manager_id:
            manager = '<@&{0}>'.format(config.manager_id)
        else:
            manager = 'None'
        embed.add_field(name='Admin', value=admin)
        embed.add_field(name='Manager', value=manager)
        menu = paginator.SimplePages(
            entries, per_page=15,
            embed=embed,
            numbers=False,
        )
        try:
            await menu.start(ctx)
        except:
            pass

    @command_config.command(name='disable')
    async def command_disable(
            self,
            ctx: Context,
            to_disable: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.Member, discord.Role, discord.CategoryChannel] = None,
            *,
            command: CommandName() = '',
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
            CommandConfigType.from_object(to_disable),
            ctx.guild.id,
            to_disable.id,
            command,
        )
        if command != '':
            description = 'Disabled command `{1}` for {0}'.format(CommandConfigType.format_type(to_disable), command)
        else:
            description = 'Disabled globally for {0}'.format(CommandConfigType.format_type(to_disable))
        await ctx.send(embed=ctx.create_embed(description))

    @command_config.command(name='enable')
    async def command_enable(
            self,
            ctx: Context,
            to_enable: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.Member, discord.Role, discord.CategoryChannel] = None,
            *,
            command: CommandName() = ''
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
            CommandConfigType.from_object(to_enable),
            ctx.guild.id,
            to_enable.id,
            command,
        )
        if command != '':
            description = 'Enabled command `{1}` for {0}'.format(CommandConfigType.format_type(to_enable), command)
        else:
            description = 'Enabled globally for {0}'.format(CommandConfigType.format_type(to_enable))
        await ctx.send(embed=ctx.create_embed(description))

    @command_config.command(name='remove')
    async def command_remove(
            self,
            ctx: Context,
            to_disable: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.Member, discord.Role, discord.CategoryChannel],
            *,
            command: CommandName() = ''
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
            command,
        )
        if command != '':
            description = 'Removed command settings `{1}` for {0}'.format(CommandConfigType.format_type(to_disable), command)
        else:
            description = 'Removed global settings for {0}'.format(CommandConfigType.format_type(to_disable))
        await ctx.send(embed=ctx.create_embed(description))

    async def change_config(self, allow, config_type, guild_id, object_id, name):
        command = ('INSERT INTO command_config(guild_id, type, object_id, allow, name) '
                   'VALUES({0}, {1}, {2}, {3}, %s) ON CONFLICT ON CONSTRAINT one_command '
                   'DO UPDATE SET allow = EXCLUDED.allow;')
        command = command.format(guild_id, config_type.value, object_id, allow)
        async with db.MaybeAcquire() as con:
            con.execute(command, (name,))
        self.get_command_config.invalidate(self, guild_id)

    async def remove_config(self, guild_id, object_id, name):
        command = "DELETE FROM command_config WHERE guild_id = {0} AND object_id = {1} AND name = %s;"
        command = command.format(guild_id, object_id)
        async with db.MaybeAcquire() as con:
            con.execute(command, (name,))
        self.get_command_config.invalidate(self, guild_id)


def setup(bot):
    bot.add_cog(CommandSettings(bot))

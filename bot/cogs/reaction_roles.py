import enum

import discord
from discord.ext import commands

from glocklib import database as db, checks
from bot.util import storage_cache as cache
from glocklib import context as Context
from bot.util.emoji_util import Emoji
from glocklib import paginator as pages


class ReactionMessagesTable(db.Table, table_name='reaction_messages'):
    reaction_role_id = db.Column(db.Integer(big=True, auto_increment=True), primary_key=True)
    guild_id = db.Column(db.Integer(big=True))
    channel_id = db.Column(db.Integer(big=True))
    message_id = db.Column(db.Integer(big=True), unique=True)
    type = db.Column(db.Integer(small=True))

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)
        sql = "CREATE UNIQUE INDEX IF NOT EXISTS reaction_messages_uniq_idx ON reaction_messages (guild_id, message_id);"
        return statement + '\n' + sql


class ReactionRolesTable(db.Table, table_name='reaction_roles'):
    reaction_role_id = db.Column(db.ForeignKey('reaction_messages', 'reaction_role_id'), index=True, nullable=False)
    role_id = db.Column(db.Integer(big=True), nullable=False)
    reaction = db.Column(db.String(), nullable=False)

    @classmethod
    def create_table(cls, *, overwrite=False):
        statement = super().create_table(overwrite=overwrite)

        # create the constraints
        sql = 'ALTER TABLE reaction_roles DROP CONSTRAINT IF EXISTS unique_roles; ' \
              'ALTER TABLE reaction_roles ADD CONSTRAINT unique_roles UNIQUE (reaction_role_id, role_id);' \
              'ALTER TABLE reaction_roles DROP CONSTRAINT IF EXISTS unique_reactions; ' \
              'ALTER TABLE reaction_roles ADD CONSTRAINT unique_reactions UNIQUE (reaction_role_id, reaction);'

        return '{0}\n{1}'.format(statement, sql)


class ReactionType(enum.Enum):

    toggle = 0
    once = 1

    @classmethod
    def get_description(cls, reaction_type):
        if reaction_type == ReactionType.toggle:
            return 'Toggles the specific reaction role. Users can have as many from the message.'
        if reaction_type == ReactionType.once:
            return 'Toggles the specific reaction role. Users can only have one from a message.'
        return 'Unknown...'


class ReactionRole:

    __slots__ = ('reaction', 'role')

    def __init__(self, reaction, role):
        self.reaction = reaction
        self.role = role


class ReactionRolesContainer:

    def __init__(self, guild, channel, message, roles, reaction_type):
        self.guild = guild
        self.channel = channel
        self.message = message
        self.roles = roles
        self.reaction_type = reaction_type

    def get_react(self, react):
        for r in self.roles:
            if r.reaction == react:
                return r

    def all_except(self, role):
        return [r for r in self.roles if r != role]


class ReactionTypeConverter(commands.Converter):

    async def convert(self, ctx: Context, argument):
        try:
            return ReactionType(int(argument))
        except:
            pass
        return ReactionType[argument]


class ReactionRoles(commands.Cog):
    """Configures reaction roles."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        guild = payload.guild_id
        if guild is None:
            return
        user = payload.member
        if user.bot:
            # No reaction roles for bot..
            return
        message = payload.message_id
        emoji = str(payload.emoji)
        roles: ReactionRolesContainer = await self.get_reaction_roles(guild, message)
        if not roles:
            return
        await self.handle_reaction(True, user, roles, emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        guild = payload.guild_id
        if guild is None:
            return
        user = payload.member
        if user is None:
            guild_obj = self.bot.get_guild(guild)
            if guild_obj is None:
                return
            user = guild_obj.get_member(payload.user_id)
        if user is None:
            return
        if user.bot:
            # No reaction roles for bot..
            return
        message = payload.message_id
        emoji = str(payload.emoji)
        roles: ReactionRolesContainer = await self.get_reaction_roles(guild, message)
        if not roles:
            return
        await self.handle_reaction(False, user, roles, emoji)

    async def handle_reaction(self, add, user, roles, reaction):
        user: discord.Member
        role = roles.get_react(reaction)
        if roles.reaction_type == ReactionType.toggle:
            if add:
                await user.add_roles(role.role, reason='Reaction')
            else:
                await user.remove_roles(role.role, reason='Reaction')
        elif roles.reaction_type == ReactionType.once:
            if add:
                for message_reaction in roles.message.reactions:
                    if str(message_reaction.emoji) != reaction:
                        await roles.message.remove_reaction(message_reaction.emoji, user)

                await user.add_roles(role.role, reason='Reaction')
            else:
                await user.remove_roles(role.role, reason='Reaction')

    # MPL v2 https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L203
    @cache.cache()
    async def get_message(self, channel, message_id):
        try:
            o = discord.Object(id=message_id + 1)
            # don't wanna use get_message due to poor rate limit (1/1s) vs (50/1s)
            msg = await channel.history(limit=1, before=o).next()

            if msg.id != message_id:
                return None

            return msg
        except Exception:
            return None

    @commands.group(name='!role', aliases=['!roles'])
    @checks.is_manager_or_perms()
    @commands.guild_only()
    async def role_command(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help('!role')

    @role_command.command(name='list')
    @commands.cooldown(1, 8, type=commands.BucketType.user)
    async def list_roles(self, ctx: Context):
        command = 'SELECT * FROM reaction_messages WHERE guild_id={0};'
        roles_select = 'SELECT * FROM reaction_roles WHERE reaction_role_id in ({0});'
        async with db.MaybeAcquire(pool=self.bot.pool) as con:
            messages = await con.fetch(command.format(ctx.guild.id))
            if len(messages) == 0:
                return await ctx.send(ctx.create_embed("You don't have any reaction roles setup!", error=True))
            roles = await con.fetch(roles_select.format(
                ','.join(str(entry['reaction_role_id']) for entry in messages)
            ))
        string_representation = "<#{channel_id}> (Type: `{reaction_type}`) - {all_roles}\n{formatted_roles}"
        format_roles = "{0} <@&{1}>"
        strings = []
        for message in messages:
            message_roles = [role for role in roles if role['reaction_role_id'] == message['reaction_role_id']]
            strings.append(
                string_representation.format(
                    channel_id=message['channel_id'],
                    reaction_type=message['type'],
                    all_roles=len(message_roles),
                    formatted_roles='\n'.join([format_roles.format(r['reaction'], r['role_id']) for r in message_roles])
                )
            )
        menu = pages.SimplePages(entries=strings, per_page=1, embed=ctx.create_embed())
        try:
            await menu.start(ctx)
        except:
            pass

    @role_command.command(name='create')
    @commands.cooldown(1, 8, type=commands.BucketType.user)
    async def add_role(self, ctx: Context, message: discord.Message, role: discord.Role, reaction: Emoji):
        list_format = '{0}. {1}'
        reaction_types = '\n'.join(
            [list_format.format(i, ReactionType.get_description(reaction_type)) for i, reaction_type in enumerate(ReactionType)],
        )
        result = await ctx.ask('What type of role do you want this to be? ```\n{0}\n```'.format(reaction_types))
        if not result:
            return await ctx.send(embed=ctx.create_embed('Timed out!', error=True))
        try:
            role_int = int(result)
            role_type = ReactionType(role_int)
        except:
            return await ctx.send(embed=ctx.create_embed('Invalid reaction type!', error=True))
        await self.insert_role(ctx.guild.id, message.channel.id, message.id, role_type.value, role.id, reaction)
        await message.add_reaction(reaction)
        await ctx.send(embed=ctx.create_embed('Success!'))

    async def insert_role(self, guild_id, channel_id, message_id, reaction_index, role_id, reaction):
        command = 'INSERT INTO reaction_messages (guild_id, channel_id, message_id, type) VALUES ({0}, {1}, {2}, {3}) ON CONFLICT DO NOTHING;'
        command = command.format(guild_id, channel_id, message_id, reaction_index)
        select = 'SELECT * FROM reaction_messages WHERE guild_id = {0} AND message_id = {1};'
        select = select.format(guild_id, message_id)
        insert = 'INSERT INTO reaction_roles (reaction_role_id, role_id, reaction) VALUES ({0}, {1}, $1) ON CONFLICT DO NOTHING;'
        async with db.MaybeAcquire(pool=self.bot.pool) as con:
            await con.execute(command)
            message_entry = await con.fetchrow(select)
            insert = insert.format(message_entry['reaction_role_id'], role_id)
            await con.execute(insert, str(reaction))
        self.get_reaction_roles.invalidate(self, guild_id, message_id)

    @cache.cache()
    async def get_reaction_roles(self, guild_id, message_id):
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return None

        check_command = 'SELECT * FROM reaction_messages WHERE guild_id = {0} and message_id = {1};'
        roles_command = 'SELECT * FROM reaction_roles WHERE reaction_role_id = {0};'

        async with db.MaybeAcquire(pool=self.bot.pool) as con:
            entry = await con.fetchrow(check_command.format(guild_id, message_id))
            if entry is None:
                # Not a reaction message
                return None
            roles_entry = await con.fetch(roles_command.format(entry['reaction_role_id']))

        if len(roles_entry) == 0:
            # No reaction roles
            return None

        roles = []
        for role_entry in roles_entry:
            role = guild.get_role(role_entry['role_id'])
            if role is None:
                continue
            roles.append(ReactionRole(role_entry['reaction'], role))
        try:
            reaction_type = ReactionType(entry['type'])
        except ValueError:
            reaction_type = ReactionType.toggle
        channel = guild.get_channel(entry['channel_id'])
        if channel is None:
            return None
        message = await self.get_message(channel, message_id)
        return ReactionRolesContainer(guild, channel, message, roles, reaction_type)


def setup(bot):
    bot.add_cog(ReactionRoles(bot))

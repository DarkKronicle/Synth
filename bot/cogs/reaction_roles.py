import enum

import discord
from discord.ext import commands

from bot.util import database as db
from bot.util import storage_cache as cache


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


# class ReactionRolesTable(db.Table, table_name='reaction_roles'):
#     reaction_role_id = db.Column(db.ForeignKey('reaction_messages', 'reaction_role_id'), index=True, nullable=False)
#     role_id = db.Column(db.Integer(big=True), nullable=False)
#     reaction = db.Column(db.String(), nullable=False)


class ReactionType(enum.Enum):

    toggle = 0


class ReactionRole:

    __slots__ = ('reaction', 'role')

    def __init__(self, reaction, role):
        self.reaction = reaction
        self.role = role


class ReactionRolesContainer:

    def __init__(self, guild, message, roles, reaction_type):
        self.guild = guild
        self.message = message
        self.roles = roles
        self.reaction_type = reaction_type


class ReactionRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_message_add(self, payload: discord.RawReactionActionEvent):
        emoji = str(payload.emoji)

    # MPL v2 https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L203
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

    @cache.cache()
    async def get_reaction_roles(self, guild_id, message_id):
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return None

        check_command = 'SELECT * FROM reaction_messages WHERE guild_id = {0} and message_id = {1};'
        roles_command = 'SELECT * FROM reaction_roles WHERE reaction_role_id = {0};'

        async with db.MaybeAcquire() as con:
            con.execute(check_command.format(guild_id, message_id))
            entry = con.fetchone()
            if entry is None:
                # Not a reaction message
                return None
            con.execute(roles_command.format(entry['reaction_role_id']))
            roles_entry = con.fetchall()

        if len(roles_entry) == 0:
            # No reaction roles
            return None

        roles = []
        for entry in roles_entry:
            role = guild.get_role(entry['role_id'])
            if role is None:
                continue
            roles.append(ReactionRole(entry['reaction'], role))
        try:
            reaction_type = ReactionType(entry['type'])
        except ValueError:
            reaction_type = ReactionType.toggle
        channel = guild.get_channel(entry['channel_id'])
        if channel is None:
            return None
        message = await self.get_message(channel, message_id)
        return ReactionRolesContainer(guild, message, roles, reaction_type)


def setup(bot):
    bot.add_cog(ReactionRoles(bot))

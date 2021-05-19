from bot.cogs.channels.channel_base import StatChannel
from bot.util.context import Context
from bot.util import database as db


class MessagesChannel(StatChannel):

    def __init__(self):
        self.channel_type = 1

    async def name_from_sql(self, guild_id, channel_id, name, text, connection) -> str:
        command = "SELECT * FROM messages WHERE guild_id = {0} AND time >= NOW() at time zone 'utc' - INTERVAL '24 HOURS';"
        command = command.format(guild_id)
        connection.execute(command)
        entries = connection.fetchall()
        i = 0
        for entry in entries:
            if entry['channel_id'] is None and entry['user_id'] is None:
                i += entry['amount']
            elif entry['channel_id'] is not None:
                i += entry['amount']
        return name.replace('{0}', str(i))

    async def create(self, ctx: Context, channel, text):
        name = text
        command = "INSERT INTO stat_channels(guild_id, channel_id, type, name) VALUES ({0}, {1}, {2}, %s);"
        command = command.format(ctx.guild.id, channel.id, self.channel_type)
        async with db.MaybeAcquire() as con:
            con.execute(command, (name,))
        await ctx.send("Created one?!")

    async def get_info(self, guild_id, channel_id, name, text):
        pass

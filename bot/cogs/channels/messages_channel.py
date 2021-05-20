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

    async def create(self, ctx: Context, channel):
        description = ('What name would you like the channel to have? '
                       'Use `{0}` for the number placeholder.\n\nExamples:'
                       '```\n{0} Messages\nTotal of {0}\n```')
        name = await ctx.ask(embed=ctx.create_embed(description))
        if name is None:
            return await ctx.send(embed=ctx.create_embed(description='Cancelled!', error=True))
        if '{0}' not in name:
            return await ctx.send(embed=ctx.create_embed(description='Channel name has to contain `{0}`!', error=True))
        if len(name) > 50:
            return await ctx.send(embed=ctx.create_embed(description="Channel name can't be over 50 characters!", error=True))
        command = "INSERT INTO stat_channels(guild_id, channel_id, type, name) VALUES ({0}, {1}, {2}, %s);"
        command = command.format(ctx.guild.id, channel.id, self.channel_type)
        arguments = ''
        async with db.MaybeAcquire() as con:
            con.execute(command, (name,))
        info = await self.get_info(ctx.guild.id,channel.id, name, arguments)
        await ctx.send(embed=ctx.create_embed('Created new stat channel!\n\n{0}'.format(info)))

    async def get_info(self, guild_id, channel_id, name, text):
        return '<#{0}> - Messages in the last day'.format(channel_id)

    def get_standard_description(self):
        return 'A channel to display the amount of messages in a set time period.'

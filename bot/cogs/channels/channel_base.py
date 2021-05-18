from bot.util.context import Context


class StatChannel:

    def name_from_sql(self, guild_id, channel_id, name, text, connection) -> str:
        raise NotImplementedError

    async def create(self, ctx: Context, channel) -> str:
        raise NotImplementedError

    async def get_info(self, guild_id, channel_id, name, text):
        raise NotImplementedError
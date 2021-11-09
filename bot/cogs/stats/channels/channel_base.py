from glocklib import context as Context


class StatChannel:

    async def name_from_sql(self, guild_id, channel_id, name, text, connection) -> str:
        raise NotImplementedError

    async def create(self, ctx: Context, channel) -> str:
        raise NotImplementedError

    async def get_info(self, guild_id, channel_id, name, text):
        raise NotImplementedError

    def get_standard_description(self):
        raise NotImplementedError

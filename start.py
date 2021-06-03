import asyncio
import traceback

from bot.synth_bot import SynthBot, startup_extensions, cogs_dir
from bot.util import database as db
import bot as bot_storage
from bot.util.config import Config
from pathlib import Path
import importlib
import logging


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name='discord.http')

    def filter(self, record):
        if record.levelname == 'WARNING' and 'We are being rate limited.' in record.msg:
            return False
        return True


logging.getLogger().setLevel(logging.INFO)
logging.getLogger('discord').setLevel(logging.INFO)
logging.getLogger('discord.client').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.http').addFilter(RemoveNoise())


async def create_tables(connection):
    for table in db.Table.all_tables():
        try:
            await table.create(connection=connection)
        except Exception:     # noqa: E722
            logging.warning('Failed creating table {0}'.format(table.tablename))
            traceback.print_exc()


async def database(pool):

    cogs = startup_extensions

    for cog in cogs:
        try:
            importlib.import_module('{0}.{1}'.format(cogs_dir, cog))
        except Exception:     # noqa: E722
            logging.warning('Could not load {0}'.format(cog))
            traceback.print_exc()
            return

    logging.info('Preparing to create {0} tables.'.format(len(db.Table.all_tables())))

    async with pool.acquire() as con:
        await create_tables(con)


def run_bot():
    bot_storage.config = Config(Path('./config.toml'))
    loop = asyncio.get_event_loop()
    log = logging.getLogger()
    kwargs = {
        'command_timeout': 60,
        'max_size': 20,
        'min_size': 20,
    }
    url = 'postgresql://{1}:{2}@localhost/{0}'.format(
        bot_storage.config['postgresql_name'],
        bot_storage.config['postgresql_user'],
        bot_storage.config['postgresql_password'],
    )
    try:
        pool = loop.run_until_complete(db.Table.create_pool(url, **kwargs))
        loop.run_until_complete(database(pool))
    except Exception as e:
        log.exception('Could not set up PostgreSQL. Exiting.')
        return

    bot = SynthBot(pool)
    bot.run()


if __name__ == '__main__':
    run_bot()

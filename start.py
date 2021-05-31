import asyncio
import traceback

import psycopg2

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


def create_tables(connection):
    run = asyncio.get_event_loop().run_until_complete
    for table in db.Table.all_tables():
        try:
            run(table.create(connection=connection))
        except Exception:     # noqa: E722
            logging.warning('Failed creating table {0}'.format(table.tablename))
            traceback.print_exc()


def database():

    cogs = startup_extensions

    for cog in cogs:
        try:
            importlib.import_module('{0}.{1}'.format(cogs_dir, cog))
        except Exception:     # noqa: E722
            logging.warning('Could not load {0}'.format(cog))
            traceback.print_exc()
            return

    logging.info('Preparing to create {0} tables.'.format(len(db.Table.all_tables())))
    connection = psycopg2.connect(
        'dbname={0} user={1} password={2}'.format(
            bot_storage.config['postgresql_name'],
            bot_storage.config['postgresql_user'],
            bot_storage.config['postgresql_password'],
        ),
    )

    create_tables(connection)

    connection.commit()
    connection.cursor().close()
    connection.close()


def run_bot():
    bot_storage.config = Config(Path('./config.toml'))
    db.Table.create_data(
        bot_storage.config['postgresql_name'],
        bot_storage.config['postgresql_user'],
        bot_storage.config['postgresql_password'],
    )
    database()
    bot = SynthBot()
    bot.run()


if __name__ == '__main__':
    run_bot()

import asyncio
import traceback

import psycopg2

from bot.synth_bot import SynthBot, startup_extensions, cogs_dir
import bot.util.database as db
import bot as bot_storage
from bot.util.config import Config
from pathlib import Path
import importlib


def database():
    run = asyncio.get_event_loop().run_until_complete

    cogs = startup_extensions

    for ext in cogs:
        try:
            importlib.import_module(cogs_dir + "." + ext)
        except Exception:
            print(f'Could not load {ext}')
            traceback.print_exc()
            return

    print(f"Preparing to create {len(db.Table.all_tables())} tables.")
    connection = psycopg2.connect(
        f"dbname={bot_storage.config['postgresql_name']} user={bot_storage.config['postgresql_user']} password={bot_storage.config['postgresql_password']}")
    for table in db.Table.all_tables():
        try:
            run(table.create(connection=connection))
        except Exception:
            print(f"Failed creating table {table.tablename}")
            traceback.print_exc()
    connection.commit()
    connection.cursor().close()
    connection.close()


def run_bot():
    bot_storage.config = Config(Path("./config.toml"))
    db.Table.create_data(bot_storage.config['postgresql_name'], bot_storage.config['postgresql_user'], bot_storage.config['postgresql_password'])
    database()
    bot = SynthBot()
    bot.run()


if __name__ == '__main__':
    run_bot()

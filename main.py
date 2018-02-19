import asyncio
import datetime
import json
import logging

import sqlalchemy as sa

from abot.bot import Bot
from abot.dubtrack import DubtrackBotBackend, DubtrackMessage, DubtrackWS

logger = logging.getLogger()

metadata = sa.MetaData()
Songs = sa.Table('song_history', metadata,
                 sa.Column('id', sa.Integer, primary_key=True),
                 sa.Column('played', sa.Integer, unique=True),
                 sa.Column('skipped', sa.Boolean),
                 sa.Column('username', sa.Text),
                 sa.Column('song', sa.Text),
                 )


async def download_all_songs():
    dws = DubtrackWS()
    await dws.initialize()
    engine = get_engine()
    conn = engine.connect()
    with open('last_page') as fd:
        last_page = int(fd.read())
    await dws.get_room_id()
    insert_clause = Songs.insert()
    while True:
        logger.info(f'Doing page {last_page}')
        try:
            entries = await dws.get_history(page=last_page)
        except:
            logger.exception('Something went wrong, sleeping to retry')
            await asyncio.sleep(60)
            continue
        if not entries:
            logger.error(f'There are no entries in page {last_page}')
            await asyncio.sleep(60)
            break
        played = entries[0]['played']
        playtime = datetime.datetime.fromtimestamp(played / 1000)

        for entry in entries:
            try:
                trans = conn.begin()
                conn.execute(
                    insert_clause,
                    played=entry['played'],
                    username=entry['_user']['username'],
                    song=json.dumps(entry),
                    skipped=entry['skipped'],
                )
                trans.commit()
            except Exception as e:
                trans.rollback()
                logger.info(f'Duplicate entry {entry["played"]}: {e}')
        logger.info(f'Done page {last_page}, {playtime.isoformat()}')
        last_page += 1
    with open('last_page', mode='wt') as fd:
        fd.write(str(last_page))


ENGINE = None


def get_engine():
    global ENGINE
    if ENGINE:
        return ENGINE
    ENGINE = sa.create_engine('sqlite:///songs.sqlite3')
    return ENGINE


def create_sqlite_db():
    engine = get_engine()
    metadata.create_all(engine)


async def message_handler(message: DubtrackMessage):
    print(f'Received {message.text}')
    # await message.channel.say('Bot speaking here')


def run_bot():
    # Setup
    bot = Bot()
    dubtrack_backend = DubtrackBotBackend()
    dubtrack_backend.configure()
    bot.attach_backend(backend=dubtrack_backend)

    bot.add_event_handler(DubtrackMessage, func=message_handler)

    # Run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.run_forever())


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('abot.dubtrack').setLevel(logging.DEBUG)
    logging.getLogger('abot.dubtrack.layer1').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer2').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer3').setLevel(logging.WARNING)
    dubtrack = DubtrackWS()
    loop = asyncio.get_event_loop()
    # loop.run_until_complete(dubtrack.ws_api_consume())
    # create_sqlite_db()
    # loop.run_until_complete(download_all_songs())
    run_bot()

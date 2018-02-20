import asyncio
import datetime
import json
import logging
import time

import sqlalchemy as sa

from abot.bot import Bot, Event
from abot.dubtrack import DubtrackBotBackend, DubtrackMessage, DubtrackPlaying, DubtrackWS

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


async def playing_handler(ev: DubtrackPlaying):
    print(f'{id(ev)} Handling in playing_handler')
    played_ts = ev._data['song']['played'] / 1000
    song_length_ts = ev.song_length / 1000
    played = datetime.datetime.fromtimestamp(played_ts)
    ending = datetime.datetime.fromtimestamp(played_ts + song_length_ts)
    print(f'Playing {played} + {song_length_ts} = {ending}: {ev.song_name}')
    now = time.time()
    await asyncio.sleep(played_ts + song_length_ts - now)
    print(f'Song should be finishing now')


async def other_event_handler(ev: Event):
    print(f'{id(ev)} Handling in other_event_handler')


async def event_handler(ev: Event):
    print(f'{id(ev)} Handling in event_handler')


async def message_handler(ev: DubtrackMessage):
    print(f'{id(ev)} Handling in message_handler')
    # print(f'Received {ev.text}')
    # await ev.channel.say('Bot speaking here')


def run_bot():
    # Setup
    bot = Bot()
    dubtrack_backend = DubtrackBotBackend()
    with open('credentials.json') as f:
        config = json.load(f)

    # dubtrack_backend.configure(**config)
    bot.attach_backend(backend=dubtrack_backend)

    bot.add_event_handler(Event, func=event_handler)
    bot.add_event_handler(Event, func=other_event_handler)
    bot.add_event_handler(DubtrackMessage, func=message_handler)
    bot.add_event_handler(DubtrackPlaying, func=playing_handler)

    # Run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.run_forever())


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('abot.dubtrack').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer1').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer2').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer3').setLevel(logging.WARNING)
    dubtrack = DubtrackWS()
    loop = asyncio.get_event_loop()
    # loop.run_until_complete(dubtrack.ws_api_consume())
    # create_sqlite_db()
    # loop.run_until_complete(download_all_songs())
    run_bot()

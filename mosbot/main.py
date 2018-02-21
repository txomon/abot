import asyncio
import datetime
import json
import logging
import time

import sqlalchemy as sa

from abot.bot import Bot
from abot.dubtrack import DubtrackBotBackend, DubtrackMessage, DubtrackPlaying, DubtrackWS
from mosbot import config
from mosbot.db import SongsHistory, sqlite_get_engine

logger = logging.getLogger()


async def download_all_songs():
    dws = DubtrackWS()
    await dws.initialize()
    engine = await sqlite_get_engine()
    conn = await engine.connect()
    with open('last_page') as fd:
        last_page = int(fd.read())
    await dws.get_room_id()
    errors_together = 0
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
            trans = await conn.begin()
            try:
                query = sa.insert(SongsHistory).values({
                    'played': entry['played'],
                    'username': entry['_user']['username'],
                    'song': json.dumps(entry),
                    'skipped': entry['skipped'],
                })
                await conn.execute(query)
                await trans.commit()
                errors_together = 0
            except Exception as e:
                errors_together += 1
                await trans.rollback()
                logger.info(f'Duplicate entry {entry["played"]}: {e}')
                if errors_together > 3:
                    break
        else:
            logger.info(f'Done page {last_page}, {playtime.isoformat()}')
            last_page += 1
            continue
        logger.info('Amount of errors suggest we catched up')
        break
    with open('last_page', mode='wt') as fd:
        fd.write(str(last_page))


async def playing_handler(ev: DubtrackPlaying):
    print(f'{id(ev)} Handling in playing_handler')
    played_ts = ev.played
    song_length_ts = ev.length
    played = datetime.datetime.fromtimestamp(played_ts)
    ending = datetime.datetime.fromtimestamp(played_ts + song_length_ts)
    print(f'Playing {played} + {song_length_ts} = {ending}: {ev.song_name}')
    now = time.time()
    await asyncio.sleep(played_ts + song_length_ts - now)
    print(f'Song should be finishing now')


async def message_handler(ev: DubtrackMessage):
    print(f'{id(ev)} Handling in message_handler')
    # print(f'Received {ev.text}')
    # await ev.channel.say('Bot speaking here')


def mos_bot():
    logging.basicConfig(level=logging.INFO)
    # Setup
    bot = Bot()
    dubtrack_backend = DubtrackBotBackend()
    dubtrack_backend.configure(username=config.DUBTRACK_USERNAME, password=config.DUBTRACK_PASSWORD)
    bot.attach_backend(backend=dubtrack_backend)

    bot.add_event_handler(DubtrackMessage, func=message_handler)
    bot.add_event_handler(DubtrackPlaying, func=playing_handler)

    # Run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.run_forever())


def mos_history():
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(download_all_songs())
    # loop.run_until_complete(save_history_songs())


if __name__ == '__main__':
    logging.getLogger('abot.dubtrack').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer1').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer2').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer3').setLevel(logging.WARNING)
    dubtrack = DubtrackWS()
    # loop.run_until_complete(dubtrack.ws_api_consume())
    # create_sqlite_db()

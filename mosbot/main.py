import asyncio
import datetime
import json
import logging.config
import os
import pprint
import sys
import time
import traceback

import sqlalchemy as sa

from abot.dubtrack import DubtrackMessage, DubtrackPlaying, DubtrackSkip, DubtrackWS

logger = logging.getLogger(__name__)


async def download_all_songs():
    dws = DubtrackWS()
    await dws.initialize()
    engine = sqlite_get_engine()
    conn = engine.connect()
    with open('last_page') as fd:
        last_page = int(fd.read())
    await dws.get_room_id()
    errors_together = 0
    while True:
        logger.info(f'Doing page {last_page}')
        try:
            entries = dws.get_history(page=last_page)
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
            trans = conn.begin()
            try:
                query = sa.insert(SongsHistory).values({
                    'played': entry['played'],
                    'username': entry['_user']['username'],
                    'song': json.dumps(entry),
                    'skipped': entry['skipped'],
                })
                conn.execute(query)
                trans.commit()
                errors_together = 0
            except Exception as e:
                errors_together += 1
                trans.rollback()
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


last_song = None


async def playing_handler(ev: DubtrackPlaying):
    global last_song

    played_ts = ev.played
    last_song = played_ts
    song_length_ts = ev.length
    played = datetime.datetime.fromtimestamp(played_ts)
    ending = datetime.datetime.fromtimestamp(played_ts + song_length_ts)

    print(f'Song {played_ts} playing')


async def skip_handler(ev: DubtrackSkip):
    ts = time.time()
    print(f'Song {last_song} skipped at {ts}')


async def message_handler(ev: DubtrackMessage):
    print(f'{id(ev)} Handling in message_handler')
    # print(f'Received {ev.text}')
    # await ev.channel.say('Bot speaking here')


def setup_logging(debug=False):
    filename = 'logging.conf' if not debug else 'logging-debug.conf'
    logging.config.fileConfig(os.path.join(os.path.dirname(__file__), filename), disable_existing_loggers=False)
    if debug:
        logger.debug('Level is debug now')
        #logging.getLogger('abot.dubtrack.layer3').setLevel(logging.DEBUG)
        def excepthook(type, value, tb):
            traceback.print_exception(type, value, tb)

            while tb.tb_next:
                tb = tb.tb_next

            logger.error(f'Locals: {pprint.pformat(tb.tb_frame.f_locals)}')

        sys.excepthook = excepthook
    else:
        logger.info('Level is info now')



if __name__ == '__main__':
    logging.getLogger('abot.dubtrack').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer1').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer2').setLevel(logging.WARNING)
    logging.getLogger('abot.dubtrack.layer3').setLevel(logging.WARNING)
    dubtrack = DubtrackWS()
    # loop.run_until_complete(dubtrack.ws_api_consume())
    # create_sqlite_db()

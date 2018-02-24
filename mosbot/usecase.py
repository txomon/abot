# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import datetime
import json
import logging

import aiopg.sa as asa
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as psa

from abot.dubtrack import DubtrackWS
from mosbot import db
from mosbot.config import BotConfig

logger = logging.getLogger(__name__)


async def save_history_songs():
    engine = await db.get_engine()
    last_song = await load_bot_data(BotConfig.last_saved_history)
    if not last_song:
        logger.error('There is no bot data regarding last saved playback')
        return

    dws = DubtrackWS()
    await dws.initialize()

    history_songs = {}
    found_last_song = False
    for page in range(1, 1000):
        if found_last_song:
            break  # We want to do whole pages just in case...
        songs = await dws.get_history(page)
        for song in songs:
            played = song['played']
            if played <= last_song:
                found_last_song = True
            history_songs[played] = song

    songs = []
    tasks = {}
    # Logic here: [ ][ ][s][s][ ][s][ ]
    # Groups:     \-/\-/\-------/\----/
    for song, in sorted(history_songs.items()):
        song = json.loads(song)
        songs.append(song)
        if not song['skipped']:
            tasks[song['played']] = asyncio.ensure_future(
                save_history_chunk(songs, await engine.acquire())
            )
            songs = []

    await asyncio.wait(tasks.values())

    last_successful_song = None
    for last_song, task in sorted(tasks.items()):
        if task.exception():
            break
        last_successful_song = last_song
    if last_successful_song:
        await save_bot_data(BotConfig.last_saved_history, last_successful_song)


async def save_history_chunk(songs, conn: asa.SAConnection):
    # {'__v': 0,
    #  '_id': '583bf4a9d9abb248008a698a',
    #  '_song': {
    #      '__v': 0,
    #      '_id': '5637c2cf7d7d3f2200b05659',
    #      'created': '2015-11-02T20:08:47.588Z',
    #      'fkid': 'eOwwLhMPRUE',
    #      'images': {
    #          'thumbnail': 'https://i.ytimg.com/vi/eOwwLhMPRUE/hqdefault.jpg',
    #          'youtube': {
    #              'default': {
    #                  'height': 90,
    #                  'url': 'https://i.ytimg.com/vi/eOwwLhMPRUE/default.jpg',
    #                  'width': 120
    #              },
    #              'high': {
    #                  'height': 360,
    #                  'url': 'https://i.ytimg.com/vi/eOwwLhMPRUE/hqdefault.jpg',
    #                  'width': 480
    #              },
    #              'maxres': {
    #                  'height': 720,
    #                  'url': 'https://i.ytimg.com/vi/eOwwLhMPRUE/maxresdefault.jpg',
    #                  'width': 1280
    #              },
    #              'medium': {
    #                  'height': 180,
    #                  'url': 'https://i.ytimg.com/vi/eOwwLhMPRUE/mqdefault.jpg',
    #                  'width': 320
    #              },
    #              'standard': {
    #                  'height': 480,
    #                  'url': 'https://i.ytimg.com/vi/eOwwLhMPRUE/sddefault.jpg',
    #                  'width': 640
    #              }
    #          }
    #      },
    #      'name': 'Craig Armstrong - Dream Violin',
    #      'songLength': 204000,
    #      'type': 'youtube'
    #  },
    #  '_user': {
    #      '__v': 0,
    #      '_id': '57595c7a16c34f3d00b5ea8d',
    #      'created': 1465474170519,
    #      'dubs': 0,
    #      'profileImage': {
    #          'bytes': 72094,
    #          'etag': 'fdcdd43edcaaec225a6dcd9701e62be1',
    #          'format': 'png',
    #          'height': 500,
    #          'public_id': 'user/57595c7a16c34f3d00b5ea8d',
    #          'resource_type': 'image',
    #          'secure_url':
    #              'https://res.cloudinary.com/hhberclba/image/upload/v1465474392/user'
    #              '/57595c7a16c34f3d00b5ea8d.png',
    #          'tags': [],
    #          'type': 'upload',
    #          'url': 'http://res.cloudinary.com/hhberclba/image/upload/v1465474392/user'
    #                 '/57595c7a16c34f3d00b5ea8d.png',
    #          'version': 1465474392,
    #          'width': 500
    #      },
    #      'roleid': 1,
    #      'status': 1,
    #      'username': 'masterofsoundtrack'
    #  },
    #  'created': 1480324264803,
    #  'downdubs': 0,
    #  'isActive': True,
    #  'isPlayed': True,
    #  'order': 243,
    #  'played': 1480464322618,
    #  'roomid': '561b1e59c90a9c0e00df610b',
    #  'skipped': False,
    #  'songLength': 204000,
    #  'songid': '5637c2cf7d7d3f2200b05659',
    #  'updubs': 1,
    #  'userid': '57595c7a16c34f3d00b5ea8d'
    #  }
    for retries in range(10):
        previous_song, previous_playback_id = {}, None
        trans = await conn.begin()
        for song in songs:
            # Generate Action skip for the previous Playback entry
            song_played = datetime.datetime.utcfromtimestamp(song['played'] / 1000)
            if previous_song.get('skipped'):
                query = sa.select([db.UserAction.c.id]) \
                    .where(db.UserAction.c.action == db.Action.skip) \
                    .where(db.UserAction.c.playback_id == previous_playback_id)

                user_action_id = await (await conn.execute(query)).first()
                if not user_action_id:
                    entry = {
                        'ts': song_played,
                        'playback_id': previous_playback_id,
                        'action': db.Action.skip,
                    }
                    query = psa.insert(db.UserAction).values(entry).on_conflict_do_nothing()
                    user_action_id = await (await conn.execute(query)).first()
                    if not user_action_id:
                        logger.error(
                            f'Error UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')
                        await trans.rollback()
                        raise ValueError(
                            f'\tCollision UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')
                    else:
                        logger.debug(f'UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')
                else:
                    logger.debug(f'\tExists UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')

            # Query or create the User for the Playback entry
            dtid = song['userid']
            username = song['_user']['username']
            entry = {
                'dtid': dtid,
                'username': username,
            }
            query = sa.select([db.User.c.id]).where(db.User.c.dtid == dtid)
            user_id = await (await conn.execute(query)).first()
            if not user_id:
                query = psa.insert(db.User) \
                    .values(entry) \
                    .returning(db.User.c.id) \
                    .on_conflict_do_update(
                    index_elements=[db.User.c.dtid],
                    set_=entry
                )
                user_id = await (await conn.execute(query)).first()
                user_id, = user_id.as_tuple()
                if not user_id:
                    logger.error(f'Error User#{user_id} {username}#{dtid} by {song_played}')
                    await trans.rollback()
                    raise ValueError(f'Error generating User {username}#{dtid} for {song_played}')
                else:
                    logger.debug(f'User#{user_id} {username}#{dtid} by {song_played}')
            else:
                logger.debug(f'\tExists User#{user_id} {username}#{dtid} by {song_played}')
                user_id, = user_id.as_tuple()

            # Query or create the Track entry for this Playback entry
            origin = getattr(db.Origin, song['_song']['type'])
            length = song['_song']['songLength']
            name = song['_song']['name']
            fkid = song['_song']['fkid']

            entry = {
                'length': length / 1000,
                'name': name,
                'origin': origin,
                'extid': fkid,
            }

            query = sa.select([db.Track.c.id]) \
                .where(db.Track.c.extid == fkid) \
                .where(db.Track.c.origin == origin)
            track_id = await (await conn.execute(query)).first()

            if not track_id:
                query = psa.insert(db.Track) \
                    .values(entry) \
                    .returning(db.Track.c.id) \
                    .on_conflict_do_update(
                    index_elements=[db.Track.c.origin, db.Track.c.extid],
                    set_=entry
                )

                track_id = await (await conn.execute(query)).first()
                track_id, = track_id.as_tuple()

                if not track_id:
                    logger.error(f'Error Track#{track_id} {origin}#{fkid} by {song_played}')
                    await trans.rollback()
                    raise ValueError(f'Error generating Track {origin}#{fkid} for {song_played}')
                else:
                    logger.debug(f'Track#{track_id} {origin}#{fkid} by {song_played}')
            else:
                logger.debug(f'\tExists Track#{track_id} {origin}#{fkid} by {song_played}')
                track_id, = track_id.as_tuple()

            # Query or create the Playback entry
            entry = {
                'track_id': track_id,
                'user_id': user_id,
                'start': song_played,
            }
            query = sa.select([db.Playback.c.id]) \
                .where(db.Playback.c.start == song_played)
            playback_id = await (await conn.execute(query)).first()

            if not playback_id:
                query = psa.insert(db.Playback) \
                    .values(entry) \
                    .returning(db.Playback.c.id) \
                    .on_conflict_do_update(
                    index_elements=[db.Playback.c.start],
                    set_=entry
                )
                playback_id = await (await conn.execute(query)).first()
                playback_id, = playback_id.as_tuple()

                if not playback_id:
                    logger.error(f'Error Playback#{playback_id} track:{track_id} user_id:{fkid} start:{song_played}')
                    await trans.rollback()
                    raise ValueError(f'Error generating Playback track:{track_id} user_id:{fkid} start:{song_played}')
                else:
                    logger.debug(f'Playback#{playback_id} track:{track_id} user_id:{fkid} start:{song_played}')
            else:
                logger.debug(f'\tExists Playback#{playback_id} track:{track_id} user_id:{fkid} start:{song_played}')
                playback_id, = playback_id.as_tuple()

            # Query or create the UserAction<upvote> UserAction<downvote> entries
            for action, dubkey in ((db.Action.upvote, 'updubs'), (db.Action.downvote, 'downdubs')):
                # if no updubs/downdubs
                votes = song[dubkey]
                if not votes:
                    continue

                query = sa.select([sa.func.count(db.UserAction.c.id)]) \
                    .where(db.UserAction.c.action == action) \
                    .where(db.UserAction.c.playback_id == playback_id)
                action_count = await (await conn.execute(query)).first()
                action_count, = action_count.as_tuple()
                if action_count == votes:
                    continue
                if action_count > votes:
                    logger.error(f'Playback {playback_id} votes: real {dubkey} > {action_count} db')
                    continue
                # There are less than they should
                for _ in range(votes - action_count):
                    entry = {
                        'ts': song_played,
                        'playback_id': playback_id,
                        'action': action,
                    }
                    query = psa.insert(db.UserAction).values(entry)
                    user_action_id = await (await conn.execute(query)).first()
                    if not user_action_id:
                        logger.error(
                            f'\tError UserAction<vote>#{user_action_id} {playback_id}({song_played})')
                        await trans.rollback()
                        raise ValueError(
                            f'\tCollision UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')
                    else:
                        logger.debug(f'UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')

            previous_song, previous_playback_id = song, playback_id
        try:
            await trans.commit()
            break
        except:
            await trans.rollback()
    else:
        logger.error(f'Failed to commit song-chunk: [{", ".join(songs)}]')
    await conn.close()


async def save_bot_data(key, value):
    engine = await db.get_engine()
    async with  engine.acquire() as conn:
        entry = {
            'key': key,
            'value': value
        }
        query = psa.insert([db.BotData]) \
            .values(entry) \
            .on_conflict_do_update(
            index_elements=[db.BotData.c.key],
            set_=entry
        )
        result = await (await conn.execute(query)).first()
        if not result:
            logger.error(f'Failed to save {key} value in database')


async def load_bot_data(key):
    engine = await db.get_engine()
    async with  engine.acquire() as conn:
        query = sa.select([db.BotData.c.value]).where(db.BotData.c.key == key)
        result = await (await conn.execute(query)).first()
        if not result:
            logger.info(f'Failed to load {key} value from database')
            return None
        return result.as_tuple()[0]

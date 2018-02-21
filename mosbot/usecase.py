# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import datetime
import json
import logging

import aiopg.sa as asa
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as psa

from mosbot.db import Action, Origin, Playback, SongsHistory, Track, User, UserAction, get_engine, sqlite_get_engine

logger = logging.getLogger(__name__)


async def save_history_songs():
    sqlite_engine = await sqlite_get_engine()
    conn = await sqlite_engine.connect()
    query = sa.select([SongsHistory.c.song]).order_by(sa.asc(SongsHistory.c.played)).limit(2)
    result = await conn.execute(query)

    engine = await get_engine()

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
                song_played = datetime.datetime.fromtimestamp(song['played'] / 1000)
                if previous_song.get('skipped'):
                    query = sa.select([UserAction.c.id]) \
                        .where(UserAction.c.action == Action.skip) \
                        .where(UserAction.c.ts == song_played) \
                        .where(UserAction.c.playback_id == previous_playback_id)

                    user_action_id = await (await conn.execute(query)).first()
                    if not user_action_id:
                        entry = {
                            'ts': song_played,
                            'playback_id': previous_playback_id,
                            'action': Action.skip,
                        }
                        query = psa.insert(UserAction).values(entry).on_conflict_do_nothing()
                        user_action_id = await (await conn.execute(query)).first()
                        if not user_action_id:
                            logger.info(
                                f'\tCollision UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')
                        else:
                            logger.info(f'UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')
                    else:
                        logger.info(
                            f'\tExists UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')

                # Query or create the User for the Playback entry
                dtid = song['userid']
                username = song['_user']['username']
                entry = {
                    'dtid': dtid,
                    'username': username,
                }

                query = psa.insert(User).values(entry).returning([User.c.id]).on_conflict_update()
                user_id = await (await conn.execute(query)).first()
                if not user_id:
                    await trans.rollback()
                    raise ValueError(f'Error generating User {username}#{dtid} for {song_played}')
                else:
                    logger.info(f'User#{user_id} {username}#{dtid} by {song_played}')

                # Query or create the Track entry for this Playback entry
                origin = getattr(Origin, song['_song']['type'])
                length = song['_song']['songLength']
                name = song['_song']['name']
                fkid = song['_song']['fkid']

                entry = {
                    'length': length / 1000,
                    'name': name,
                    'origin': origin,
                    'extid': fkid,
                }
                query = psa.insert(Track).values(entry).returning([Track.c.id]).on_conflict_update()
                track_id = await (await conn.execute(query)).first()
                if not track_id:
                    await trans.rollback()
                    raise ValueError(f'Error generating Track {origin}#{fkid} for {song_played}')
                else:
                    logger.info(f'Track#{track_id} {origin}#{fkid} by {song_played}')

                # Query or create the Playback entry
                entry = {
                    'track_id': track_id,
                    'user_id': user_id,
                    'start': song_played,
                }
                query = psa.insert(Playback).values(entry).returning([Playback.c.id]).on_conflict_update()
                playback_id = await (await conn.execute(query)).first()
                if not playback_id:
                    await trans.rollback()
                    raise ValueError(f'Error generating Playback track:{track_id} user_id:{fkid} start:{song_played}')
                else:
                    logger.info(f'Playback#{playback_id} track:{track_id} user_id:{fkid} start:{song_played}')

                previous_song, previous_playback_id = song, playback_id
            try:
                await trans.commit()
                break
            except:
                await trans.rollback()
        else:
            logger.error(f'Failed to commit song-chunk: [{", ".join(songs)}]')

    songs = []

    # Logic here: [ ][ ][s][s][ ][s][ ]
    # Groups:     \-/\-/\-------/\----/
    async for song, in result:
        song = json.loads(song)
        songs.append(song)
        if not song['skipped']:
            asyncio.ensure_future(save_history_chunk(songs, await engine.connect()))
            songs = []

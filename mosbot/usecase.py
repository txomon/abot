# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import datetime
import logging
import time

import aiopg.sa as asa
import sqlalchemy as sa

from abot.dubtrack import DubtrackDub, DubtrackEntity, DubtrackPlaying, DubtrackSkip, DubtrackWS
from mosbot import db
from mosbot.db import Action, BotConfig, Origin
from mosbot.query import get_dub_action, get_last_playback, get_playback, get_track, get_user, load_bot_data, \
    query_simplified_user_actions, save_bot_data, save_playback, save_track, save_user, save_user_action

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
    played = time.time()
    logger.info(f'Starting page retrieval until {last_song}')
    for page in range(1, 1000):
        logger.debug(f'Retrieving page {page}, {len(history_songs)} songs, looking for {last_song} now at {played}')
        if found_last_song:
            break  # We want to do whole pages just in case...
        songs = await dws.get_history(page)
        for song in songs:
            played = song['played'] / 1000
            if played <= last_song:
                found_last_song = True
            history_songs[played] = song

    songs = []
    tasks = {}
    # Logic here: [ ][ ][s][s][ ][s][ ]
    # Groups:     \-/\-/\-------/\----/
    logger.info('Saving data chunks in database')
    for played, song in sorted(history_songs.items()):
        songs.append(song)
        if not song['skipped']:
            tasks[played] = asyncio.ensure_future(
                save_history_chunk(songs, await engine.acquire())
            )
            songs = []

    logger.debug('Waiting for data to be saved')
    await asyncio.wait(tasks.values())

    last_successful_song = None
    for last_song, task in sorted(tasks.items()):
        if task.exception():
            logger.error(f'Saving task failed at {last_song}')
            break
        last_successful_song = last_song
    if last_successful_song:
        logger.info(f'Successfully saved until {last_successful_song}')
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
    song_played = None
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
                    user_action = await save_user_action(user_action_dict={
                        'ts': song_played,
                        'playback_id': previous_playback_id,
                        'action': db.Action.skip,
                    }, conn=conn)
                    user_action_id = user_action['id']
                    if not user_action_id:
                        logger.error(
                            f'Error UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')
                        await trans.rollback()
                        raise ValueError(
                            f'\tCollision UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')

            # Query or create the User for the Playback entry
            dtid = song['userid']
            username = song['_user']['username']
            user = await get_user(user_dict={'dtid': dtid}, conn=conn)
            if not user:
                user = await save_user(user_dict={'dtid': dtid, 'username': username}, conn=conn)
                if not user:
                    await trans.rollback()
                    raise ValueError('Impossible to create/save the user')
            user_id = user['id']

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

            track = await get_track(track_dict=entry, conn=conn)
            if not track:
                track = await save_track(track_dict=entry, conn=conn)
                if not track:
                    logger.error(f'Error Track#{track_id} {origin}#{fkid} by {song_played}')
                    await trans.rollback()
                    raise ValueError(f'Error generating Track {origin}#{fkid} for {song_played}')
            track_id = track['id']

            # Query or create the Playback entry
            entry = {
                'track_id': track_id,
                'user_id': user_id,
                'start': song_played,
            }
            playback = await get_playback(playback_dict=entry, conn=conn)
            if not playback:
                playback = await save_playback(playback_dict=entry, conn=conn)
                if not playback:
                    logger.error(f'Error Playback#{playback_id} track:{track_id} user_id:{fkid} start:{song_played}')
                    await trans.rollback()
                    raise ValueError(f'Error generating Playback track:{track_id} user_id:{fkid} start:{song_played}')
            playback_id = playback['id']

            # Query or create the UserAction<upvote> UserAction<downvote> entries
            user_actions = await query_simplified_user_actions(playback_id, conn=conn)
            for dubkey in ('updubs', 'downdubs'):
                # if no updubs/downdubs
                votes = song[dubkey]
                action = get_dub_action(dubkey)

                if not votes:
                    continue

                action_user_actions = [a for a in user_actions if a['action'] == action]
                action_count = len(action_user_actions)
                if action_count == votes:
                    continue
                if action_count > votes:
                    logger.error(f'Playback {playback_id} votes: real {dubkey} > {action_count} db')
                    continue
                # There are less than they should
                for _ in range(votes - action_count):
                    user_action = await save_user_action(user_action_dict={
                        'ts': song_played,
                        'playback_id': playback_id,
                        'action': action,
                    }, conn=conn)
                    if not user_action:
                        logger.error(
                            f'\tError UserAction<vote>#{user_action_id} {playback_id}({song_played})')
                        await trans.rollback()
                        raise ValueError(
                            f'\tCollision UserAction<skip>#{user_action_id} {previous_playback_id}({song_played})')

            previous_song, previous_playback_id = song, playback_id
        try:
            await trans.commit()
            logger.info(f'Saved songs up to {song_played}')
            break
        except:
            await trans.rollback()
    else:
        logger.error(f'Failed to commit song-chunk: [{", ".join(songs)}]')
    await conn.close()


async def ensure_dubtrack_entity(user: DubtrackEntity, *, conn=None):
    dtid = user.id
    username = user.username
    user = await get_user(user_dict={'dtid': dtid}, conn=conn)
    if not user:
        user = await save_user(user_dict={'dtid': dtid, 'username': username}, conn=conn)
        if not user:
            raise ValueError('Impossible to create/save the user')
    return user


async def ensure_dubtrack_playing(event: DubtrackPlaying, *, conn=None):
    user = await ensure_dubtrack_entity(event.sender)
    user_id = user['id']
    track_entry = {
        'length': event.length.total_seconds(),
        'origin': getattr(Origin, event.song_type),
        'extid': event.song_external_id,
        'name': event.song_name,
    }
    track = await get_track(track_dict=track_entry, conn=conn)
    if not track:
        track = await save_track(track_dict=track_entry, conn=conn)
        if not track:
            raise ValueError(f"Couldn't save track {track_entry}")
    track_id = track['id']

    playback_entry = {
        'user_id': user_id,
        'track_id': track_id,
        'start': event.played,
    }

    playback = await get_playback(playback_dict=playback_entry, conn=conn)
    if not playback:
        await save_playback(playback_dict=playback_entry, conn=conn)


async def ensure_dubtrack_skip(event: DubtrackSkip, *, conn=None):
    playback = await get_last_playback(conn=conn)
    user = await ensure_dubtrack_entity(event.sender)
    playback_id = playback['id']
    user_id = user['id']
    await save_user_action(user_action_dict={
        'playback_id': playback_id,
        'user_id': user_id,
        'action': Action.skip,
        'ts': datetime.datetime.utcnow(),
    })


async def ensure_dubtrack_dub(event: DubtrackDub, *, conn=None):
    playback = await get_last_playback(conn=conn)
    if not event.played == playback['start']:
        logger.error(f'Last saved playback is {playback["start"]} but this vote is for {event.played}')
        return
    playback_id = playback['id']

    user = await ensure_dubtrack_entity(event.sender, conn=conn)
    user_id = user['id']
    action_type = get_dub_action(event.dubtype)

    user_action_dict = {
        'ts': datetime.datetime.utcnow(),
        'playback_id': playback_id,
        'user_id': user_id,
        'action': action_type,
    }
    await save_user_action(user_action_dict=user_action_dict, conn=conn)

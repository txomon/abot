# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import logging
from typing import List, Optional

import sqlalchemy as sa
import sqlalchemy.sql.functions as saf
from asyncio_extras import async_contextmanager
from sqlalchemy.dialects import postgresql as psa

from mosbot import db
from mosbot.db import Action, Playback, Track, User, UserAction, get_engine

logger = logging.getLogger(__name__)


@async_contextmanager
async def ensure_connection(conn):
    provided_connection = bool(conn)
    if not provided_connection:
        conn = await (await get_engine()).acquire()
    try:
        yield conn
    finally:
        if not provided_connection:
            await conn.close()


async def get_user(*, user_dict: dict, conn=None) -> Optional[dict]:
    assert user_dict

    sq = sa.select([User])
    if 'id' in user_dict:
        sq = sq.where(User.c.id == user_dict['id'])
    else:
        if 'dtid' in user_dict:
            sq = sq.where(User.c.dtid == user_dict['dtid'])
        elif 'username' in user_dict:
            sq = sq.where(User.c.username == user_dict['username'])
        else:
            raise ValueError(f'Not enough parameters in select spec {user_dict}')

    async with ensure_connection(conn) as conn:
        user = await (await conn.execute(sq)).first()
        return dict(user) if user else user


async def save_user(*, user_dict: dict, conn=None) -> Optional[dict]:
    assert 'username' in user_dict or 'dtid' in user_dict
    query = psa.insert(User) \
        .values(user_dict) \
        .on_conflict_do_update(
        index_elements=[User.c.dtid],
        set_=user_dict
    )
    async with ensure_connection(conn) as conn:
        user = await (await conn.execute(query)).first()
        return dict(user) if user else user


async def get_track(*, track_dict: dict, conn=None) -> Optional[dict]:
    assert 'id' in track_dict or 'extid' in track_dict
    sq = sa.select([Track])

    if 'id' in track_dict:
        sq = sq.where(Track.c.id == track_dict['id'])
    elif 'extid' in track_dict:
        sq = sq.where(Track.c.extid == track_dict['extid'])
        if 'origin' in track_dict:
            sq = sq.where(Track.c.origin == track_dict['origin'])
    else:
        raise ValueError(f'Not enough parameters for selecting Track, {track_dict}')

    async with ensure_connection(conn) as conn:
        track = await (await conn.execute(sq)).first()
        return dict(track) if track else track


async def save_track(*, track_dict: dict, conn=None) -> Optional[dict]:
    assert track_dict
    query = psa.insert(Track) \
        .values(track_dict) \
        .on_conflict_do_update(
        index_elements=[Track.c.extid, Track.c.origin],
        set_=track_dict
    )
    async with ensure_connection(conn) as conn:
        track = await (await conn.execute(query)).first()
        if not track:
            return track
        track = dict(track)
        track.update(track_dict)
        return track


async def get_playback(*, playback_dict: dict, conn=None) -> Optional[dict]:
    sq = sa.select([Playback])

    if 'id' in playback_dict:
        sq = sq.where(Playback.c.id == playback_dict['id'])
    elif 'start' in playback_dict:
        sq = sq.where(Playback.c.start == playback_dict['start'])
    else:
        raise ValueError(f'Need either ID or start for getting a playback: {playback_dict}')

    async with ensure_connection(conn) as conn:
        playback = await (await conn.execute(sq)).first()
        return dict(playback) if playback else playback


async def save_playback(*, playback_dict: dict, conn=None) -> Optional[dict]:
    assert {'track_id', 'start', 'user_id'} <= set(playback_dict.keys())
    query = psa.insert(Playback) \
        .values(playback_dict) \
        .on_conflict_do_update(
        index_elements=[Playback.c.start],
        set_=playback_dict
    )
    async with ensure_connection(conn) as conn:
        playback = await (await conn.execute(query)).first()
        return dict(playback) if playback else playback


async def get_user_action(*, user_action_dict: dict, conn=None) -> Optional[dict]:
    sq = sa.select([UserAction])

    if 'id' in user_action_dict:
        sq = sq.where(UserAction.c.id == user_action_dict['id'])
    else:
        raise ValueError(f'Need ID for getting a user action: {user_action_dict}')

    async with ensure_connection(conn) as conn:
        useraction = await (await conn.execute(sq)).first()
        return dict(useraction) if useraction else useraction


async def save_user_action(*, user_action_dict: dict, conn=None) -> Optional[dict]:
    assert 'playback_id' in user_action_dict
    query = psa.insert(UserAction) \
        .values(user_action_dict) \
        .on_conflict_do_update(
        index_elements=[UserAction.c.id],
        set_=user_action_dict
    )
    async with ensure_connection(conn) as conn:
        useraction = await (await conn.execute(query)).first()
        return dict(useraction) if useraction else useraction


async def delete_user_action(*, user_action_id, conn=None):
    query = sa.delete(UserAction) \
        .where(UserAction.c.id == user_action_id)
    async with ensure_connection(conn) as conn:
        deleted_rows = (await conn.execute(query)).rowcount
        return deleted_rows


async def save_bot_data(key, value, *, conn=None):
    entry = {
        'key': key,
        'value': value
    }
    query = psa.insert(db.BotData) \
        .values(entry) \
        .on_conflict_do_update(
        index_elements=[db.BotData.c.key],
        set_=entry
    )
    async with ensure_connection(conn) as conn:
        result = await (await conn.execute(query)).first()
        if not result:
            logger.error(f'Failed to save {key} value in database')


async def load_bot_data(key, *, conn=None):
    query = sa.select([db.BotData.c.value]).where(db.BotData.c.key == key)
    async with ensure_connection(conn) as conn:
        result = await (await conn.execute(query)).first()
        if not result:
            logger.info(f'Failed to load {key} value from database')
            return None
        return result.as_tuple()[0]


async def get_last_playback(*, conn=None) -> dict:
    query = sa.select([db.Playback]) \
        .order_by(sa.desc(db.Playback.c.start)) \
        .limit(1)
    async with ensure_connection(conn) as conn:
        result = await (await conn.execute(query)).first()
        return dict(result) if result else None


async def get_user_user_actions(user_id, *, conn=None) -> List[dict]:
    query = sa.select([db.UserAction]) \
        .where(UserAction.c.user_id == user_id)
    result = []
    async with ensure_connection(conn) as conn:
        async for user_action in await conn.execute(query):
            result.append(dict(user_action))
        return result


async def get_user_dub_user_actions(user_id, *, conn=None) -> List[dict]:
    query = sa.select([db.UserAction]) \
        .where(UserAction.c.user_id == user_id) \
        .where(UserAction.c.action in [Action.upvote, Action.downvote])
    async with ensure_connection(conn) as conn:
        result = []
        async for user_action in await conn.execute(query):
            result.append(dict(user_action))
        return result


def get_dub_action(dub):
    upvote = {'upvote', 'updub', 'updubs', }
    downvote = {'downvote', 'downdub', 'downdubs', }
    if dub in upvote:
        return Action.upvote
    elif dub in downvote:
        return Action.downvote
    else:
        logger.error(f'Tried to convert {dub} into Action')
        raise ValueError(f'Tried to convert {dub} into Action')


def get_opposite_dub_action(dub):
    upvote = {'upvote', 'updub', 'updubs', }
    downvote = {'downvote', 'downdub', 'downdubs', }
    if dub in upvote:
        return Action.downvote
    elif dub in downvote:
        return Action.upvote
    else:
        logger.error(f'Tried to convert {dub} into Action')
        raise ValueError(f'Tried to convert {dub} into Action')


async def query_simplified_user_actions(playback_id, *, conn=None) -> List[dict]:
    sub_query = sa.select([
        db.UserAction.c.user_id,
        saf.max(db.UserAction.c.ts).label('ts'),
        db.UserAction.c.playback_id,
    ]).where(
        db.UserAction.c.playback_id == playback_id
    ).group_by(
        db.UserAction.c.user_id,
        db.UserAction.c.playback_id,
        sa.case([
            (db.UserAction.c.user_id.is_(None), db.UserAction.c.id),
        ], else_=0)
    ).alias()

    query = sa.select([
        sa.distinct(db.UserAction.c.id),
        db.UserAction.c.action,
        db.UserAction.c.playback_id,
        db.UserAction.c.ts,
        db.UserAction.c.user_id,
    ]).select_from(
        db.UserAction.join(
            sub_query,
            sa.and_(
                sub_query.c.ts == db.UserAction.c.ts,
                db.UserAction.c.playback_id == sub_query.c.playback_id,
                sa.case([
                    (sa.and_(
                        db.UserAction.c.user_id.is_(None),
                        sub_query.c.user_id.is_(None)
                    ), sa.true())
                ], else_=db.UserAction.c.user_id == sub_query.c.user_id)
            )
        )
    )
    async with ensure_connection(conn) as conn:
        result = []
        async for user_action in await conn.execute(query):
            result.append(dict(user_action))
        return result

# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import enum
from typing import Any, Optional

import aiopg.sa as asa
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as psa
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import functions

from mosbot import config


class utcnow(functions.FunctionElement):  # noqa
    key = 'utcnow'
    type = sa.DateTime(timezone=True)


@compiles(utcnow, 'postgresql')
def _pg_utcnow(element, compiler, **kwargs):
    return "(statement_timestamp() AT TIME ZONE 'utc')::TIMESTAMP WITH TIME ZONE"


ENGINE = None


async def get_engine():
    global ENGINE
    if ENGINE:
        return ENGINE
    ENGINE = await asa.create_engine(config.DATABASE_URL)
    return ENGINE


async def ensure_connection(conn):
    provided_connection = bool(conn)
    if not provided_connection:
        conn = await (await get_engine()).aquire()
    yield conn
    if not provided_connection:
        await conn.close()


metadata = sa.MetaData()

User = sa.Table('user', metadata,
                sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                sa.Column('dtid', sa.Text, unique=True, nullable=False),
                sa.Column('username', sa.Text, nullable=False),
                sa.Column('country', sa.Text, nullable=True),
                )


async def get_user(*, user_dict: dict, conn=None) -> Any[dict, None]:
    assert user_dict

    sq = sa.select([User])
    has_better = False
    if 'id' in user_dict:
        sq = sq.where(User.c.id == user_dict['id'])
        has_better = True
    if 'dtid' in user_dict:
        sq = sq.where(User.c.dtid == user_dict['dtid'])
        has_better = True
    if not has_better and 'username' in user_dict:
        sq = sq.where(User.c.username == user_dict['username'])

    async with ensure_connection(conn) as conn:
        user = await (await conn.execute(sq)).first()
        return dict(user) if user else user


async def save_user(*, user_dict: dict, conn=None) -> Optional[dict]:
    assert user_dict
    async with ensure_connection(conn) as conn:
        query = psa.insert(User) \
            .values(user_dict) \
            .on_conflict_do_update(
            index_elements=[User.c.dtid],
            set_=user_dict
        )
        user = await (await conn.execute(query)).first()
        return dict(user) if user else user


class Origin(enum.Enum):
    youtube = 1
    soundcloud = 2


Track = sa.Table('track', metadata,
                 sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                 sa.Column('length', sa.Integer, nullable=False),
                 sa.Column('origin', psa.ENUM(Origin), nullable=False),
                 sa.Column('extid', sa.Text, nullable=False),
                 sa.Column('name', sa.Text, nullable=False),
                 sa.UniqueConstraint('origin', 'extid')
                 )


async def get_track(*, track_dict: dict, conn=None) -> Optional[dict]:
    assert track_dict
    sq = sa.select([Track])

    if 'id' in track_dict:
        sq = sq.where(Track.c.id == track_dict['id'])
    if 'extid' in track_dict:
        sq = sq.where(Track.c.extid == track_dict['extid'])
        if 'origin' in track_dict:
            sq = sq.where(Track.c.origin == track_dict['origin'])

    async with ensure_connection(conn) as conn:
        track = await (await conn.execute(sq)).first()
        return dict(track) if track else track


async def save_track(*, track_dict: dict, conn=None) -> Optional[dict]:
    pass


Playback = sa.Table('playback', metadata,
                    sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                    sa.Column('track_id', sa.ForeignKey('track.id'), nullable=False),
                    sa.Column('user_id', sa.ForeignKey('user.id'), nullable=True),
                    sa.Column('start', sa.DateTime, unique=True, nullable=False),
                    )


class Action(enum.Enum):
    skip = 1
    upvote = 2
    downvote = 3


UserAction = sa.Table('user_action', metadata,
                      sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                      sa.Column('ts', sa.DateTime, nullable=False),
                      sa.Column('playback_id', sa.ForeignKey('playback.id'), nullable=False),
                      sa.Column('user_id', sa.ForeignKey('user.id'), nullable=True),
                      sa.Column('action', psa.ENUM(Action), nullable=False),
                      )

BotData = sa.Table('bot_data', metadata,
                   sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                   sa.Column('key', sa.Text, unique=True, nullable=False),
                   sa.Column('value', sa.JSON, nullable=False),
                   )


class BotConfig:
    last_saved_history = 'last_saved_history'

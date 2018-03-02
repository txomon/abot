# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import enum

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


metadata = sa.MetaData()

User = sa.Table('user', metadata,
                sa.Column('id', sa.Integer, primary_key=True, nullable=False),
                sa.Column('dtid', sa.Text, unique=True, nullable=False),
                sa.Column('username', sa.Text, nullable=False),
                sa.Column('country', sa.Text, nullable=True),
                )


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

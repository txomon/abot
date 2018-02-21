# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import enum

import sqlalchemy as sa

ENGINE = None


def sqlite_get_engine():
    global ENGINE
    if ENGINE:
        return ENGINE
    ENGINE = sa.create_engine('sqlite:///songs.sqlite3')
    return ENGINE


def create_sqlite_db():
    engine = sqlite_get_engine()
    metadata.create_all(engine)


sqlite_metadata = sa.MetaData()

SongsHistory = sa.Table('song_history', sqlite_metadata,
                        sa.Column('id', sa.Integer, primary_key=True),
                        sa.Column('played', sa.Integer, unique=True),
                        sa.Column('skipped', sa.Boolean),
                        sa.Column('username', sa.Text),
                        sa.Column('song', sa.Text),
                        )

metadata = sa.MetaData()

User = sa.Table('user', metadata,
                sa.Column('id', sa.Integer, primary_key=True),
                sa.Column('dtid', sa.Text, unique=True),
                sa.Column('name', sa.Text),
                sa.Column('country', sa.Text),
                )

Track = sa.Table('track', metadata,
                 sa.Column('id', sa.Integer, primary_key=True),
                 sa.Column('length', sa.Integer),
                 sa.Column('origin', sa.Text),
                 sa.Column('extid', sa.Text),
                 sa.Column('name', sa.Text),
                 sa.UniqueConstraint('origin', 'extid')
                 )

Playback = sa.Table('playback', metadata,
                    sa.Column('id', sa.Integer, primary_key=True),
                    sa.Column('track_id', sa.ForeignKey('track.id')),
                    sa.Column('user_id', sa.ForeignKey('user.id')),
                    sa.Column('start', sa.Integer),
                    )


class Action(enum.Enum):
    skip = 1
    upvote = 2
    downvote = 3


UserAction = sa.Table('user_action', metadata,
                      sa.Column('id', sa.Integer, primary_key=True),
                      sa.Column('ts', sa.Integer),
                      sa.Column('playback_id', sa.ForeignKey('playback.id')),
                      sa.Column('user_id', sa.ForeignKey('user_id'), nullable=True),
                      sa.Column('action', sa.Enum(Action)),
                      )

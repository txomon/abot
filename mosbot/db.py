# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import sqlalchemy as sa

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


metadata = sa.MetaData()
SongsHistory = sa.Table('song_history', metadata,
                        sa.Column('id', sa.Integer, primary_key=True),
                        sa.Column('played', sa.Integer, unique=True),
                        sa.Column('skipped', sa.Boolean),
                        sa.Column('username', sa.Text),
                        sa.Column('song', sa.Text),
                        )

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
                    sa.Column('skipped', sa.Boolean),
                    sa.Column('upvotes', sa.Integer, nullable=True),
                    sa.Column('downvotes', sa.Integer),
                    )

UserAction = sa.Table('user_action', metadata,
                      sa.Column('id', sa.Integer, primary_key=True),
                      sa.Column('ts', sa.Integer),
                      sa.Column('playback_id', sa.ForeignKey('playback.id')),
                      sa.Column('user_id', sa.ForeignKey('user_id')),
                      sa.Column('action', sa.Text),
                      )

# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import json

import click
import sqlalchemy as sa

import abot.cli as cli
import abot.dubtrack as dt
from abot.bot import Bot
from mosbot import config, db
from mosbot.db import BotConfig
from mosbot.main import playing_handler, setup_logging, skip_handler
from mosbot.query import load_bot_data, save_bot_data
from mosbot.usecase import save_history_songs


class BotConfigValueType(click.ParamType):
    name = 'json'

    def convert(self, value, param, ctx):
        success, converted = self.try_json(value)
        if success:
            return converted
        success, converted = self.try_number(value)
        if success:
            return converted
        return value

    def try_json(self, value):
        try:
            return True, json.loads(value)
        except:
            return False, None

    def try_number(self, value):
        try:
            integer, floating = int(value), float(value)
            if floating == integer:
                return True, integer
            else:
                return True, floating
        except:
            return False, None


@cli.group()
async def botcmd():
    print('BOT')


@botcmd.command()
async def ping():
    print('PONG')


@botcmd.command()
async def test():
    ua1 = db.UserAction.alias('ua1')
    ua2 = db.UserAction.alias('ua2')
    import sqlalchemy.sql.functions as saf
    ts = saf.max(ua2.c.ts).label('ts')
    sub_query = sa.select([
        ua2.c.user_id,
        ts,
        ua2.c.playback_id,
    ]).group_by(
        ua2.c.user_id,
        ua2.c.playback_id,
        sa.case([
            (ua2.c.user_id.is_(None), ua2.c.id),
        ], else_=sa.true)
    )
    query = sa.select([
        sa.distinct(ua1.c.id),
        ua1.c.action,
        ua1.c.playback_id,
        ua1.c.ts,
        ua1.c.user_id,
    ]).select_from(
        ua1.join(
            sub_query,
            sa.and_(
                ts == ua1.c.ts,
                ua1.c.playback_id == ua2.c.playback_id,
                sa.case([
                    (sa.and_(
                        ua1.c.user_id.is_(None),
                        ua2.c.user_id.is_(None)
                    ), sa.true)
                ], else_=ua1.c.user_id == ua2.c.user_id)
            )
        )
    )
    print(query)


@botcmd.command()
@click.option('--value', '-v', type=BotConfigValueType())
@click.argument('key', type=click.Choice(v for v in vars(BotConfig) if not v.startswith('__')))
async def bot_config(key, value):
    if value:
        await save_bot_data(key, value)
        cli.echo(f'Saved key {key}')
    else:
        value = await load_bot_data(key)
        cli.echo(f'Value for key {key} is `{json.dumps(value)}`')


@botcmd.command()
async def history_sync():
    print('AAAAAAAAA')


@click.group()
def botcli():
    print('BOTCLI')


@botcli.command()
def mos_history():
    setup_logging()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(save_history_songs())


@botcli.command()
def run():
    setup_logging()
    # Setup
    bot = Bot()
    dubtrack_backend = dt.DubtrackBotBackend()
    dubtrack_backend.configure(username=config.DUBTRACK_USERNAME, password=config.DUBTRACK_PASSWORD)
    bot.attach_backend(backend=dubtrack_backend)

    bot.add_event_handler(dt.DubtrackSkip, func=skip_handler)
    bot.add_event_handler(dt.DubtrackPlaying, func=playing_handler)

    # Run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.run_forever())

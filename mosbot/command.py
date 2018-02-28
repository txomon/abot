# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import json
import sqlalchemy as sa

import click

import abot.cli as cli
import abot.dubtrack as dt
from abot.bot import Bot
from mosbot import config, db
from mosbot.db import BotConfig, get_engine
from mosbot.main import playing_handler, setup_logging, skip_handler
from mosbot.usecase import load_bot_data, save_bot_data, save_history_songs


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
    engine = await get_engine()
    conn = await engine.acquire()
    query = sa.select([db.User])
    rows = await conn.execute(query)
    res = await rows.first()
    print(dict(res))


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

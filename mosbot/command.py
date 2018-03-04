# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import json
import pprint
import typing

import click

import abot.cli as cli
import abot.dubtrack as dt
from abot.bot import Bot
from mosbot import config as mos_config
from mosbot.db import BotConfig
from mosbot.handler import availability_handler, history_handler
from mosbot.query import load_bot_data, save_bot_data
from mosbot.usecase import save_history_songs
from mosbot.utils import setup_logging


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


@cli.group(invoke_without_command=True)
async def botcmd():
    print('botcmd')


@botcmd.command()
async def atest():
    print('aTest')


@botcmd.command()
@click.option('--debug/--no-debug', '-d/ ', default=False)
async def history_sync(debug):
    setup_logging(debug)
    await save_history_songs()


@botcmd.command()
@click.option('--value', '-v', type=BotConfigValueType())
@click.argument('key', type=click.Choice(v for v in vars(BotConfig) if not v.startswith('__')))
async def config(key, value):
    if value:
        await save_bot_data(key, value)
        cli.echo(f'Saved key {key}')
    else:
        value = await load_bot_data(key)
        cli.echo(f'Value for key {key} is `{json.dumps(value)}`')


@click.group(invoke_without_command=True)
def botcli():
    click.echo('BOTCLI')


@botcli.command()
def test():
    click.echo('TEST')
    pprint.pprint(typing.get_type_hints(history_handler))


@botcli.command()
@click.option('--debug/--no-debug', '-d/ ', default=False)
def run(debug):
    setup_logging(debug)
    # Setup
    bot = Bot()
    dubtrack_backend = dt.DubtrackBotBackend()
    dubtrack_backend.configure(username=mos_config.DUBTRACK_USERNAME, password=mos_config.DUBTRACK_PASSWORD)
    bot.attach_backend(backend=dubtrack_backend)

    bot.add_event_handler(func=history_handler)
    bot.add_event_handler(func=availability_handler)

    # Run
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.run_forever())

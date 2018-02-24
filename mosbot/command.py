# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio

import click

import abot.cli as cli
import abot.dubtrack as dt
from abot.bot import Bot
from mosbot import config
from mosbot.main import playing_handler, setup_logging, skip_handler


@cli.group()
async def bot():
    print('BOT')

@bot.command()
async def ping():
    print('PONG')

@click.group()
def botcli():
    print('BOTCLI')

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


@botcli.command()
async def history_sync():
    print('AAAAAAAAA')


bot = cli.CommandCollection(sources=[botcli, bot])

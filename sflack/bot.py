# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
from asyncio.events import AbstractEventLoop

from sflack.http import SlackAPI


def match(expression: str, message: str):
    pass


class Bot:
    def __init__(self, **slack_api_kwargs):
        self.commands = {}
        self.slack_api = SlackAPI(**slack_api_kwargs)

    def add_bot_command(self, expr, f):
        assert callable(f)
        self.commands[expr] = f

    def _handle_message(self, message):
        pass

    async def run_forever(self):
        async for message in self.slack_api.consume():
            asyncio.sleep(1)
            print('Running')

    def start(self, event_loop: AbstractEventLoop = None):
        return asyncio.ensure_future(self.run_forever(), loop=event_loop)

# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
from asyncio.events import AbstractEventLoop


class Bot:
    def __init__(self):
        self.commands = {}

    def add_command_expr(self, expr, f):
        assert callable(f)
        self.commands[expr] = f

    def _handle_message(self, message):
        pass

    async def run_forever(self):
        while True:
            asyncio.sleep(1)
            print('Running')

    def start(self, event_loop: AbstractEventLoop = None):
        return asyncio.ensure_future(self.run_forever(), loop=event_loop)

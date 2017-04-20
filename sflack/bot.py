# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import logging
import re
from asyncio.events import AbstractEventLoop

from sflack.http import SlackAPI

logger = logging.getLogger(__name__)


def match(expression: str, message: str):
    return re.match(expression, message)


class Event(dict):
    def __init__(self, *args, bot, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    def __getattr__(self, item):
        return self[item]


class Bot:
    def __init__(self, names, **slack_api_kwargs):
        self.commands = {}
        self.slack_api = SlackAPI(**slack_api_kwargs)
        self.names = names

    def add_bot_command(self, expr, f):
        assert callable(f)
        self.commands[expr] = f

    async def _handle_message(self, event):
        message_split = event.text.split(' ', 1)
        if len(message_split) == 1:
            logger.error('No matching')
            return
        name, text = message_split
        if name not in self.names:
            logger.error('No matching')
            return
        for expression, function in self.commands.items():
            if match(expression=expression, message=text):
                asyncio.ensure_future(function(event))
        else:
            logger.error('No matching')

    async def _handle_event(self, event):
        if event.type != 'message':
            return
        await self._handle_message(event)

    async def run_forever(self):
        async for event in self.slack_api.rtm_api_consume():
            ev = Event(event, bot=self)
            await self._handle_event(event=ev)

    def start(self, event_loop: AbstractEventLoop = None):
        return asyncio.ensure_future(self.run_forever(), loop=event_loop)

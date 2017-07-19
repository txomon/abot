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
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    def __getattr__(self, item):
        try:
            return self[item]
        except:
            raise AttributeError()

    @classmethod
    def from_dict(cls, event_dict, bot):
        event = cls(bot=bot)
        event.update(event_dict)
        return event

    @classmethod
    def from_event(cls, event):
        new_event = cls(bot=event.bot)
        new_event.update(event)
        return new_event


class MessageEvent(Event):
    async def say(self, text: str, to: str = None):
        # Say something in the same channel as the message
        if to is None:
            to = self.channel
        await self.bot.slack_api.write_to(to, text)

    async def tell(self, text: str, to: str = None):
        if to is None:
            to = self.user
        # Say something to the sender
        await self.bot.slack_api.write_to(to, text)

    @property
    def sender(self):
        return self.bot.slack_api.get_user_by_id(self.user)


class Bot:
    def __init__(self, bot_name, spaced_names=True, **slack_api_kwargs):
        if isinstance(bot_name, str):
            bot_name = [bot_name]
        self.commands = {}
        self.slack_api = SlackAPI(**slack_api_kwargs)
        self.bot_names = bot_name
        self.spaced_names = spaced_names
        self.expression_values = {'bot_name': fr'(?P<bot_name>{"|".join(bot_name)})'}

    def add_name_lead_command(self, expr, f):
        assert callable(f)
        if self.spaced_names:
            expression = '^{bot_name} ' + expr + '$'
        else:
            expression = '^{bot_name}' + expr + '$'
        self.add_message_handler(expression, f)

    def add_message_handler(self, rexpression, func):
        self.commands[rexpression] = func

    async def _handle_message(self, event: MessageEvent):
        already_matched = False
        for expression, function in self.commands.items():
            expression = expression.format(**self.expression_values)
            if not match(expression=expression, message=event.text):
                logger.debug(f'Text `{event.text}` didn\'t match `{expression}`')
                continue
            if already_matched:
                logger.warning(f'Skipping already executed {event} (Would have been {function})')
                continue
            already_matched = True
            logger.debug(f'Executing {event} in {function}')
            asyncio.ensure_future(
                self.run_event(function=function, event=event)
            )
        else:
            logger.debug(f'No matching {event}')

    async def _handle_event(self, event):
        if event.type != 'message':
            return
        if getattr(event, 'subtype', None):
            return
        await self._handle_message(MessageEvent.from_event(event=event))

    async def run_forever(self):
        continue_running = True
        while continue_running:
            try:
                async for event in self.slack_api.rtm_api_consume():
                    ev = Event.from_dict(event, bot=self)
                    await self._handle_event(event=ev)
            except Exception as e:
                continue_running = await self.internal_exception_handler(e)

    async def internal_exception_handler(self, exception):
        logger.error('Internal exception handled', exc_info=exception)
        return True

    async def run_event(self, function, event):
        try:
            await function(event)
        except Exception as exception:
            await self.handle_bot_exception(function, event, exception)

    async def handle_bot_exception(self, function, event, exception):
        logger.exception(f'Failed running {event} in {function}')
        await event.say(f':boom:... Houston we found a problem: `{exception}`')

    def start(self, event_loop: AbstractEventLoop = None):
        return asyncio.ensure_future(self.run_forever(), loop=event_loop)

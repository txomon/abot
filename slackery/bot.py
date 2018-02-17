# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import logging
import re
import shlex
from asyncio.events import AbstractEventLoop
from inspect import iscoroutinefunction

from slackery.http import SlackAPI

logger = logging.getLogger(__name__)


class Entity:
    async def tell(self, text: str, to: str = None):
        # Say something to the sender
        raise NotImplementedError()


class Event:
    @property
    def sender(self) -> Entity:
        # Return the entity that sent this
        raise NotImplementedError()

    async def say(self, text: str, to: str = None):
        # Say something in the same channel as the message
        raise NotImplementedError()

    async def reply(self, text: str, to: str = None)
        # Reply to the message mentioning if possible
        raise NotImplementedError()

    async def tell(self, text: str, to: str = None):
        # Say something to the sender directly if possible
        raise NotImplementedError()


class MessageEvent(Event):
    @property
    def text(self):
        # Return the content of the message in plaintext
        raise NotImplementedError()


class Bot:
    def __init__(self):
        self.commands = {}

    def add_addressed_command(self, expr, *, func=None):
        def wrapper(f):
            assert callable(f)
            if self.spaced_names:
                expression = '{bot_name} ' + expr  # To be formatted later
            else:
                expression = '{bot_name}' + expr  # To be formatted later
            self.add_message_handler(expression, func=f)
            return f

        if func is None:
            return wrapper
        else:
            wrapper(func)

    def add_message_handler(self, rexpression, *, func=None):
        assert iscoroutinefunction(
            func), f'Handler for {rexpression} needs to be coroutine ({func.__name__})'
        self.commands[rexpression] = func

    async def _handle_message(self, event: MessageEvent):
        already_matched = False
        try:
            tokens = tokenize_event(event=event)
        except ValueError as e:
            error_string = e.args[0]
            await event.say(error_string)
            return

        for command, operator in get_commands_from_tokens(tokens=tokens):
            for expression, func in self.commands.items():
                expression = expression.format(**self.expression_values)
                message = ' '.join(command)
                message_match = match(expression=expression, message=message)
                if not message_match:
                    logger.debug(
                        f'Text `{message}` didn\'t match `{expression}`')
                    continue
                if already_matched:
                    logger.warning(
                        f'Skipping already executed {message} (Would have been {func})')
                    continue
                already_matched = True
                event.matches = message_match.groupdict()
                logger.debug(f'Executing {event} in {func}')
                self.run_event(func=func, event=event)
            else:
                logger.debug(f'No matching {event}')

    async def _handle_event(self, event: Event):
        if not isinstance(event, MessageEvent):
            return
        if 'subtype' in event.content:
            return
        asyncio.ensure_future(
            self._handle_message(event=event)
        )

    async def run_forever(self):
        continue_running = True
        while continue_running:
            try:
                async for event in self.slack_api.rtm_api_consume():
                    ev = Event.from_obj(content=event, bot=self)
                    await self._handle_event(event=ev)
            except Exception as e:
                continue_running = await self.internal_exception_handler(e)

    async def internal_exception_handler(self, exception):
        logger.error('Internal exception handled', exc_info=exception)
        return True

    async def run_event(self, func, event):
        try:
            await func(event)
        except Exception as exception:
            await self.handle_bot_exception(func, event, exception)

    async def handle_bot_exception(self, func, event, exception):
        logger.exception(f'Failed running {event} in {func}')
        await event.say(f':boom:... Houston we found a problem: ```{exception}```')

    def start(self, event_loop: AbstractEventLoop = None):
        return asyncio.ensure_future(self.run_forever(), loop=event_loop)

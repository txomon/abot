# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import inspect
import logging
import pprint
import typing
from asyncio.events import AbstractEventLoop
from collections import Iterable, defaultdict
from typing import List, Optional

from abot.cli import CommandCollection, Group
from abot.util import iterator_merge

logger = logging.getLogger(__name__)


class Backend:
    def configure(self, **config):
        raise NotImplementedError

    async def initialize(self):
        raise NotImplementedError()

    async def consume(self):
        raise NotImplementedError()

    def whoami(self) -> Optional['Entity']:
        raise NotImplementedError()

    def is_mentioned(self, message_event: 'MessageEvent') -> Optional[str]:
        username = self.whoami().username
        text = message_event.text
        if not username or text:
            return None
        if len(text) < 2:
            return None
        if text.startswith(username) or text[1:].startswith(username):
            return username
        return None


class BotObject:
    @property
    def bot(self) -> 'Bot':
        if hasattr(self, '_bot'):
            return self._bot
        raise ValueError('Bot is not set in BotObject')

    @bot.setter
    def bot(self, bot: 'Bot'):
        if hasattr(self, '_bot'):
            raise ValueError(f'Bot {self._bot} is in place, cannot replace with {bot}')
        self._bot = bot

    @property
    def backend(self) -> Backend:
        raise NotImplementedError()


class Channel(BotObject):
    @property
    async def entities(self) -> List['Entity']:
        raise NotImplementedError()

    async def say(self, text: str):
        # Say something in the same channel as the message
        raise NotImplementedError()


class Entity(BotObject):
    async def tell(self, text: str):
        # Say something to the sender
        raise NotImplementedError()

    @property
    def id(self) -> str:
        raise NotImplementedError()

    @property
    def username(self) -> str:
        raise NotImplementedError()


class Event(BotObject):
    @property
    def sender(self) -> Entity:
        # Return the entity that sent this
        raise NotImplementedError()

    @property
    def channel(self) -> Channel:
        # Return the channel used to send the Event
        raise NotImplementedError()

    async def reply(self, text: str):
        # Reply to the message mentioning if possible
        raise NotImplementedError()


class MessageEvent(Event):
    @property
    def text(self) -> str:
        # Return the content of the message in plaintext
        raise NotImplementedError()


class Bot:
    def __init__(self):
        self.backends = {}
        self.event_handlers = defaultdict(set)
        self.message_handlers = set()

    def attach_backend(self, backend: Backend):
        if backend in self.backends:
            raise ValueError(f'Backend {backend} is already attached to bot')
        iterator = self.backend_consume(backend)
        self.backends[backend] = iterator

    async def backend_consume(self, backend):
        while True:
            try:
                async for event in backend.consume():
                    yield event
            except BaseException:
                logger.exception(f'Exception in {backend} handled. Trying to recover.')

    def attach_command_group(self, group: Group):
        self.message_handlers.add(group)

    async def _handle_message(self, message):
        name = message.backend.is_mentioned(message)
        if not name:
            return
        cmd = CommandCollection(self.message_handlers)
        asyncio.ensure_future(await cmd.async_message(message))

    def add_event_handler(self, event_class=None, *, func=None):
        if event_class and not isinstance(event_class, Iterable):
            event_class = (event_class,)

        def wrapper(f):
            nonlocal event_class
            assert asyncio.iscoroutinefunction(func), \
                f'Handler for {event_class} needs to be coroutine ({func})'
            if event_class is None:
                event_class = extract_possible_argument_types(func)

            for ec in event_class:
                self.event_handlers[f].add(ec)
            return f

        if func is None:
            return wrapper
        else:
            wrapper(func)

    async def _handle_event(self, event: Event):
        # Same event can be handled multiple times, Messages only once
        if isinstance(event, MessageEvent):
            logger.debug(f'Handling message {event.text}')
            await self._handle_message(event)
        runs = 0
        for cls in inspect.getmro(event.__class__):
            for handler, handled_classes in self.event_handlers.items():
                if cls not in handled_classes:
                    continue
                asyncio.ensure_future(self.run_event(handler, event))
                runs += 1
        if not runs:
            logger.debug(f'No message handler for {event}')

    async def run_forever(self):
        continue_running = True

        for backend in self.backends:
            await backend.initialize()

        while continue_running:
            try:
                async for event in iterator_merge(*self.backends.values()):
                    await self._handle_event(event=event)
            except Exception as e:
                continue_running = await self.internal_exception_handler(e)

    async def internal_exception_handler(self, exception):
        logger.error('Internal exception handled', exc_info=exception)

        tb = exception.__traceback__
        while tb.tb_next:
            tb = tb.tb_next

        logger.error(f'Locals: {pprint.pformat(tb.tb_frame.f_locals)}')
        return True

    async def run_event(self, func, event):
        logger.debug(f'Starting handling {event} with <{func.__name__}>')
        try:
            await func(event)
        except Exception as exception:
            await self.handle_bot_exception(func, event, exception)
        else:
            logger.debug(f'Finished handling {event} with <{func.__name__}>')

    async def handle_bot_exception(self, func, event, exception):
        logger.exception(f'Failed running {event} in {func}')
        # await event.say(f':boom:... Houston we found a problem: ```{exception}```')

    def start(self, event_loop: AbstractEventLoop = None):
        return asyncio.ensure_future(self.run_forever(), loop=event_loop)


def extract_possible_argument_types(func) -> Iterable:
    args = typing.get_type_hints(func)
    if len(args) != 1:
        raise AttributeError(f'Function {func} can only have one argument if using type hinting')
    type_hint = next(iter(args.values()))
    if type_hint.__class__.__name__ == '_Union':
        return type_hint.__args__
    return type_hint,

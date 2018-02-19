# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import inspect
import logging
from asyncio.events import AbstractEventLoop

import aiostream

from abot.util import iterator_merge

logger = logging.getLogger(__name__)


class Backend:
    def configure(self, **config):
        raise NotImplementedError

    async def initialize(self):
        raise NotImplementedError()

    async def consume(self):
        raise NotImplementedError()


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
    async def say(self, text: str):
        # Say something in the same channel as the message
        raise NotImplementedError()


class Entity(BotObject):
    async def tell(self, text: str):
        # Say something to the sender
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
        self.event_handlers = {}

    def attach_backend(self, backend: Backend):
        if backend in self.backends:
            raise ValueError(f'Backend {backend} is already attached to bot')
        iterator = backend.consume()
        self.backends[backend] = iterator

    def _handle_message(self, message):
        raise NotImplementedError()

    def add_event_handler(self, event_class, *, func=None):
        def wrapper(f):
            assert asyncio.iscoroutinefunction(
                func), f'Handler for {event_class} needs to be coroutine ({func})'
            if event_class in self.event_handlers:
                raise ValueError(
                    f'Event handler for {event_class} is already registered on {self.event_handlers[event_class]}')
            self.event_handlers[event_class] = f
            return f

        if func is None:
            return wrapper
        else:
            wrapper(func)

    async def _handle_event(self, event: Event):
        # TODO: Generate _handle_message
        # if isinstance(event, MessageEvent):
        #     logger.debug(f'Message event {event} handling as message')
        #     self._handle_message(event)
        #     return
        for cls in inspect.getmro(event.__class__):
            handler = self.event_handlers.get(cls)
            if handler:
                break
        else:
            logger.warning(f'No message handler for {event}')
            return
        logger.debug(f'Handling {event} with <{handler.__name__}>')
        await handler(event)

    async def run_forever(self):
        continue_running = True

        for backend in self.backends:
            await backend.initialize()

        while continue_running:
            try:
                async for event in iterator_merge(*self.backends.values()):
                    asyncio.ensure_future(self._handle_event(event=event))
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

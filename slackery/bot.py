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


def match(expression: str, message: str):
    return re.fullmatch(expression, message)


class Event:
    affinity = None

    def __init__(self, content, bot):
        self.content = content
        self.bot = bot

    @classmethod
    def from_obj(cls, content, bot):
        for cl in cls.__subclasses__():
            if cl.affinity == content['type']:
                return cl(content, bot)
        else:
            return cls(content, bot)


class MessageEvent(Event):
    affinity = 'message'

    async def say(self, text: str, to: str = None):
        # Say something in the same channel as the message
        if to is None:
            to = self.content['channel']
        await self.bot.slack_api.write_to(to, text)

    async def tell(self, text: str, to: str = None):
        if to is None:
            to = self.content['user']
        # Say something to the sender
        await self.bot.slack_api.write_to(to, text)

    @property
    def sender(self):
        return self.bot.slack_api.get_user_by_id(self.content['user'])

    @property
    def text(self):
        return self.content['text']

    @property
    def matches(self):
        if not hasattr(self, '_matches'):
            self._matches = {}
        return self._matches

    @matches.setter
    def matches(self, matches):
        if hasattr(self, '_matches'):
            raise ValueError('Matches can only be set once')
        self._matches = matches


def create_shlex_error(parser: shlex.shlex, exception: ValueError) -> str:
    current_read = parser.instream.tell() - 1
    token_length = len(parser.token)
    full_string = parser.instream.getvalue()

    guilty_string = full_string[current_read - token_length:]

    try:
        exception_value = exception.args[0].lower()
    except:
        exception_value = 'unknown exception'
    error_string = f'Bad command, {exception_value}: {guilty_string}'
    return error_string


def tokenize_event(event: MessageEvent):
    parser = shlex.shlex(event.content, posix=True, punctuation_chars=True)
    parser.whitespace = ' \t'
    tokens = []
    try:
        while True:
            token = parser.get_token()
            if token is None:
                break
            tokens.append(token)
    except ValueError as e:
        string = create_shlex_error(parser=parser, exception=e)
        raise ValueError(string) from None
    return tokens


def get_commands_from_tokens(tokens):
    command = []
    for token in tokens:
        if token in ['&&', '\r', ';', '\n', '||', '&']:
            if command:
                yield command, token
                command = []
        else:
            command.append(token)


class Bot:
    def __init__(self, bot_name, spaced_names=True, **slack_api_kwargs):
        if isinstance(bot_name, str):
            bot_name = [bot_name]
        self.commands = {}
        self.slack_api = SlackAPI(**slack_api_kwargs)
        self.bot_names = bot_name
        self.spaced_names = spaced_names
        self.expression_values = {'bot_name': fr'(?P<bot_name>{"|".join(bot_name)})'}

    def add_name_lead_command(self, expr, *, func=None):
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
        assert iscoroutinefunction(func), f'Handler for {rexpression} needs to be coroutine ({func.__name__})'
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
                    logger.debug(f'Text `{message}` didn\'t match `{expression}`')
                    continue
                if already_matched:
                    logger.warning(f'Skipping already executed {message} (Would have been {func})')
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

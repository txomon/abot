# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import asynctest as am
import logging
import pytest
from typing import Union
from unittest import mock

from abot import cli
from abot.bot import Abort, Backend, Bot, BotObject, Channel, Entity, Event, MessageEvent, \
    extract_possible_argument_types
from tests.dummy_backend import DummyBackend, DummyEvent, DummyMessageEvent


# Helper functions

def func_union_dict_list(b: Union[dict, list]): pass


def func_dict(b: dict): pass


def func_invalid(b: dict, c: list): pass


async def async_handler_func(event): pass


# Fixtures
@pytest.fixture()
def bot():
    return Bot()


@pytest.fixture()
def dummy_backend():
    return DummyBackend()


@pytest.fixture()
def dummy_bot(bot, dummy_backend):
    bot.attach_backend(dummy_backend)
    return bot


@pytest.fixture
def asyncio_mock(mocker):
    return mocker.patch('abot.bot.asyncio')


@pytest.fixture
def command_collection_mock(mocker):
    return mocker.patch('abot.bot.CommandCollection')


# Tests start

@pytest.mark.parametrize('func,outcome', [
    (func_union_dict_list, (dict, list)),
    (func_dict, (dict,)),
    (func_invalid, AttributeError)
])
def test_extract_possible_argument_types(func, outcome):
    if outcome == AttributeError:
        with pytest.raises(outcome):
            assert outcome == extract_possible_argument_types(func)
    else:
        assert outcome == extract_possible_argument_types(func)


@pytest.mark.asyncio
async def test_backend_requirements():
    class TestBackend(Backend):
        pass

    backend = TestBackend()
    with pytest.raises(NotImplementedError):
        backend.configure()
    with pytest.raises(NotImplementedError):
        await backend.initialize()
    with pytest.raises(NotImplementedError):
        await backend.consume()
    with pytest.raises(NotImplementedError):
        backend.whoami()


@pytest.mark.parametrize('text,succeeds', [
    ('t', False), ('', False),
    ('txomon', True), ('@txomon', True), ('!txomon', True),
    ('txomon,', True), ('@txomon,', True), ('!txomon,', True),
    ('txomon:', True), ('@txomon:', True), ('!txomon:', True),
    ('txomon, you do', True), ('@txomon, you do', True), ('!txomon, you do', True),
    ('txomon,you do', True), ('@txomon,you do', True), ('!txomon,you do', True),
    ('txomon: you do', True), ('@txomon: you do', True), ('!txomon: you do', True),
    ('txomon:you do', True), ('@txomon:you do', True), ('!txomon:you do', True),
    ('txomon you do', True), ('@txomon you do', True), ('!txomon you do', True),
    ('txomonyou do', False), ('@txomonyou do', False), ('!txomonyou do', False),
    ('#txomonyou do', False), ('#txomonyou do', False), ('#txomonyou do', False),
    ('#txomon you do', False), ('#txomon you do', False), ('#txomon you do', False),
])
def test_backend_is_mentioned(text: str, succeeds: bool, dummy_backend: DummyBackend):
    dummy_backend.me.username = 'txomon'
    event_mock = mock.MagicMock(spec=MessageEvent)
    event_mock.text = text
    assert bool(dummy_backend.is_mentioned(event_mock)) == succeeds


def test_bot_object():
    obj = BotObject()

    # First make sure that getter/setter routine is correct
    with pytest.raises(ValueError):
        obj.bot

    mm = obj.bot = mock.MagicMock()
    assert mm == obj.bot

    with pytest.raises(ValueError):
        obj.bot = mm

    # Now errors
    with pytest.raises(NotImplementedError):
        assert obj.backend


@pytest.mark.asyncio
async def test_channel():
    channel = Channel()
    with pytest.raises(NotImplementedError):
        assert await channel.entities

    with pytest.raises(NotImplementedError):
        assert await channel.say('AAAA')


@pytest.mark.asyncio
async def test_entity():
    entity = Entity()

    with pytest.raises(NotImplementedError):
        assert await entity.tell('AAAA')

    with pytest.raises(NotImplementedError):
        assert entity.id

    with pytest.raises(NotImplementedError):
        assert entity.username


@pytest.mark.asyncio
async def test_event():
    event = Event()

    with pytest.raises(NotImplementedError):
        assert await event.reply('AAAA')

    with pytest.raises(NotImplementedError):
        assert event.channel

    with pytest.raises(NotImplementedError):
        assert event.sender


def test_message_event():
    event = MessageEvent()

    with pytest.raises(NotImplementedError):
        assert event.text


def test_bot_creation():
    bot = Bot()
    assert bot.backends == {}
    assert bot.event_handlers == {}
    assert bot.message_handlers == set()


def test_bot_attach_backend(bot: Bot, dummy_backend: DummyBackend):
    bot.attach_backend(dummy_backend)
    with pytest.raises(ValueError):
        bot.attach_backend(dummy_backend)


@pytest.mark.asyncio
async def test_bot_backend_consume(dummy_bot: Bot, dummy_backend: DummyBackend):
    dummy_backend.events = ['a', 'b', 'c']

    events = []
    with pytest.raises(Abort):
        async for event in dummy_bot.backend_consume(dummy_backend):
            events.append(event)
            if len(events) == 4:
                dummy_backend.events.append(Exception())
            if len(events) == 8:
                dummy_backend.events[3] = Abort()
    assert events == ['a', 'b', 'c'] * 3


def test_bot_attach_command_group(dummy_bot: Bot):
    @cli.group()
    async def main_group():
        pass

    dummy_bot.attach_command_group(main_group)
    assert main_group in dummy_bot.message_handlers

    dummy_bot.attach_command_group(main_group)
    assert main_group in dummy_bot.message_handlers


@pytest.mark.parametrize('is_mentioned', [True, False])
@pytest.mark.asyncio
async def test_bot_handle_message(
        dummy_bot: Bot,
        asyncio_mock: mock.MagicMock,
        is_mentioned: bool,
        command_collection_mock: mock.MagicMock):
    m = mock.MagicMock(spec=MessageEvent)
    m.backend.is_mentioned.return_value = is_mentioned
    await dummy_bot._handle_message(m)
    m.backend.is_mentioned.assert_called_once_with(m)
    if not is_mentioned:
        assert len(asyncio_mock.mock_calls) == 0
    else:
        command_collection_mock.assert_called_once_with(dummy_bot.message_handlers)
        cmd = command_collection_mock.return_value
        cmd.async_message.assert_called_once_with(m)
        assert len(asyncio_mock.ensure_future.mock_calls) == 1


def test_bot_add_event_handler(dummy_bot):
    async def auto_reg_event_handler(event: Event):
        pass

    dummy_bot.add_event_handler(func=auto_reg_event_handler)
    assert len(dummy_bot.event_handlers) == 1

    @dummy_bot.add_event_handler(Event)
    async def event_handler(event):
        pass

    assert len(dummy_bot.event_handlers) == 2

    @dummy_bot.add_event_handler()
    async def decorated_run_event_handler(event: Event):
        pass

    assert len(dummy_bot.event_handlers) == 3

    @dummy_bot.add_event_handler
    async def decorated_event_handler(event: Event):
        pass

    assert len(dummy_bot.event_handlers) == 4


@pytest.mark.parametrize('event_class, listener_class', [
    (DummyEvent, DummyEvent),
    (DummyEvent, DummyMessageEvent),
    (DummyMessageEvent, DummyEvent),
    (DummyMessageEvent, DummyMessageEvent),
])
@pytest.mark.asyncio
async def test_bot_handle_event(dummy_bot: Bot, event_class, listener_class, asyncio_mock):
    dummy_bot._handle_message = am.CoroutineMock()
    dummy_bot.run_event = am.CoroutineMock()

    dummy_bot.add_event_handler(event_class_or_func=listener_class, func=async_handler_func)

    event: Event = event_class()

    await dummy_bot._handle_event(event)

    if issubclass(event_class, MessageEvent):
        dummy_bot._handle_message.assert_awaited_once_with(event)
    if issubclass(listener_class, MessageEvent) and not issubclass(event_class, MessageEvent):
        dummy_bot.run_event.assert_not_called()
        dummy_bot.run_event.assert_not_awaited()
    else:  # listener_class is Event
        dummy_bot.run_event.assert_called_once_with(async_handler_func, event)
        asyncio_mock.ensure_future.assert_called_once()


@pytest.mark.asyncio
async def test_bot__run_forever(dummy_bot: Bot, dummy_backend: DummyBackend):
    dummy_backend.initialize = am.CoroutineMock()
    dummy_backend.events = [Event(), Event(), Abort()]
    dummy_bot.internal_exception_handler = am.CoroutineMock(return_value=False)
    e = Exception()
    dummy_bot._handle_event = am.CoroutineMock(side_effect=[True, e])

    await dummy_bot._run_forever()

    dummy_backend.initialize.assert_called_once_with()
    assert dummy_bot._handle_event.mock_calls == [mock.call(event=dummy_backend.events[0]),
                                                  mock.call(event=dummy_backend.events[1])]
    dummy_bot.internal_exception_handler.assert_awaited_once_with(e)


@pytest.mark.asyncio
async def test_bot_run_forever(dummy_bot: Bot):
    rf = dummy_bot._run_forever = am.CoroutineMock()

    await dummy_bot.run_forever()

    rf.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_internal_exception_handler(dummy_bot: Bot):
    def a():
        raise Exception()

    try:
        a()
    except Exception as e:
        res = await dummy_bot.internal_exception_handler(e)
    assert res is True


@pytest.mark.parametrize('returns', [
    Abort(),
    Exception(),
    None,
])
@pytest.mark.asyncio
async def test_bot_run_event(dummy_bot, returns):
    func = am.CoroutineMock()
    func.side_effect = returns
    func.__name__ = 'func'
    event = Event()
    dummy_bot.forever_loop = am.MagicMock()
    dummy_bot.handle_bot_exception = am.CoroutineMock()

    await dummy_bot.run_event(func, event)

    if isinstance(returns, Abort):
        dummy_bot.forever_loop.set_exception.assert_called_once_with(returns)
    elif isinstance(returns, Exception):
        dummy_bot.handle_bot_exception.assert_awaited_once_with(func, event, returns)


@pytest.mark.asyncio
async def test_bot_handle_bot_exception(dummy_bot):
    func = am.CoroutineMock()
    event = Event()
    try:
        raise Exception()
    except Exception as e:
        await dummy_bot.handle_bot_exception(func, event, e)


def test_bot_start(dummy_bot: Bot, asyncio_mock):
    m = mock.MagicMock()
    dummy_bot.run_forever = am.CoroutineMock()
    dummy_bot.start(m)

    asyncio_mock.ensure_future.assert_called_once()
    dummy_bot.run_forever.assert_called_once_with()


# Integration tests

@pytest.mark.integration
@pytest.mark.asyncio
async def test_bot_events(dummy_bot: Bot, dummy_backend: DummyBackend, caplog):
    handler_calls = mock.MagicMock()
    dummy_event = mock.MagicMock(spec=Event)

    async def auto_reg_event_handler(event: Event):
        handler_calls.auto_reg_event_handler(event)

    dummy_bot.add_event_handler(func=auto_reg_event_handler)
    assert len(dummy_bot.event_handlers) == 1

    @dummy_bot.add_event_handler(Event)
    async def event_handler(event):
        handler_calls.event_handler(event)

    assert len(dummy_bot.event_handlers) == 2

    @dummy_bot.add_event_handler()
    async def decorated_run_event_handler(event: Event):
        handler_calls.decorated_event_handler(event)

    assert len(dummy_bot.event_handlers) == 3

    @dummy_bot.add_event_handler
    async def decorated_event_handler(event: Event):
        handler_calls.decorated_event_handler(event)

    assert len(dummy_bot.event_handlers) == 4

    dummy_backend.events = [dummy_event, Abort()]

    caplog.set_level(logging.DEBUG, logger='asyncio')
    asyncio.get_event_loop().set_debug(True)

    with pytest.raises(Abort):
        await dummy_bot._run_forever()

    assert len(handler_calls.mock_calls) == 4, handler_calls.mock_calls

# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import logging
from typing import Union
from unittest import mock

import pytest

from abot import cli
from abot.bot import Abort, Backend, Bot, BotObject, Channel, Entity, Event, MessageEvent, \
    extract_possible_argument_types
from tests.dummy_backend import DummyBackend


# Helper functions

def func_union_dict_list(b: Union[dict, list]): pass


def func_dict(b: dict): pass


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


# Tests start

@pytest.mark.parametrize('func,outcome', [
    (func_union_dict_list, (dict, list)),
    (func_dict, (dict,)),
])
def test_extract_possible_argument_types(func, outcome):
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
    dummy_backend.events = ['a', 'b', 'c', Exception()]

    events = []
    with pytest.raises(Abort):
        async for event in dummy_bot.backend_consume(dummy_backend):
            events.append(event)
            if len(events) == 4:
                dummy_backend.events[3] = Abort()
    assert events == ['a', 'b', 'c', 'a', 'b', 'c']


def test_bot_attach_command_group(dummy_bot: Bot):
    @cli.group()
    async def main_group():
        pass

    dummy_bot.attach_command_group(main_group)
    assert main_group in dummy_bot.message_handlers

    dummy_bot.attach_command_group(main_group)
    assert main_group in dummy_bot.message_handlers

def test_


# Integration tests

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

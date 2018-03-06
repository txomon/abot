# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from typing import Union
from unittest import mock

import pytest

from abot.bot import Backend, Bot, BotObject, Channel, Entity, Event, MessageEvent, extract_possible_argument_types
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


def test_backend_attach(bot: Bot, dummy_backend: DummyBackend):
    bot.attach_backend(dummy_backend)
    with pytest.raises(ValueError):
        bot.attach_backend(dummy_backend)


@pytest.mark.asyncio
async def test_backend_consume(dummy_bot: Bot, dummy_backend: DummyBackend):
    pass

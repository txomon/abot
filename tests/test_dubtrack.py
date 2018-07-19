# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asynctest as am
import pytest
import unittest.mock as mock

from abot import dubtrack


@pytest.fixture
def datetime_mock(mocker):
    return mocker.patch('abot.dubtrack.datetime')


def test_dubtrack_object():
    data, backend = object(), object()
    dub_obj = dubtrack.DubtrackObject(data, backend)

    assert dub_obj._dubtrack_backend == backend
    assert dub_obj._data == data
    assert dub_obj.backend == backend


@pytest.mark.asyncio
async def test_dubtrack_channel():
    data, backend = mock.MagicMock(), mock.MagicMock()

    channel = dubtrack.DubtrackChannel(data, backend)
    backend._register_user.assert_called_once_with(data)

    backend.dubtrackws.say_in_room = am.CoroutineMock()
    await channel.say('hello')
    backend.dubtrackws.say_in_room.assert_called_once_with('hello')

    backend.dubtrack_id = None
    with pytest.raises(ValueError):
        await channel.say('alo')

    backend.reset_mock()

    user = mock.MagicMock()
    backend.dubtrack_users = [user]

    assert channel.entities == [backend._get_entity.return_value], backend.mock_calls

    backend._get_entity.assert_called_once_with(user)

    assert repr(channel)


@pytest.mark.parametrize('property_name', (
        'username',
        'id',
        'dubs',
        'played_count',
        'skips',
        'songs_in_queue',
))
@pytest.mark.asyncio
async def test_dubtrack_entity(property_name):
    data, backend = mock.MagicMock(), mock.MagicMock()

    entity = dubtrack.DubtrackEntity(data, backend)

    value = getattr(entity, property_name)
    assert value == data.get.return_value
    data.get.assert_called_once_with(property_name)

    assert repr(entity)

    assert entity == entity

    await entity.tell('something')

    assert entity != object()
    assert entity != dubtrack.DubtrackEntity(mock.MagicMock(), backend)


@pytest.mark.parametrize('data,return_type', (
        ({'type': 'chat-message'}, dubtrack.DubtrackMessage),
        ({'type': 'bu'}, dubtrack.DubtrackEvent)
))
def test_dubtrack_event_from_data(data, return_type):
    backend = mock.MagicMock()

    result = dubtrack.DubtrackEvent.from_data(data=data, dubtrack_backend=backend)

    assert isinstance(result, return_type)
    assert result.backend == backend
    assert result._data == data


@pytest.mark.asyncio
async def test_dubtrack_event():
    data, backend = mock.MagicMock(), mock.MagicMock()
    event = dubtrack.DubtrackEvent(data=data, dubtrack_backend=backend)

    # Test sender is pass implementation
    assert event.sender is None

    # Test unset channel raises ValueError
    with pytest.raises(ValueError):
        assert event.channel

    # Test channel can be set
    channel = event.channel = mock.MagicMock()

    # Test channel has been set
    assert event.channel == channel

    # Test channel cannot be set again
    with pytest.raises(ValueError):
        event.channel = channel

    # Assert reply can be called
    assert None is await event.reply('something', 'someone')

    # Working __repr__
    assert repr(event)


@pytest.mark.asyncio
async def test_dubtrack_message():
    data, backend = mock.MagicMock(), mock.MagicMock()
    event = dubtrack.DubtrackMessage(data=data, dubtrack_backend=backend)

    # Check contructor
    backend._register_user.assert_called_once_with(data.get.return_value)
    data.get.assert_called_once_with('user')

    # Check .sender attribute
    data.reset_mock()
    assert event.sender == backend._get_entity.return_value
    backend._get_entity.assert_called_once_with(
        data.get.return_value.get.return_value
    )
    data.get.assert_called_once_with('user', {})
    data.get.return_value.get.assert_called_once_with('username')

    # Check .text attribute
    data.reset_mock()
    assert event.text == data.get.return_value
    data.get.assert_called_once_with('message')

    # Check .message_id attribute
    data.reset_mock()
    assert event.message_id == data.get.return_value
    data.get.assert_called_once_with('chatid')

    # Check __repr__
    assert repr(event)


@pytest.mark.asyncio
async def test_dubtrack_skip():
    data, backend = mock.MagicMock(), mock.MagicMock()
    event = dubtrack.DubtrackSkip(data=data, dubtrack_backend=backend)

    # Check .sender attribute
    assert event.sender == backend._get_entity.return_value
    backend._get_entity.assert_called_once_with(data.get.return_value)
    data.get.assert_called_once_with('username')

    # Check __repr__ works
    assert repr(event)


@pytest.mark.asyncio
async def test_dubtrack_delete():
    data, backend = mock.MagicMock(), mock.MagicMock()
    event = dubtrack.DubtrackDelete(data=data, dubtrack_backend=backend)

    # Check .sender attribute
    assert event.sender == backend._get_entity.return_value
    backend._get_entity.assert_called_once_with(
        data.get.return_value.get.return_value
    )
    data.get.assert_called_once_with('user', {})
    data.get.return_value.get.assert_called_once_with('username')

    # Check .message_id attribute
    data.reset_mock()
    assert event.message_id == data.get.return_value
    data.get.assert_called_once_with('chatid')

    # Check __repr__ works
    assert repr(event)


@pytest.mark.asyncio
async def test_dubtrack_dub(datetime_mock):
    data, backend = mock.MagicMock(), mock.MagicMock()
    event = dubtrack.DubtrackDub(data=data, dubtrack_backend=backend)

    # Check __ini__
    backend._register_user.assert_called_once_with(data.__getitem__.return_value)
    data.__getitem__.assert_called_once_with('user')

    # Check .sender
    data.reset_mock()
    assert event.sender == backend._get_entity.return_value
    backend._get_entity.assert_called_once_with(
        data.get.return_value.get.return_value
    )
    data.get.assert_called_once_with('user', {})
    data.get.return_value.get.assert_called_once_with('username')

    # Check .dubtype
    data.reset_mock()
    assert event.dubtype == data.get.return_value
    data.get.assert_called_once_with('dubtype')

    # Check .total_updubs
    data.reset_mock()
    assert event.total_updubs == data.get.return_value.get.return_value
    data.get.assert_called_once_with('playlist', {})
    data.get.return_value.get.assert_called_once_with('updubs')

    # Check .total_downdubs
    data.reset_mock()
    assert event.total_downdubs == data.get.return_value.get.return_value
    data.get.assert_called_once_with('playlist', {})
    data.get.return_value.get.assert_called_once_with('downdubs')

    # Check .length with some value
    data.reset_mock()
    assert event.length == datetime_mock.timedelta.return_value
    datetime_mock.timedelta.assert_called_once_with(
        milliseconds=data.get.return_value.get.return_value
    )
    data.get.assert_called_once_with('playlist', {})
    data.get.return_value.get.assert_called_once_with('songLength')

    # Check .played with some value
    data.reset_mock()
    assert event.played == datetime_mock.datetime.utcfromtimestamp.return_value
    datetime_mock.datetime.utcfromtimestamp.assert_called_once_with(
        data.get.return_value.get.return_value.__truediv__.return_value
    )
    data.get.return_value.get.return_value.__truediv__.assert_called_once_with(1000)
    data.get.assert_called_once_with('playlist', {})

    # Changing to without values
    data.get.return_value = {}

    # Check .length without value
    data.reset_mock()
    assert event.length is None
    data.get.assert_called_once_with('playlist', {})

    # Check .played without value
    data.reset_mock()
    assert event.played is None
    data.get.assert_called_once_with('playlist', {})

    # Check __repr__ works
    assert repr(event)


@pytest.mark.asyncio
async def test_dubtrack_room_queue_reorder():
    data, backend = mock.MagicMock(), mock.MagicMock()
    event = dubtrack.DubtrackRoomQueueReorder(data=data, dubtrack_backend=backend)

    # Check __ini__
    backend._register_user.assert_called_once_with(data.__getitem__.return_value)
    data.__getitem__.assert_called_once_with('user')

    # Check .sender
    data.reset_mock()
    assert event.sender == backend._get_entity.return_value
    backend._get_entity.assert_called_once_with(
        data.get.return_value.get.return_value
    )
    data.get.assert_called_once_with('user', {})
    data.get.return_value.get.assert_called_once_with('username')

    # Check __repr__ works
    assert repr(event)


@pytest.mark.asyncio
async def test_dubtrack_user_queue_update():
    pass

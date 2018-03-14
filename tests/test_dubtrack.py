# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import unittest.mock as mock

import asynctest as am
import pytest

from abot import dubtrack


def test_dubtrack_object():
    data, backend = object(), object()
    dub_obj = dubtrack.DubtrackObject(data, backend)

    assert dub_obj._dubtrack_backend == backend
    assert dub_obj._data == data


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

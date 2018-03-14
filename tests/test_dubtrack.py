# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import unittest.mock as mock

from abot import dubtrack


def test_dubtrack_object():
    data, backend = object(), object()
    dub_obj = dubtrack.DubtrackObject(data, backend)

    assert dub_obj._dubtrack_backend == backend
    assert dub_obj._data == data


def test_dubtrack_channel():
    data, backend = mock.MagicMock(), mock.MagicMock()

    channel = dubtrack.DubtrackChannel(data, backend)

    backend._register_user.assert_called_once_with(data)




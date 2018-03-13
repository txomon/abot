# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import unittest.mock as mock

import pytest

from abot import cli


def test_stringio_wrapper():
    m = mock.MagicMock()
    with cli.stringio_wrapper(m) as fd:
        fd.write('aaaa')

    m.assert_called_once_with('aaaa')


# Integration tests

@pytest.mark.asyncio
async def test_simple_bot_async_command():
    """Test command through bot interface"""
    message_mock = mock.MagicMock()
    message_mock.text = 'bot ping'

    @cli.group()
    def acmds(): pass

    ping_mock = mock.MagicMock()

    @acmds.command()
    async def ping(*args, **kwargs):
        ping_mock(*args, **kwargs)

    cmd_collection = cli.CommandCollection(sources=[acmds])

    await cmd_collection.async_message(message_mock)

    ping_mock.assert_called_once_with()


def test_simple_cli_async_command():
    """Test command through cli interface"""

    @cli.group()
    def acmds(): pass

    ping_mock = mock.MagicMock()

    @acmds.command()
    async def ping(*args, **kwargs):
        ping_mock(*args, **kwargs)

    cmd_collection = cli.CommandCollection(sources=[acmds])
    cmd_collection.main(['ping'], standalone_mode=False)

    ping_mock.assert_called_once_with()


@pytest.mark.skip('Not supported: Sync command in cli interface')
def test_simple_cli_sync_command():
    @cli.group()
    def acmds(): pass

    ping_mock = mock.MagicMock()

    @acmds.command()
    def ping(*args, **kwargs):
        ping_mock(*args, **kwargs)

    cmd_collection = cli.CommandCollection(sources=[acmds])
    cmd_collection.main(['ping'], standalone_mode=False)

    ping_mock.assert_called_once_with()


@pytest.mark.skip('Not supported: Sync command in bot interface')
def test_simple_bot_sync_command():
    """Test sync command through bot interface"""
    message_mock = mock.MagicMock()
    message_mock.text = 'bot ping'

    @cli.group()
    def acmds(): pass

    ping_mock = mock.MagicMock()

    @acmds.command()
    async def ping(*args, **kwargs):
        ping_mock(*args, **kwargs)

    cmd_collection = cli.CommandCollection(sources=[acmds])

    cmd_collection.async_message(message_mock)

    ping_mock.assert_called_once_with()

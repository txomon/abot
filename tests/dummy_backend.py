# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from unittest import mock

from abot.bot import Backend, Event, MessageEvent


class DummyBackend(Backend):
    def __init__(self):
        self.events = []
        self.me = mock.MagicMock()

    def configure(self, **config):
        pass

    async def initialize(self):
        pass

    async def consume(self):
        for event in self.events:
            if isinstance(event, BaseException):
                raise event
            else:
                yield event

    def whoami(self):
        return self.me


class DummyEvent(Event):
    pass


class DummyMessageEvent(MessageEvent, DummyEvent):
    @property
    def text(self):
        return ''

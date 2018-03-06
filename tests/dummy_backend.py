# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from unittest import mock

from abot.bot import Backend


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
            yield event

    def whoami(self):
        return self.me

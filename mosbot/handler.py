# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from typing import Any

from abot.dubtrack import DubtrackSkip, DubtrackPlaying


def history_handler(event: Any[DubtrackSkip, DubtrackPlaying]):
    if isinstance(event, DubtrackPlaying):
        pass
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from typing import Any

from abot.dubtrack import DubtrackDub, DubtrackPlaying, DubtrackSkip
from mosbot.query import ensure_connection
from mosbot.usecase import ensure_dubtrack_playing, ensure_dubtrack_skip, ensure_dubtrack_dub


async def history_handler(event: Any[DubtrackSkip, DubtrackPlaying, DubtrackDub]):
    async with ensure_connection(None) as conn:
        if isinstance(event, DubtrackPlaying):
            await ensure_dubtrack_playing(event=event, conn=conn)
        elif isinstance(event, DubtrackSkip):
            await ensure_dubtrack_skip(event=event, conn=conn)
        elif isinstance(event, DubtrackDub):
            await ensure_dubtrack_dub(event=event, conn=conn)


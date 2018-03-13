# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import pytest

from abot.util import iterator_merge


async def three_yields():
    yield 1
    yield 2
    yield 3


async def exception_yield():
    yield 1
    raise Exception()


@pytest.mark.asyncio
async def test_iterator_merge_normal():
    y1, y2 = three_yields(), three_yields()
    async for item in iterator_merge({y1: asyncio.ensure_future(y1.__anext__()), y2: None}):
        print(item)

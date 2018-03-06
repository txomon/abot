# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
from typing import AsyncIterator


async def iterator_merge(*iterators: AsyncIterator):
    iterators = {i: None for i in iterators}
    while iterators:
        for iterator, value in list(iterators.items()):
            if not value:
                iterators[iterator] = asyncio.ensure_future(iterator.__anext__())

        tasks, _ = await asyncio.wait(iterators.values(), return_when=asyncio.FIRST_COMPLETED)
        for task in tasks:
            # We send the result up
            try:
                res = task.result()
                yield res
            except StopAsyncIteration:
                # We remove the task from the list
                for it, old_next in list(iterators.items()):
                    if task is old_next:
                        iterators.pop(it)
            else:
                # We remove the task from the key
                for it, old_next in list(iterators.items()):
                    if task is old_next:
                        iterators[it] = None

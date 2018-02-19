# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio


async def iterator_merge(*iterators):
    all_iterators, iterators = iterators, {i: None for i in iterators}
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


if __name__ == '__main__':
    async def gen(t):
        for n in range(10):
            yield n
            await asyncio.sleep(t)


    async def test():
        async for n in iterator_merge(gen(0.3), gen(0.5)):
            print(n)


    loop = asyncio.get_event_loop()
    loop.run_until_complete(test())

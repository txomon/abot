# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import json
import logging

import aiohttp
from aiohttp import WSMsgType

logger = logging.getLogger(__name__)


async def ws_consume(url):
    session = aiohttp.ClientSession()
    async with session.ws_connect(url) as socket:
        async for message in socket:
            if message.tp == WSMsgType.text:
                logger.debug('Received %s', message)
                yield json.loads(message)
            elif message.tp in (WSMsgType.closed, WSMsgType.error):
                logger.debug('Finishing ws, %s', message)
                if not socket.closed:
                    await socket.close()
                break
    await session.close()

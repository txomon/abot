# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import json
import logging

import aiohttp
from aiohttp import WSMsgType


logger = logging.getLogger(__name__)


class SlackAPI:
    def __init__(self, bot_access_token, loop=None):
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.bot_access_token = bot_access_token
        self.session = aiohttp.ClientSession(loop=self.loop)

    async def bot_request(self, method, url, json=None, headers=None):
        if headers == None:
            headers = {}
        headers['']
        async with self.session.request(method=method, url=url, json=json, headers=headers) as res:
            return await res.json()

    async def consume_ws(self):
        async with self.session.ws_connect(url) as socket:
            async for message in socket:
                if message.tp == WSMsgType.text:
                    logger.debug('Received %s', message)
                    yield json.loads(message)
                elif message.tp in (WSMsgType.closed, WSMsgType.error):
                    logger.debug('Finishing ws, %s', message)
                    if not socket.closed:
                        await socket.close()
                    break

    def __del__(self):
        asyncio.ensure_future(self.session.close(), loop=self.loop)

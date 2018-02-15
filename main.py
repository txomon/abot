import asyncio
import aiohttp
import logging
import string
import random
import json
import time
from yarl import URL

AIO_SESSION = None

WS_URL = URL('https://ws.dubtrack.fm/ws/')

logger = logging.getLogger()


def get_aio_session():
    global AIO_SESSION
    if AIO_SESSION:
        return AIO_SESSION
    AIO_SESSION = aiohttp.ClientSession()
    return AIO_SESSION


def gen_request_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=44))


class DubtrackWS:
    INIT = '0'
    PING = '2'
    PONG = '3'
    DATA = '4'

    def __init__(self, room='master-of-soundtrack'):
        self.ws_config = {}
        self.heartbeat = None
        self.ws_client_id = None
        self.ws_session = None
        self.room_info = None

    async def api_get(self, url):
        session = get_aio_session()
        async with session.get(url) as resp:
            response = await resp.json()
        return response['data']

    async def get_token(self):
        response = await self.api_get('https://api.dubtrack.fm/auth/token')
        return response['token']

    async def get_room_info(self, room):
        response = await self.api_get(f'https://api.dubtrack.fm/room/{room}')
        self.room_info = response
        return response

    async def get_active_song(self):
        room_id = self.room_info['_id']
        return await self.api_get(f'https://api.dubtrack.fm/room/{room_id}/playlist/active')

    async def get_users(self):
        room_id = self.room_info['_id']
        return await self.api_get(f'https://api.dubtrack.fm/room/{room_id}/users')

    async def get_user(self, user_id):
        return await self.api_get(f'https://api.dubtrack.fm/user/{user_id}')

    async def raw_ws_consume(self):
        last_token_fail = last_consume_fail = 0
        while True:  # two tries per level
            try:
                token = await self.get_token()
            except:
                logger.exception('Trouble getting token')
                now = time.time()
                if last_token_fail + 15 > now:  # If the token has failed in the last 15 secs
                    break
                last_token_fail, last_consume_fail = now, 0
                continue
            while True:
                try:
                    async for msg in self._raw_ws_consume(access_token=token):
                        yield msg
                except:
                    logger.exception('Consumption has failed')
                    now = time.time()
                    if last_consume_fail + 15 > now:  # If consumption has failed in the last 15 secs
                        break
                    last_consume_fail = now

    async def _raw_ws_consume(self, access_token):
        params = {
            'connect': 1,
            'EIO': 3,
            'transport': 'websocket',
            'access_token': access_token,
        }
        if self.ws_client_id:
            params['clientId'] = self.ws_client_id
        ws_connect_url = WS_URL.with_query(params)

        session = get_aio_session()
        async with session.ws_connect(ws_connect_url) as ws_session:
            self.ws_session = ws_session
            await self.ws_session_opened_cb()
            async for msg in ws_session:
                if msg.type in (aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                    logger.info('Closed WS channel')
                    break
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    yield (ws_session, msg.data)
            self.ws_session = None

    async def ws_send(self, message):
        for _ in range(3):
            if self.ws_session:
                break
            await asyncio.sleep(0.5)
        else:
            logger.error('Cannot send message, ws_session is not set')
            logger.debug(f'Message that cannot be sent is: {message}')
            raise Exception('No session available')
        logger.debug(f'Sending message {message}')
        await self.ws_session.send_str(message)

    async def do_heartbeat(self, interval):
        while True:
            logger.debug('Sending ping')
            await self.ws_send(self.PING)
            await asyncio.sleep(interval/1000)

    async def ws_session_opened_cb(self):
        if not self.heartbeat:
            # Just harcoding, not important
            self.heartbeat = asyncio.ensure_future(self.do_heartbeat(25000))
        await self.ws_send('4{action: 10, channel: "room:561b1e59c90a9c0e00df610b"}')

    async def ws_api_consume(self):
        async for session, message in self.raw_ws_consume():
            # They have a digit+json... => 1{"asdf": "czxc"}
            code = message.data[0]
            if code == self.INIT:
                continue  # Ignoring the heartbeat rate for now
            elif code == self.PING:
                logger.warning('Received a ping?!?')
                continue
            elif code == self.PONG:
                logger.debug('Received pong')
                continue
            elif code != '4':  # 4 is the main case
                logger.warning('Received unknown message {message.data}')
                continue

            logger.info(f'Received message: {message}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    dubtrack = DubtrackWS()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(dubtrack.ws_api_consume())

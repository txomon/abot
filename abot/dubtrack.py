# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import json
import logging
import random
import string
import time
from collections import defaultdict

import aiohttp
from yarl.__init__ import URL

logger = logging.getLogger('dubtrack')
logger_layer1 = logging.getLogger('dubtrack.layer1')
logger_layer2 = logging.getLogger('dubtrack.layer2')
logger_layer3 = logging.getLogger('dubtrack.layer3')


def gen_request_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=44))


class DubtrackWS:
    INIT = '0'
    PING = '2'
    PONG = '3'
    DATA = '4'

    def __init__(self, room='master-of-soundtrack'):
        self.room = room
        self.heartbeat = None
        self.ws_client_id = None
        self.ws_session = None
        self.room_info = None
        self.connection_id = None
        self.connected_clients = defaultdict(set)
        self.aio_session = aiohttp.ClientSession()

    async def api_get(self, url):
        async with self.aio_session.get(url) as resp:
            response = await resp.json()
        return response['data']

    async def get_token(self):
        # {'action': 17,
        #  'clientId': '4d3855621cd95d0d6a363806f712e2d0',
        #  'reqId': 'b5509b95b608cb7609891ef9e162cba3',
        #  'token': 'eyJhbGciOiJ.........HJwQL-7ytGnsXkucV5h_A_pV8V6YsA7DYQgxRpOaQMg'}
        response = await self.api_get('https://api.dubtrack.fm/auth/token')
        return response['token']

    async def get_room_info(self):
        # {'__v': 0,
        #  '_id': '561b1e59c90a9c0e00df610b',
        #  '_user': {'__v': 0,
        #            '_id': '56097db281c87803009bd1c5',
        #            'created': 1443462577850,
        #            'dubs': 0,
        #            'profileImage': {'bytes': 34965,
        #                             'etag': '495e80a989c26e9a5e672f243c8f3322',
        #                             'format': 'jpg',
        #                             'height': 500,
        #                             'overwritten': True,
        #                             'placeholder': False,
        #                             'resource_type': 'image',
        #                             'secure_url':
        # 'https://res.cloudinary.com/hhberclba/image/upload/v1510175888/user/56097db281c87803009bd1c5.jpg',
        #                             'type': 'upload',
        #                             'url':
        # 'http://res.cloudinary.com/hhberclba/image/upload/v1510175888/user/56097db281c87803009bd1c5.jpg',
        #                             'version': 1510175888,
        #                             'width': 500},
        #            'roleid': 1,
        #            'status': 1,
        #            'username': 'mullins'},
        #  'activeUsers': 9,
        #  'allowedDjs': 0,
        #  'background': {'bytes': 849194,
        #                 'etag': '685925bd5248799f9f03eeeec7a485a1',
        #                 'format': 'jpg',
        #                 'height': 1200,
        #                 'public_id': 'kealmtphavj32zsshcsd',
        #                 'resource_type': 'image',
        #                 'secure_url': 'https://res.cloudinary.com/hhberclba/image/upload/v1446588169
        # /kealmtphavj32zsshcsd.jpg',
        #                 'tags': [],
        #                 'type': 'upload',
        #                 'url': 'http://res.cloudinary.com/hhberclba/image/upload/v1446588169/kealmtphavj32zsshcsd
        # .jpg',
        #                 'version': 1446588169,
        #                 'width': 1920},
        #  'created': 1444617817050,
        #  'currentSong': {'fkid': '_imFm3FdFJE',
        #                  'name': 'Ennio Morricone - Giù la testa - (1971)',
        #                  'songid': '5824295e8fae8e0f00209a30',
        #                  'type': 'youtube'},
        #  'description': 'film/videogame scores/soundtracks and epic/trailer music.\n'
        #         '\n'
        #         'rules: http://mos.rf.gd/index.html\n'
        #         'overplayed list: http://mos.rf.gd/overplayed.html\n'
        #         'facebook page: https://www.facebook.com/MasterofSoundtrack/\n'
        #         'mail address: masterofsoundtrack(@)yahoo.com\n'
        #         '---\n'
        #         'custom skin: http://bit.ly/dubtracky\n'
        #         '---\n'
        #         'dub+, helpful dubtrack extension: https://dub.plus/#/\n'
        #         '---\n'
        #         'next NameThatTune: '
        #         'https://www.facebook.com/events/203834513429820/\n'
        #         '---\n'
        #         'first ever MoS review: http://bit.ly/296M8PX',
        #  'displayDJinQueue': True,
        #  'displayInLobby': True,
        #  'displayInSearch': True,
        #  'displayQueue': False,
        #  'displayUserGrab': True,
        #  'displayUserJoin': True,
        #  'displayUserLeave': True,
        #  'isPublic': False,
        #  'lang': None,
        #  'limitQueueLength': False,
        #  'lockQueue': False,
        #  'maxLengthSong': 11,
        #  'maxSongQueueLength': 0,
        #  'metaDescription': 'MoS, MasterOfSoundtrack, masterofsoundtrack, Master of '
        #  'Soundtrack, master of soundtrack, scores, soundtrack, '
        #  'movie, film, videogame, epic music, trailer',
        #  'musicType': None,
        #  'name': 'Master Of Soundtrack',
        #  'otSession': None,
        #  'password': None,
        #  'realTimeChannel': 'dubtrackfm-master-of-soundtrack',
        #  'recycleDJ': True,
        #  'roomDisplay': 'public',
        #  'roomEmbed': '',
        #  'roomType': 'room',
        #  'roomUrl': 'master-of-soundtrack',
        #  'slowMode': False,
        #  'status': 1,
        #  'timeSongQueueRepeat': 1440,
        #  'updated': 1444617817050,
        #  'userid': '56097db281c87803009bd1c5',
        #  'waitListRandom': False,
        #  'welcomeMessage': 'Welcome to MoS! Please take 5 minutes to read the rules: '
        #            'http://mos.rf.gd/index.html - Also check the OP list and '
        #            'avoid those songs: http://mos.rf.gd/overplayed.html\n'
        #            'Visit us on FB: http://xurl.es/hncih , next NTT: '
        #            'http://xurl.es/3u71y'}

        response = await self.api_get(f'https://api.dubtrack.fm/room/{self.room}')
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

    async def get_history(self, page=None):
        # [{'__v': 0,
        #   '_id': '5a8453aed51c3101003def50',
        #   '_song': {'__v': 0,
        #             '_id': '5795e51c828c22790037db1e',
        #             'created': '2016-07-25T10:08:28.691Z',
        #             'fkid': 'EqkFgAn4U-o',
        #             'images': {'thumbnail': 'https://i.ytimg.com/vi/EqkFgAn4U-o/hqdefault.jpg'},
        #             'name': 'Me Before You Orchestral- Craig Armstrong (Me Before You- The Score)',
        #             'songLength': 434000,
        #             'type': 'youtube'},
        #   '_user': {'__v': 0,
        #             '_id': '56a80c626894b9410067b716',
        #             'created': 1453853793914,
        #             'dubs': 0,
        #             'profileImage': {'bytes': 33387,
        #                              'etag': '0eb4420cbced52aa81f1bd3368a87f27',
        #                              'format': 'gif',
        #                              'height': 325,
        #                              'pages': 4,
        #                              'public_id': 'user/56a80c626894b9410067b716',
        #                              'resource_type': 'image',
        #                              'secure_url':
        # 'https://res.cloudinary.com/hhberclba/image/upload/v1477307984/user/56a80c626894b9410067b716.gif',
        #                              'tags': [],
        #                              'type': 'upload',
        #                              'url':
        # 'http://res.cloudinary.com/hhberclba/image/upload/v1477307984/user/56a80c626894b9410067b716.gif',
        #                              'version': 1477307984,
        #                              'width': 325},
        #             'roleid': 1,
        #             'status': 1,
        #             'username': 'hennersC'},
        #     'created': 1518621605692,
        #     'downdubs': 0,
        #     'isActive': True,
        #     'isPlayed': True,
        #     'order': 10,
        #     'played': 1518787795607,
        #     'roomid': '561b1e59c90a9c0e00df610b',
        #     'skipped': False,
        #     'songLength': 434000,
        #     'songid': '5795e51c828c22790037db1e',
        #     'updubs': 2,
        #     'userid': '56a80c626894b9410067b716'}]
        room_id = self.room_info['_id']
        url = URL(f'https://api.dubtrack.fm/room/{room_id}/playlist/history')
        if page:
            url = url.with_query({'page': page})
        return await self.api_get(url)

    async def raw_ws_consume(self):
        last_token_fail = last_consume_fail = 0
        await self.get_room_info()
        while True:  # two tries per level
            try:
                token = await self.get_token()
            except:
                logger_layer1.exception('Trouble getting token')
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
                    logger_layer1.exception('Consumption has failed')
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

        ws_connect_url = str(URL('https://ws.dubtrack.fm/ws/').with_query(params))

        async with self.aio_session.ws_connect(ws_connect_url) as ws_session:
            self.ws_session = ws_session
            await self.ws_session_opened_cb()
            async for msg in ws_session:
                if msg.type in (aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                    logger_layer1.debug('Closed WS channel')
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
            logger_layer1.error('Cannot send message, ws_session is not set')
            logger_layer1.debug(f'Message that cannot be sent is: {message}')
            raise Exception('No session available')
        logger_layer1.debug(f'Sending message {message}')
        await self.ws_session.send_str(message)

    async def do_heartbeat(self, interval):
        while True:
            logger_layer1.debug('Sending ping')
            await self.ws_send(self.PING)
            await asyncio.sleep(interval / 1000)

    async def send_room_subscription(self):
        if not self.room_info or not self.room_info.get('_id'):
            await self.get_room_info()
        subscription = {
            'action': 10,
            "channel": f'room:{self.room_info["_id"]}',
        }
        await self.ws_send(f'4{json.dumps(subscription)}')

    async def send_presence_update(self):
        if not self.room_info or not self.room_info.get('_id'):
            await self.get_room_info()
        presence_update = {
            "action": 14,
            "channel": f'room:{self.room_info["_id"]}',
            "presence": {"action": 0, "data": {}},
            "reqId": gen_request_id()}
        await self.ws_send(f'4{json.dumps(presence_update)}')

    async def ws_session_opened_cb(self):
        if not self.heartbeat:
            # Just harcoding, not important
            self.heartbeat = asyncio.ensure_future(self.do_heartbeat(25000))
        await self.send_room_subscription()
        await self.send_presence_update()

    async def ws_api_consume(self):
        async for session, message in self.raw_ws_consume():
            # First layer
            # They have a digit+json... => 1{"asdf": "czxc"}
            code = message[0]
            if code == self.INIT:
                continue  # Ignoring the heartbeat rate for now
            elif code == self.PING:
                logger_layer1.warning('Received a ping?!?')
                continue
            elif code == self.PONG:
                logger_layer1.debug('Received pong')
                continue
            elif code != '4':  # 4 is the main case
                logger_layer1.warning('Received unknown message {message}')
                continue

            logger_layer1.debug(f'Received message: {message}')

            # Second layer: 4
            # They have action in the first level of the json
            data = json.loads(message[1:])
            action = data['action']
            if action == 4:  # Client ID given for future reconnections
                self.ws_client_id = data['clientId']
                self.connection_id = data['connectionId']
                continue
            elif action == 11:  # ACK from action=10, also contains what in #4
                continue
            elif action == 14:  # Presence updates
                presence = data['presence']
                connection_id = presence.get('connectionId')
                client_id = presence.get('clientId')
                if 'reqId' in data and connection_id != self.connection_id:
                    logger_layer2.error(
                        f'Presence packet says connectionId {connection_id} instead of {self.connection_id}. '
                        f'Ignoring..?')
                    continue
                if action == 0:
                    logger_layer2.debug(
                        f'Client {client_id} connected with {connection_id}')
                    self.connected_clients[client_id].add(connection_id)
                elif action == 1:
                    logger_layer2.debug(
                        f'Client {client_id} disconnected with {connection_id}')
                    self.connected_clients[client_id].remove(connection_id)
                continue
            elif action != 15:  # 4, Action 15 is the main case
                logger_layer2.warning('Received unknown action {action}')
                continue

            # Third layer: 4=>action#15
            message = data['message']
            if message['type'] != 'json':
                logger_layer3.info(
                    f'Ignoring, becase type is not json: {message}')
                continue

            content_type = message['name']
            content = json.loads(message['data'])
            if content_type == 'chat-message':
                # {'chatid': '560b135c7ae1ea0300869b20-1518783003490',
                #  'message': 'this is going goood :P',
                #  'queue_object': {'__v': 0,
                #                   '_id': '5628db0a3883a45600b7e68f',
                #                   '_user': '560b135c7ae1ea0300869b20',
                #                   'active': True,
                #                   'authorized': True,
                #                   'dubs': 368,
                #                   'order': 99999,
                #                   'ot_token': None,
                #                   'playedCount': 1677,
                #                   'queuePaused': None,
                #                   'roleid': '52d1ce33c38a06510c000001',
                #                   'roomid': '561b1e59c90a9c0e00df610b',
                #                   'skippedCount': 0,
                #                   'songsInQueue': 0,
                #                   'updated': 1518771989676,
                #                   'userid': '560b135c7ae1ea0300869b20',
                #                   'waitLine': 0},
                #  'time': 1518783003490,
                #  'type': 'chat-message',
                #  'user': {'__v': 0,
                #           '_force_updated': 1516971162191,
                #           '_id': '560b135c7ae1ea0300869b20',
                #           'created': 1443566427591,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '560b135c7ae1ea0300869b21',
                #                        'userid': '560b135c7ae1ea0300869b20'},
                #           'username': 'txomon'}}
                chatid = content['chatid']
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                logger_layer3.debug(
                    f'Chat {username}#{userid} (chatid#{chatid}): {content["message"]}')
            elif content_type == 'chat-skip':
                # {'type': 'chat-skip', 'username': 'txomon'}
                username = content['username']
                logger_layer3.debug(f'Chat-skip by {username}')
            elif content_type == 'delete-chat-message':
                # {'chatid': '560b135c7ae1ea0300869b20-1518784684020',
                #  'type': 'delete-chat-message',
                #  'user': {'__v': 0,
                #           '_force_updated': 1516971162191,
                #           '_id': '560b135c7ae1ea0300869b20',
                #           'created': 1443566427591,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '560b135c7ae1ea0300869b21',
                #                        'userid': '560b135c7ae1ea0300869b20'},
                #           'username': 'txomon'}}
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                chatid = content['chatid']
                logger_layer3.debug(f'User {username}#{userid} deleted {chatid}')
            elif content_type == 'room_playlist-queue-update-dub':
                # {'type': 'room_playlist-queue-update-dub',
                #  'user': {'__v': 0,
                #           '_force_updated': 1499443841892,
                #           '_id': '5628edc08d7d6a5600335d3d',
                #           'created': 1445522880666,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '5628edc08d7d6a5600335d3e',
                #                        'userid': '5628edc08d7d6a5600335d3d'},
                #           'username': 'iCel'}}
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                status = content['user']['status']
                roleid = content['user']['roleid']
                dubs = content['user']['dubs']
                logger_layer3.debug(
                    f'User {username}/{userid} changed personal queue')
            elif content_type == 'user-join':
                # {'roomUser': {'__v': 0,
                #               '_id': '57f36aff34169c1a0018f92d',
                #               '_user': '57f36acd6c9b5c5b003d41d2',
                #               'active': False,
                #               'authorized': True,
                #               'dubs': 3533,
                #               'order': 99999,
                #               'ot_token': None,
                #               'playedCount': 10862,
                #               'queuePaused': None,
                #               'roomid': '561b1e59c90a9c0e00df610b',
                #               'skippedCount': 0,
                #               'songsInQueue': 588,
                #               'updated': 1518783589638,
                #               'userid': '57f36acd6c9b5c5b003d41d2',
                #               'waitLine': 0},
                #  'type': 'user-join',
                #  'user': {'__v': 0,
                #           '_force_updated': 1504509671098,
                #           '_id': '57f36acd6c9b5c5b003d41d2',
                #           'created': 1475570381585,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '57f36acd6c9b5c5b003d41d3',
                #                        'userid': '57f36acd6c9b5c5b003d41d2'},
                #           'username': 'eberg'}}
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                # TODO: Explore roomUser
                logger_layer3.debug(f'User {username}{userid} joined')
            elif content_type == 'user-pause-queue':
                # {'type': 'user-pause-queue',
                #  'user': {'__v': 0,
                #           '_force_updated': 1499443841892,
                #           '_id': '5628edc08d7d6a5600335d3d',
                #           'created': 1445522880666,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '5628edc08d7d6a5600335d3e',
                #                        'userid': '5628edc08d7d6a5600335d3d'},
                #           'username': 'iCel'},
                #     'user_queue': {'__v': 0,
                #                    '_id': '5628ededa2d0f81300edc39a',
                #                    '_user': '5628edc08d7d6a5600335d3d',
                #                    'active': True,
                #                    'authorized': True,
                #                    'dubs': 25899,
                #                    'order': 99999,
                #                    'ot_token': None,
                #                    'playedCount': 23897,
                #                    'queuePaused': None,
                #                    'roleid': '5615fa9ae596154a5c000000',
                #                    'roomid': '561b1e59c90a9c0e00df610b',
                #                    'skippedCount': 0,
                #                    'songsInQueue': 31,
                #                    'updated': 1518783663567,
                #                    'userid': '5628edc08d7d6a5600335d3d',
                #                    'waitLine': 0}}

                # TODO: Explore user_queue.songsInQueue
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']

                logger_layer3.debug(
                    f'User {username}#{userid} stopped playlist')

            elif content_type == 'room_playlist-dub':
                # {'dubtype': 'downdub',
                #  'playlist': {'__v': 0,
                #               '_id': '5a8453cad51c3101003df01c',
                #               '_song': '5a0db972fd20620100678621',
                #               '_user': '56a80c626894b9410067b716',
                #               'created': 1518621640481,
                #               'downdubs': 1,
                #               'isActive': True,
                #               'isPlayed': False,
                #               'order': 2,
                #               'played': 1518782587986,
                #               'roomid': '561b1e59c90a9c0e00df610b',
                #               'skipped': False,
                #               'songLength': 221000,
                #               'songid': '5a0db972fd20620100678621',
                #               'updubs': 0,
                #               'userid': '56a80c626894b9410067b716'},
                #     'type': 'room_playlist-dub',
                #     'user': {'__v': 0,
                #              '_force_updated': 1516971162191,
                #              '_id': '560b135c7ae1ea0300869b20',
                #              'created': 1443566427591,
                #              'dubs': 0,
                #              'roleid': 1,
                #              'status': 1,
                #              'userInfo': {'__v': 0,
                #                           '_id': '560b135c7ae1ea0300869b21',
                #                           'userid': '560b135c7ae1ea0300869b20'},
                #              'username': 'txomon'}}
                dubtype = content['dubtype']
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                downdubs = content['playlist']['downdubs']
                updubs = content['playlist']['updubs']
                logger_layer3.debug(
                    f"Song {dubtype} by {username}#{userid}, total {updubs}U/{downdubs}D")
            elif content_type.startswith('user_update'):
                # {'type': 'user_update_56096ce7a98a6b0300144e33',
                #  'user': {'_id': '5628b1c7e884391300d7427c',
                #           'updated': 1518781252893,
                #           'skippedCount': 0,
                #           'playedCount': 39994,
                #           'songsInQueue': 386,
                #           'active': True,
                #           'dubs': 15316,
                #           'order': 99999,
                #           'roomid': '561b1e59c90a9c0e00df610b',
                #           'userid': '56096ce7a98a6b0300144e33',
                #           '_user': '56096ce7a98a6b0300144e33',
                #           '__v': 0,
                #           'ot_token': None,
                #           'roleid': '5615fd84e596150061000003',
                #           'queuePaused': None,
                #           'authorized': True,
                #           'waitLine': 0}}
                user = content['user']
                userid = user['userid']
                skipped_count = user['skippedCount']
                played_count = user['playedCount']
                songs_in_queue = user['songsInQueue']
                dubs = user['dubs']
                logger_layer3.debug(
                    f'User updated {userid}, skip {skipped_count}, played {played_count}, queue {songs_in_queue}, '
                    f'dubs {dubs}')
            elif content_type == 'room_playlist-update':
                # {'startTime': -1,
                #  'song': {'_id': '5a853a0a07f061010053d3c8',
                #           'created': 1518680579959,
                #           'isActive': True,
                #           'isPlayed': False,
                #           'skipped': False,
                #           'order': 109,
                #           'roomid': '561b1e59c90a9c0e00df610b',
                #           'songLength': 194000,
                #           'updubs': 0, 'downdubs': 0,
                #           'userid': '56096ce7a98a6b0300144e33',
                #           'songid': '584efe5534194d8400cfd013',
                #           '_user': '56096ce7a98a6b0300144e33',
                #           '_song': '584efe5534194d8400cfd013',
                #           '__v': 0,
                #           'played': 1518781826209},
                #  'songInfo': {'_id': '584efe5534194d8400cfd013',
                #               'name': 'Luis Alvarez - Final Time',
                #               'images': {'thumbnail': 'https://i.ytimg.com/vi/KHkPbbdu5kk/hqdefault.jpg'},
                #               'type': 'youtube',
                #               'songLength': 194000,
                #               'fkid': 'KHkPbbdu5kk',
                #               '__v': 0,
                #               'created': '2016-12-12T19:45:25.669Z'},
                #  'type': 'room_playlist-update'}
                songinfo = content['songInfo']
                name = songinfo['name']
                songtype = songinfo['type']
                songid = songinfo['fkid']
                logger_layer3.debug(f'Now playing {songtype}#{songid}: {name}')
            elif content_type == 'room_playlist-queue-reorder':
                # {'type': 'room_playlist-queue-reorder',
                #  'user': {'__v': 0,
                #           '_force_updated': 1516971162191,
                #           '_id': '560b135c7ae1ea0300869b20',
                #           'created': 1443566427591,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '560b135c7ae1ea0300869b21',
                #                        'userid': '560b135c7ae1ea0300869b20'},
                #           'username': 'txomon'}}
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                logger_layer3.debug(
                    f'User {username}#{userid} reordered the queue')
            elif content_type == 'user-unsetrole':
                # {'modUser': {'__v': 0,
                #              '_id': '560b135c7ae1ea0300869b20',
                #              'created': 1443566427591,
                #              'dubs': 0,
                #              'profileImage': {'bytes': 444903,
                #                               'etag': '09da0f0c34e6ddf6eb75516ea66e17bc',
                #                               'format': 'gif',
                #                               'height': 245,
                #                               'overwritten': True,
                #                               'pages': 22,
                #                               'public_id': 'user/560b135c7ae1ea0300869b20',
                #                               'resource_type': 'image',
                #                               'secure_url':
                # 'https://res.cloudinary.com/hhberclba/image/upload/v1486657178/user/560b135c7ae1ea0300869b20.gif',
                #                               'tags': [],
                #                               'type': 'upload',
                #                               'url':
                # 'http://res.cloudinary.com/hhberclba/image/upload/v1486657178/user/560b135c7ae1ea0300869b20.gif',
                #                               'version': 1486657178,
                #                               'width': 245},
                #              'roleid': 1,
                #              'status': 1,
                #              'username': 'txomon'},
                #  'role_object': {'__v': 0,
                #                  '_id': '52d1ce33c38a06510c000001',
                #                  'label': 'Moderator',
                #                  'rights': ['skip',
                #                             'queue-order',
                #                             'kick',
                #                             'ban',
                #                             'mute',
                #                             'set-dj',
                #                             'lock-queue',
                #                             'delete-chat',
                #                             'chat-mention'],
                #                  'type': 'mod'},
                #  'type': 'user-unsetrole',
                #  'user': {'__v': 0,
                #           '_force_updated': 1499443841892,
                #           '_id': '5628edc08d7d6a5600335d3d',
                #           'created': 1445522880666,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '5628edc08d7d6a5600335d3e',
                #                        'userid': '5628edc08d7d6a5600335d3d'},
                #           'username': 'iCel'}}
                modname = content['modUser']['username']
                modid = content['modUser']['_id']
                role = content['role_object']['label']
                roletype = content['role_object']['type']
                rights = content['role_object']['rights']
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                logger_layer3.debug(
                    'User {modname}#{modid} removed from role {role}/{roletype}({", ".join(rights)}) by {username}#{'
                    'userid}')
            elif content_type == 'user-setrole':
                # {'modUser': {'__v': 0,
                #              '_id': '560b135c7ae1ea0300869b20',
                #              'created': 1443566427591,
                #              'dubs': 0,
                #              'profileImage': {'bytes': 444903,
                #                               'etag': '09da0f0c34e6ddf6eb75516ea66e17bc',
                #                               'format': 'gif',
                #                               'height': 245,
                #                               'overwritten': True,
                #                               'pages': 22,
                #                               'public_id': 'user/560b135c7ae1ea0300869b20',
                #                               'resource_type': 'image',
                #                               'secure_url':
                # 'https://res.cloudinary.com/hhberclba/image/upload/v1486657178/user/560b135c7ae1ea0300869b20.gif',
                #                               'tags': [],
                #                               'type': 'upload',
                #                               'url':
                # 'http://res.cloudinary.com/hhberclba/image/upload/v1486657178/user/560b135c7ae1ea0300869b20.gif',
                #                               'version': 1486657178,
                #                               'width': 245},
                #              'roleid': 1,
                #              'status': 1,
                #              'username': 'txomon'},
                #  'role_object': {'__v': 0,
                #                  '_id': '52d1ce33c38a06510c000001',
                #                  'label': 'Moderator',
                #                  'rights': ['skip',
                #                             'queue-order',
                #                             'kick',
                #                             'ban',
                #                             'mute',
                #                             'set-dj',
                #                             'lock-queue',
                #                             'delete-chat',
                #                             'chat-mention'],
                #                  'type': 'mod'},
                #  'type': 'user-setrole',
                #  'user': {'__v': 0,
                #           '_force_updated': 1499443841892,
                #           '_id': '5628edc08d7d6a5600335d3d',
                #           'created': 1445522880666,
                #           'dubs': 0,
                #           'roleid': 1,
                #           'status': 1,
                #           'userInfo': {'__v': 0,
                #                        '_id': '5628edc08d7d6a5600335d3e',
                #                        'userid': '5628edc08d7d6a5600335d3d'},
                #           'username': 'iCel'}}
                modname = content['modUser']['username']
                modid = content['modUser']['_id']
                role = content['role_object']['label']
                roletype = content['role_object']['type']
                rights = content['role_object']['rights']
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                logger_layer3.debug(
                    f'User {modname}#{modid} moved to role {role}/{roletype}({", ".join(rights)}) by {username}#'
                    f'{userid}')
            else:
                logger_layer3.info(
                    f'Received unknown message {content_type}: {pprint.pformat(content)}')

# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import datetime
import json
import logging
import pprint
import random
import string
import time
import weakref
from collections import defaultdict

import aiohttp
from yarl import URL

from abot.bot import Backend, BotObject, Channel, Entity, Event, MessageEvent

logger = logging.getLogger('abot.dubtrack')
logger_layer1 = logging.getLogger('abot.dubtrack.layer1')
logger_layer2 = logging.getLogger('abot.dubtrack.layer2')
logger_layer3 = logging.getLogger('abot.dubtrack.layer3')

logger.setLevel(logging.INFO)
logger_layer1.setLevel(logging.INFO)
logger_layer2.setLevel(logging.INFO)
logger_layer3.setLevel(logging.INFO)


# Dubtrack specific objects
class DubtrackObject(BotObject):
    def __init__(self, data, dubtrack_backend: 'DubtrackBotBackend'):
        self._data = data
        self._dubtrack_backend = dubtrack_backend

    @property
    def backend(self):
        return self._dubtrack_backend


class DubtrackChannel(DubtrackObject, Channel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data)

    async def say(self, text: str):
        if not self._dubtrack_backend.dubtrack_id:
            raise ValueError('You need to login to speak')
        await self._dubtrack_backend.dubtrackws.say_in_room(text)

    @property
    def entities(self):
        entities = []
        for user in self._dubtrack_backend.dubtrack_users:
            entity = self._dubtrack_backend._get_entity(user)
            if entity:
                entities.append(entity)
        return entities

    def __repr__(self):
        cls = self.__class__.__name__
        name = self._data['name']
        id = self._data['_id']
        slug = self._data['roomUrl']
        entities = self.entities
        return f'<{cls} {slug}#{id} name="{name}" {entities}>'


class DubtrackEntity(DubtrackObject, Entity):
    async def tell(self, text: str):
        pass

    @property
    def username(self):
        return self._data.get('username')

    @property
    def id(self):
        return self._data.get('id')

    @property
    def dubs(self):
        return self._data.get('dubs')

    @property
    def played_count(self):
        return self._data.get('played_count')

    @property
    def skips(self):
        return self._data.get('skips')

    @property
    def songs_in_queue(self):
        return self._data.get('songs_in_queue')

    def __repr__(self):
        cls = self.__class__.__name__
        userid = self.id
        username = self.username
        dubs = self.dubs
        played = self.played_count
        skips = self.skips
        songs = self.songs_in_queue
        return f'<{cls} {username}#{userid} {dubs}/{played} {skips}(S) ##{songs}>'

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.id == other.id:
            return True
        return False


class DubtrackEvent(DubtrackObject, Event):
    _data_type = ''

    @classmethod
    def from_data(cls, data, dubtrack_backend: 'DubtrackBotBackend'):
        for cl in cls.__subclasses__():
            if cl._data_type == data['type']:
                return cl(data, dubtrack_backend)
        else:
            return cls(data, dubtrack_backend)

    @property
    def sender(self) -> DubtrackEntity:
        return None

    @property
    def channel(self) -> DubtrackChannel:
        # Return the channel used to send the Event
        if hasattr(self, '_channel'):
            return self._channel
        raise ValueError('Channel is not set')

    @channel.setter
    def channel(self, channel: DubtrackChannel):
        if hasattr(self, '_channel'):
            raise ValueError(f'Channel {self._channel} is in place, cannot replace with {channel}')
        self._channel = channel

    async def reply(self, text: str, to: str = None):
        # Reply to the message mentioning if possible
        return

    def __repr__(self):
        cls = self.__class__.__name__
        return f'<{cls} #{self._data["type"]}>'


class DubtrackMessage(DubtrackEvent, MessageEvent):
    _data_type = 'chat-message'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data.get('user'))

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    @property
    def text(self):
        return self._data.get('message')

    @property
    def message_id(self):
        return self._data.get('chatid')

    def __repr__(self):
        cls = self.__class__.__name__
        chatid = self.message_id
        sender = self.sender
        msg = self.text
        return f'<{cls}#{chatid} {sender} "{msg}">'


class DubtrackSkip(DubtrackEvent):
    _data_type = 'chat-skip'

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('username'))

    def __repr__(self):
        cls = self.__class__.__name__
        sender = self.sender
        return f'<{cls} {sender}>'


class DubtrackDelete(DubtrackEvent):
    _data_type = 'delete-chat-message'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    @property
    def message_id(self):
        return self._data.get('chatid')

    def __repr__(self):
        cls = self.__class__.__name__
        chatid = self.message_id
        sender = self.sender
        return f'<{cls}#{chatid} {sender}>'


class DubtrackDub(DubtrackEvent):
    _data_type = 'room_playlist-dub'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    @property
    def dubtype(self):
        return self._data.get('dubtype')

    @property
    def total_updubs(self):
        return self._data.get('playlist', {}).get('updubs')

    @property
    def total_downdubs(self):
        return self._data.get('playlist', {}).get('downdubs')

    @property
    def length(self):
        song_length = self._data.get('playlist', {}).get('songLength')
        if song_length:
            return datetime.timedelta(milliseconds=song_length)

    @property
    def played(self):
        played = self._data.get('playlist', {}).get('played')
        if played:
            return datetime.datetime.utcfromtimestamp(played / 1000)

    def __repr__(self):
        cls = self.__class__.__name__
        dubtype = self.dubtype
        sender = self.sender
        downdubs = self.total_downdubs
        updubs = self.total_updubs
        return f'<{cls}#{dubtype} {sender} +{updubs}-{downdubs}>'


class DubtrackRoomQueueReorder(DubtrackEvent):
    _data_type = 'room_playlist-queue-reorder'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    def __repr__(self):
        cls = self.__class__.__name__
        sender = self.sender
        return f'<{cls} {sender}>'


class DubtrackUserQueueUpdate(DubtrackEvent):
    _data_type = 'room_playlist-queue-update-dub'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    def __repr__(self):
        cls = self.__class__.__name__
        sender = self.sender
        return f'<{cls} {sender}>'


class DubtrackPlaying(DubtrackEvent):
    _data_type = 'room_playlist-update'

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('song', {}).get('userid'))

    def __repr__(self):
        cls = self.__class__.__name__
        name = self.song_name
        songtype = self.song_type
        songfkid = self.song_external_id
        songid = self.song_id
        sender = self.sender
        return f'<{cls}#{songid} {songtype}#{songfkid} {sender} {name}>'

    @property
    def song_type(self):
        value = self._data.get('songInfo', {}).get('type')
        return value

    @property
    def song_external_id(self):
        value = self._data.get('songInfo', {}).get('fkid')
        return value

    @property
    def song_name(self):
        value = self._data.get('songInfo', {}).get('name')
        return value

    @property
    def song_id(self):
        value = self._data.get('songInfo', {}).get('songid')
        return value

    @property
    def length(self):
        value = self._data.get('songInfo', {}).get('songLength')
        if value:
            return datetime.timedelta(milliseconds=value)

    @property
    def played(self):
        value = self._data.get('song', {}).get('played')
        if value:
            return datetime.datetime.utcfromtimestamp(value / 1000)


class DubtrackJoin(DubtrackEvent):
    _data_type = 'user-join'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    def __repr__(self):
        cls = self.__class__.__name__
        sender = self.sender
        return f'<{cls} {sender}>'


class DubtrackUserPauseQueue(DubtrackEvent):
    _data_type = 'user-pause-queue'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    def __repr__(self):
        cls = self.__class__.__name__
        sender = self.sender
        return f'<{cls} {sender}>'


class DubtrackSetRole(DubtrackEvent):
    _data_type = 'user-setrole'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])
        self._dubtrack_backend._register_user(self._data['modUser'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    @property
    def receiver(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('modUser', {}).get('_id'))

    def __repr__(self):
        cls = self.__class__.__name__
        role = self._data['role_object']['label']
        roletype = self._data['role_object']['type']
        rights = self._data['role_object']['rights']
        receiver = self.receiver
        sender = self.sender
        return f'<{cls} {receiver} -> {role}/{roletype}({", ".join(rights)}) by {sender}>'


class DubtrackUnSetRole(DubtrackEvent):
    _data_type = 'user-unsetrole'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])
        self._dubtrack_backend._register_user(self._data['modUser'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('username'))

    @property
    def receiver(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('modUser', {}).get('_id'))

    def __repr__(self):
        cls = self.__class__.__name__
        role = self._data['role_object']['label']
        roletype = self._data['role_object']['type']
        rights = self._data['role_object']['rights']
        receiver = self.receiver
        sender = self.sender
        return f'<{cls} {receiver} X {role}/{roletype}({", ".join(rights)}) by {sender}>'


class DubtrackUserUpdate(DubtrackEvent):
    _data_type = 'user_update'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dubtrack_backend._register_user(self._data['user'])

    @property
    def sender(self) -> DubtrackEntity:
        return self._dubtrack_backend._get_entity(self._data.get('user', {}).get('userid'))

    def __repr__(self):
        cls = self.__class__.__name__
        user = self._data['user']
        sender = self.sender
        skipped_count = user['skippedCount']
        played_count = user['playedCount']
        songs_in_queue = user['songsInQueue']
        dubs = user['dubs']
        return f'<{cls} {sender} skip#{skipped_count} played#{played_count} queue#{songs_in_queue} dubs#{dubs}>'


# Dubtrack bot plugin

class DubtrackBotBackend(Backend):
    # Official Bot methods
    def __init__(self):
        self.dubtrackws = DubtrackWS()
        self.dubtrack_channel = None
        self.dubtrack_users = defaultdict(dict)  # ID: user_session_info
        self.dubtrack_entities = weakref.WeakValueDictionary()
        self.dubtrack_id = None

    def configure(self, *, username=None, password=None):
        if any((username, password)):
            self.dubtrackws.set_login(username, password)
            ps = '*' * len(password)
            logger.debug(f'Setting username={username}, password={ps}')

    async def initialize(self):
        # Steps are
        await self.dubtrackws.initialize()
        if self.dubtrackws.logged_in:
            session_info = await self.dubtrackws.get_user_session_info()
            username = session_info['username']
            userid = session_info['userInfo']['userid']
            self.dubtrack_id = userid
            self._register_user(session_info)
            logger.info(f'Logged in as {username}#{userid}')
        else:
            logger.info(f'Connected, but not logged in')

        users = await self.dubtrackws.get_users()
        for user in users:
            self._register_user(user)

    async def consume(self):
        await self.dubtrackws.get_room_id()
        room_info = self.dubtrackws.room_info
        self.dubtrack_channel = DubtrackChannel(room_info, self)
        active_song = await self.dubtrackws.get_active_song()
        if active_song:
            yield DubtrackPlaying(active_song, self)
        async for data in self.dubtrackws.ws_api_consume():
            if data['type'].startswith('user_update'):
                event = DubtrackUserUpdate(data, self)
            else:
                event = DubtrackEvent.from_data(data, self)
            event.channel = self.dubtrack_channel
            yield event

    # Internal data tracking methods
    def _register_user(self, user_data):
        if not user_data:
            return
        user_id = None
        update_dict = {}
        if 'userInfo' in user_data:  # From user only
            if 'userid' in user_data['userInfo']:  # From profile
                user_id = user_data['userInfo']['userid']
            if 'created' in user_data:  # From profile only
                update_dict['created'] = user_data['created'] / 1000
        if 'userid' in user_data:  # From user-queue only
            user_id = user_data['userid']
            if 'dubs' in user_data:
                update_dict['dubs'] = user_data['dubs']
        if '_user' in user_data:
            if '_id' in user_data['_user']:
                user_id = user_data['_user']['_id']
            if 'username' in user_data['_user']:
                update_dict['username'] = user_data['_user']['username']
            if 'created' in user_data['_user']:  # From profile only
                update_dict['created'] = user_data['_user']['created'] / 1000
        if 'username' in user_data:  # From user/user-queue
            update_dict['username'] = user_data['username']
        if 'playedCount' in user_data:
            update_dict['played_count'] = user_data['playedCount']
        if 'songsInQueue' in user_data:
            update_dict['songs_in_queue'] = user_data['songsInQueue']
        if 'skippedCount' in user_data:
            update_dict['skips'] = user_data['skippedCount']

        if not user_id:
            return

        self.dubtrack_users[user_id].update(update_dict)

        # Update entity if it exists... As it seems the dict is not updated
        entity = self.dubtrack_entities.get(user_id)  # type: DubtrackEntity
        if entity:
            entity._data.update(update_dict)

    def _get_user_data(self, id_or_name):
        for id, user_data in self.dubtrack_users.items():
            if id_or_name == id:
                data = {'id': id}
                data.update(user_data)
                return data
            elif id_or_name == user_data.get('username'):
                data = {'id': id}
                data.update(user_data)
                return data

    def _get_entity(self, id_or_name):
        user_data = self._get_user_data(id_or_name)
        if not user_data:
            logger.info(f'Information for user {id_or_name} not available')
            return
        user_id = user_data['id']
        entity = self.dubtrack_entities.get(user_id)
        if entity:
            return entity
        entity = DubtrackEntity(user_data, self)
        self.dubtrack_entities[user_id] = entity
        return entity

    def whoami(self) -> DubtrackEntity:
        if self.dubtrack_id:
            return self._get_entity(self.dubtrack_id)


# Dubtrack dirty binding

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
        self.connection_id = None
        self.connected_clients = defaultdict(set)
        self.aio_session = None
        self.user_session_info = None
        self.room_user_info = None
        self.room_info = None
        self.userpass = None
        self.suppress_messages = list()
        self.logged_in = None

    async def initialize(self):
        self.aio_session = aiohttp.ClientSession()
        # POST https://api.dubtrack.fm/auth/dubtrack
        if self.userpass:
            self.logged_in = await self.login(*self.userpass)
        # GET https://api.dubtrack.fm/auth/session
        await self.get_user_session_info()

    def set_login(self, username, password):
        if any((self.user_session_info, self.room_user_info, self.room_info)):
            raise ValueError('Once started, cannot login')
        self.userpass = (username, password)

    async def api_post(self, url, body):
        async with self.aio_session.post(url, body=body) as resp:
            logger.debug(f'Request: {url} - {body}')
            response = await resp.json()
            logger.debug(f'Response: {pprint.pformat(response)}')
        return response['data']

    async def api_get(self, url):
        async with self.aio_session.get(url) as resp:
            logger.debug(f'Request: {url}')
            response = await resp.json()
            logger.debug(f'Response: {pprint.pformat(response)}')
        return response['data']

    async def get_user_session_info(self):
        # {"userInfo": {"_id": "560b135c7ae1ea0300869b21",
        #               "userid": "560b135c7ae1ea0300869b20",
        #               "__v": 0},
        #  "_id": "560b135c7ae1ea0300869b20",
        #  "username": "txomon",
        #  "status": 1,
        #  "roleid": 1,
        #  "dubs": 0,
        #  "created": 1443566427591,
        #  "profileImage": {"public_id": "user/560b135c7ae1ea0300869b20",
        #                   "version": 1486657178,
        #                   "width": 245,
        #                   "height": 245,
        #                   "format": "gif",
        #                   "resource_type": "image",
        #                   "tags": [],
        #                   "pages": 22,
        #                   "bytes": 444903,
        #                   "type": "upload",
        #                   "etag": "09da0f0c34e6ddf6eb75516ea66e17bc",
        #                   "url": "http://res.cloudinary.com/hhberclba/image/upload/v1486657178/user"
        #                          "/560b135c7ae1ea0300869b20.gif",
        #                   "secure_url":
        #                       "https://res.cloudinary.com/hhberclba/image/upload/v1486657178/user"
        #                       "/560b135c7ae1ea0300869b20.gif",
        #                   "overwritten": True},
        #  "__v": 0}

        # OR

        # {'message': 'dologin'}

        if not self.user_session_info:
            self.user_session_info = await self.api_get('https://api.dubtrack.fm/auth/session')

        return self.user_session_info

    async def get_user_role(self):
        # {"room": {"_id": "561b1e59c90a9c0e00df610b",
        #           "name": "Master Of Soundtrack",
        #           "description": "film/videogame scores/soundtracks and epic/trailer music.\n\nrules: "
        #                          "http://mos.rf.gd/index.html\noverplayed list: "
        #                          "http://mos.rf.gd/overplayed.html\nfacebook page: "
        #                          "https://www.facebook.com/MasterofSoundtrack/\nmail address: masterofsoundtrack("
        #                          "@)yahoo.com\n---\ncustom skin: http://bit.ly/dubtracky\n---\ndub+, "
        #                          "helpful dubtrack extension: https://dub.plus/#/\n---\nnext NameThatTune: "
        #                          "https://www.facebook.com/events/203834513429820/\n---\nfirst ever MoS review: "
        #                          "http://bit.ly/296M8PX",
        #           "roomUrl": "master-of-soundtrack",
        #           "realTimeChannel": "dubtrackfm-master-of-soundtrack",
        #           "status": 1,
        #           "roomType": "room",
        #           "isPublic": False,
        #           "lang": None,
        #           "musicType": None,
        #           "password": None,
        #           "allowedDjs": 0,
        #           "maxLengthSong": 11,
        #           "displayQueue": False,
        #           "background": {"public_id": "kealmtphavj32zsshcsd",
        #                          "version": 1446588169,
        #                          "width": 1920,
        #                          "height": 1200,
        #                          "format": "jpg",
        #                          "resource_type": "image",
        #                          "tags": [],
        #                          "bytes": 849194,
        #                          "type": "upload",
        #                          "etag": "685925bd5248799f9f03eeeec7a485a1",
        #                          "url": "http://res.cloudinary.com/hhberclba/image/upload/v1446588169"
        #                                 "/kealmtphavj32zsshcsd.jpg",
        #                          "secure_url": "https://res.cloudinary.com/hhberclba/image/upload/v1446588169"
        #                                        "/kealmtphavj32zsshcsd.jpg"},
        #           "created": 1444617817050,
        #           "updated": 1444617817050,
        #           "userid": "56097db281c87803009bd1c5",
        #           "roomEmbed": "",
        #           "otSession": None,
        #           "_user": "56097db281c87803009bd1c5",
        #           "__v": 0,
        #           "activeUsers": 9,
        #           "currentSong": {"songid": "5677f5e03d9c59270031d943",
        #                           "type": "youtube",
        #                           "fkid": "XHaeAUFaHBU",
        #                           "name": "Halo Wars OST 01 Spirit of Fire"},
        #           "lockQueue": False,
        #           "welcomeMessage": "Welcome to MoS! Please take 5 minutes to read the rules: "
        #                             "http://mos.rf.gd/index.html - Also check the OP list and avoid those songs: "
        #                             "http://mos.rf.gd/overplayed.html\nVisit us on FB: http://xurl.es/hncih , "
        #                             "next NTT: http://xurl.es/3u71y",
        #           "metaDescription": "MoS, MasterOfSoundtrack, masterofsoundtrack, Master of Soundtrack, "
        #                              "master of soundtrack, scores, soundtrack, movie, film, videogame, "
        #                              "epic music, trailer",
        #           "displayInLobby": True,
        #           "displayInSearch": True,
        #           "limitQueueLength": False,
        #           "timeSongQueueRepeat": 1440,
        #           "recycleDJ": True,
        #           "displayDJinQueue": True,
        #           "displayUserJoin": True,
        #           "displayUserLeave": True,
        #           "displayUserGrab": True,
        #           "maxSongQueueLength": 0,
        #           "roomDisplay": "public",
        #           "waitListRandom": False,
        #           "slowMode": False},
        #  "user": {"_id": "5628db0a3883a45600b7e68f",
        #           "updated": 1519066844284,
        #           "skippedCount": 0,
        #           "playedCount": 1677,
        #           "songsInQueue": 0,
        #           "active": False,
        #           "dubs": 372,
        #           "order": 999999999,
        #           "roomid": "561b1e59c90a9c0e00df610b",
        #           "userid": "560b135c7ae1ea0300869b20",
        #           "_user": "560b135c7ae1ea0300869b20",
        #           "__v": 0,
        #           "ot_token": None,
        #           "authorized": True,
        #           "queuePaused": None,
        #           "waitLine": 0,
        #           "roleid": {"_id": "52d1ce33c38a06510c000001",
        #                      "type": "mod",
        #                      "label": "Moderator",
        #                      "rights": ["skip",
        #                                 "queue-order",
        #                                 "kick",
        #                                 "ban",
        #                                 "mute",
        #                                 "set-dj",
        #                                 "lock-queue",
        #                                 "delete-chat",
        #                                 "chat-mention"],
        #                      "__v": 0}}}

        if not self.room_user_info:
            room_id = await self.get_room_id()
            self.room_user_info = await self.api_post(f'https://api.dubtrack.fm/room/{room_id}/users', None)
        return self.room_user_info['user']['roleid']['type']

    async def say_in_room(self, text):
        # {"message": "pfff",
        #  "type": "chat-message",
        #  "chatid": None,
        #  "user": {"username": "txomon",
        #           "status": 1,
        #           "roleid": 1,
        #           "dubs": 0,
        #           "created": 1443566427591,
        #           "lastLogin": 0,
        #           "userInfo": {"_id": "560b135c7ae1ea0300869b21",
        #                        "userid": "560b135c7ae1ea0300869b20",
        #                        "__v": 0},
        #           "_force_updated": 1519046263690,
        #           "_id": "560b135c7ae1ea0300869b20",
        #           "__v": 0},
        #  "time": 1519047206095,
        #  "realTimeChannel": "dubtrackfm-master-of-soundtrack",
        #  "userRole": "mod"}

        body = {'chatid': None,
                'message': text,
                'time': int(time.time() * 1000),
                'type': 'chat-message',
                'user': self.user_session_info,
                'userRole': await self.get_user_role(), }
        room_id = await self.get_room_id()
        response = await self.aio_session.post(f'https://api.dubtrack.fm/chat/{room_id}', json=body)
        self.suppress_messages.append(text)
        return response

    async def login(self, username, password):
        # No response, just cookie set
        data = {'username': username, 'password': password}
        async with self.aio_session.post('https://api.dubtrack.fm/auth/dubtrack', data=data) as resp:
            return resp.status == 200

    async def get_token(self):
        # {'action': 17,
        #  'clientId': '4d3855621cd95d0d6a363806f712e2d0',
        #  'reqId': 'b5509b95b608cb7609891ef9e162cba3',
        #  'token': 'eyJhbGciOiJ.........HJwQL-7ytGnsXkucV5h_A_pV8V6YsA7DYQgxRpOaQMg'}
        response = await self.api_get('https://api.dubtrack.fm/auth/token')
        return response['token']

    async def get_room_id(self):
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
        if not self.room_info:
            self.room_info = await self.api_get(f'https://api.dubtrack.fm/room/{self.room}')
        return self.room_info['_id']

    async def get_active_song(self):
        # {'song': {'__v': 0,
        #           '_id': '5a8be8a5edab940100b2af20',
        #           '_song': '583198efc2225d2e00849a5b',
        #           '_user': '562e462b888e6f1900ff20bc',
        #           'created': 1519118499376,
        #           'downdubs': 0,
        #           'isActive': True,
        #           'isPlayed': False,
        #           'order': 1,
        #           'played': 1519131687972,
        #           'roomid': '561b1e59c90a9c0e00df610b',
        #           'skipped': False,
        #           'songLength': 307000,
        #           'songid': '583198efc2225d2e00849a5b',
        #           'updubs': 2,
        #           'userid': '562e462b888e6f1900ff20bc'},
        #  'songInfo': {'__v': 0,
        #               '_id': '583198efc2225d2e00849a5b',
        #               'created': '2016-11-20T12:37:03.018Z',
        #               'fkid': 'zoORlnu_6dk',
        #               'images': {'thumbnail': 'https://i.ytimg.com/vi/zoORlnu_6dk/hqdefault.jpg'},
        #               'name': 'Spain Ambient - Guitar Improv 7 (Civilization 6 OST)',
        #               'songLength': 307000,
        #               'type': 'youtube'},
        #  'startTime': 65}

        # or if no one is playing

        # {'err': {'details': {'code': 404,
        #                      'message': 'no songs in active queue'},
        #          'origin': 'method'}}

        room_id = await self.get_room_id()
        playing_song = await self.api_get(f'https://api.dubtrack.fm/room/{room_id}/playlist/active')
        if 'err' in playing_song:
            return None
        return playing_song

    async def get_users(self):
        # [
        #     {"_id": "57f36aff34169c1a0018f92d",
        #      "updated": 1519126214587,
        #      "skippedCount": 0,
        #      "playedCount": 10894,
        #      "songsInQueue": 556,
        #      "active": True,
        #      "dubs": 3542,
        #      "order": 99999,
        #      "roomid": "561b1e59c90a9c0e00df610b",
        #      "userid": "57f36acd6c9b5c5b003d41d2",
        #      "_user": {
        #          "_id": "57f36acd6c9b5c5b003d41d2",
        #          "username": "eberg",
        #          "status": 1,
        #          "roleid": 1,
        #          "dubs": 0,
        #          "created": 1475570381585,
        #          "profileImage": {
        #              "public_id": "user/57f36acd6c9b5c5b003d41d2",
        #              "version": 1476084566, "width": 500, "height": 267, "format": "jpg", "resource_type": "image",
        #              "tags": [], "bytes": 47184, "type": "upload", "etag": "010154daa60a012e27cfc5ef888dae00",
        #              "url": "http://res.cloudinary.com/hhberclba/image/upload/v1476084566/user"
        #                     "/57f36acd6c9b5c5b003d41d2.jpg",
        #              "secure_url": "https://res.cloudinary.com/hhberclba/image/upload/v1476084566/user"
        #                            "/57f36acd6c9b5c5b003d41d2.jpg",
        #              "overwritten": True},
        #          "__v": 0},
        #      "__v": 0,
        #      "authorized": True,
        #      "ot_token": None,
        #      "queuePaused": None,
        #      "waitLine": 0},
        # ]
        room_id = await self.get_room_id()
        return await self.api_get(f'https://api.dubtrack.fm/room/{room_id}/users')

    async def get_user(self, user_id):
        # {'__v': 0,
        #  '_id': '5628edc08d7d6a5600335d3d',
        #  'created': 1445522880666,
        #  'dubs': 0,
        #  'profileImage': {
        #      'bytes': 61889,
        #      'etag': 'f5f398bf49c71314e865ade3c4a7bf2a',
        #      'format': 'jpg',
        #      'height': 455,
        #      'overwritten': True,
        #      'placeholder': False,
        #      'public_id': 'user/5628edc08d7d6a5600335d3d',
        #      'resource_type': 'image',
        #      'secure_url': 'https://res.cloudinary.com/hhberclba/image/upload/v1508887786/user'
        #                    '/5628edc08d7d6a5600335d3d.jpg',
        #      'tags': [],
        #      'type': 'upload',
        #      'url': 'http://res.cloudinary.com/hhberclba/image/upload/v1508887786/user'
        #             '/5628edc08d7d6a5600335d3d.jpg',
        #      'version': 1508887786,
        #      'width': 455
        #  },
        #  'roleid': 1,
        #  'status': 1,
        #  'userInfo': {
        #      '__v': 0,
        #      '_id': '5628edc08d7d6a5600335d3e',
        #      'userid': '5628edc08d7d6a5600335d3d'
        #  },
        #  'username': 'iCel'
        #  }
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
        room_id = await self.get_room_id()
        url = URL(f'https://api.dubtrack.fm/room/{room_id}/playlist/history')
        if page:
            url = url.with_query({'page': page})
        return await self.api_get(str(url))

    async def get_room_playlist(self):
        # {"__v": 0,
        #  "created": 1520158007231,
        #  "isActive": False,
        #  "isPlayed": False,
        #  "skipped": False,
        #  "order": 999,
        #  "roomid": "561b1e59c90a9c0e00df610b",
        #  "songLength": 168000,
        #  "updubs": 0,
        #  "downdubs": 0,
        #  "userid": "560b135c7ae1ea0300869b20",
        #  "songid": "565e8fb8e39987830055f389",
        #  "_user": "560b135c7ae1ea0300869b20",
        #  "_song": "565e8fb8e39987830055f389",
        #  "_id": "5a9bc537b55af20100405d6b"}
        room_id = await self.get_room_id()
        playlist = await self.api_get(f'https://api.dubtrack.fm/room/{room_id}/playlist')
        return playlist

    async def add_song_to_playlist(self, extid, origin='youtube'):
        # {"__v": 0,
        #  "created": 1520158645688,
        #  "isActive": False,
        #  "isPlayed": False,
        #  "skipped": False,
        #  "order": 999,
        #  "roomid": "561b1e59c90a9c0e00df610b",
        #  "songLength": 222000,
        #  "updubs": 0,
        #  "downdubs": 0,
        #  "userid": "560b135c7ae1ea0300869b20",
        #  "songid": "58b6a2126ba2fa18005f3a8e",
        #  "_user": "560b135c7ae1ea0300869b20",
        #  "_song": "58b6a2126ba2fa18005f3a8e",
        #  "_id": "5a9bc7b58befc60100230823"}
        room_id = await self.get_room_id()
        response = self.api_post(f'https://api.dubtrack.fm/room/{room_id}/playlist',
                                 {'songId': extid, 'songType': origin})
        return response

    async def get_room_playlist_details(self):
        # [
        #     {"_id": "5a9bc7ba9d993401003eba43",
        #      "created": 1520158650527,
        #      "isActive": False,
        #      "isPlayed": False,
        #      "skipped": False,
        #      "order": 999,
        #      "roomid": "561b1e59c90a9c0e00df610b",
        #      "songLength": 309000,
        #      "updubs": 0,
        #      "downdubs": 0,
        #      "userid": "560b135c7ae1ea0300869b20",
        #      "songid": "5a9bc7ba9d993401003eba42",
        #      "_user": {"_id": "560b135c7ae1ea0300869b20",
        #                "username": "txomon",
        #                "status": 1,
        #                "roleid": 1,
        #                "dubs": 0,
        #                "created": 1443566427591,
        #                "profileImage": {"public_id": "user/560b135c7ae1ea0300869b20",
        #                                 "version": 1486657178,
        #                                 "width": 245,
        #                                 "height": 245,
        #                                 "format": "gif",
        #                                 "resource_type": "image",
        #                                 "tags": [],
        #                                 "pages": 22,
        #                                 "bytes": 444903,
        #                                 "type": "upload",
        #                                 "etag": "09da0f0c34e6ddf6eb75516ea66e17bc",
        #                                 "url":
        #                                     "http://res.cloudinary.com/hhberclba/image/upload/v1486657178/user"
        #                                     "/560b135c7ae1ea0300869b20.gif",
        #                                 "secure_url":
        #                                     "https://res.cloudinary.com/hhberclba/image/upload/v1486657178/user"
        #                                     "/560b135c7ae1ea0300869b20.gif",
        #                                 "overwritten": True},
        #                "__v": 0},
        #      "_song": {"_id": "5a9bc7ba9d993401003eba42",
        #                "name": "Chu Ishikawa - Megatron (Clean Version)",
        #                "images": {"thumbnail": "https://i.ytimg.com/vi/Nku49pPj0kU/hqdefault.jpg"},
        #                "type": "youtube",
        #                "songLength": 309000,
        #                "fkid": "Nku49pPj0kU",
        #                "__v": 0,
        #                "created": "2018-03-04T10:17:30.329Z"},
        #      "__v": 0}]
        room_id = await self.get_room_id()
        response = self.api_get(f'https://api.dubtrack.fm/room/{room_id}/playlist/details')
        return response

    async def delete_track_in_queue(self, user_id):
        # {"userNextSong": {
        #     "_id": "5a9bce0357faec01003e0c03",
        #     "created": 1520160259582,
        #     "isActive": False,
        #     "isPlayed": False,
        #     "skipped": False,
        #     "order": 999,
        #     "roomid": "561b1e59c90a9c0e00df610b",
        #     "songLength": 246000,
        #     "updubs": 0,
        #     "downdubs": 0,
        #     "userid": "560b135c7ae1ea0300869b20",
        #     "songid": "560895658e9cb60300550def",
        #     "_user": {
        #         "_id": "560b135c7ae1ea0300869b20",
        #         "username": "txomon",
        #         "status": 1,
        #         "roleid": 1,
        #         "dubs": 0,
        #         "created": 1443566427591,
        #         "profileImage": {
        #             "public_id": "user/560b135c7ae1ea0300869b20",
        #             "version": 1486657178,
        #             "width": 245,
        #             "height": 245,
        #             "format": "gif",
        #             "resource_type": "image",
        #             "tags": [],
        #             "pages": 22,
        #             "bytes": 444903,
        #             "type": "upload",
        #             "etag": "09da0f0c34e6ddf6eb75516ea66e17bc",
        #             "url":
        #                 "http://res.cloudinary.com/hhberclba/image/upload/v1486657178/user"
        #                 "/560b135c7ae1ea0300869b20.gif",
        #             "secure_url":
        #                 "https://res.cloudinary.com/hhberclba/image/upload/v1486657178/user"
        #                 "/560b135c7ae1ea0300869b20.gif",
        #             "overwritten": True},
        #         "__v": 0},
        #     "_song": {
        #         "_id": "560895658e9cb60300550def",
        #         "name": "Back To The Future - The Power Of Love",
        #         "images": {
        #             "thumbnail": "https://i.ytimg.com/vi/-NMph943tsw/hqdefault.jpg",
        #             "youtube": {"default": {
        #                 "url": "https://i.ytimg.com/vi/-NMph943tsw/default.jpg",
        #                 "width": 120,
        #                 "height": 90},
        #                 "medium": {
        #                     "url": "https://i.ytimg.com/vi/-NMph943tsw/mqdefault.jpg",
        #                     "width": 320,
        #                     "height": 180},
        #                 "high": {
        #                     "url": "https://i.ytimg.com/vi/-NMph943tsw/hqdefault.jpg",
        #                     "width": 480,
        #                     "height": 360},
        #                 "standard": {
        #                     "url": "https://i.ytimg.com/vi/-NMph943tsw/sddefault.jpg",
        #                     "width": 640,
        #                     "height": 480}}},
        #         "type": "youtube",
        #         "fkid": "-NMph943tsw",
        #         "streamUrl": None,
        #         "songLength": 246000,
        #         "__v": 0,
        #         "created": "2015-09-28T01:18:29.979Z"},
        #     "__v": 0}}

        # or if no next song in user's queue

        # {"userNextSong": None}

        room_id = await self.get_room_id()
        url = f'https://api.dubtrack.fm/room/{room_id}/queue/user/{user_id}'
        async with self.aio_session.delete(url) as resp:
            logger.debug(f'Request: {url}')
            response = await resp.json()
            logger.debug(f'Response: {pprint.pformat(response)}')
        return response['data']

    async def raw_ws_consume(self):
        last_token_fail = last_consume_fail = 0
        while True:  # two tries per level
            try:
                token = await self.get_token()
            except Exception:
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
                except Exception:
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
        room_id = await self.get_room_id()
        subscription = {
            'action': 10,
            "channel": f'room:{room_id}',
        }
        await self.ws_send(f'4{json.dumps(subscription)}')

    async def send_presence_update(self):
        room_id = await self.get_room_id()
        presence_update = {
            "action": 14,
            "channel": f'room:{room_id}',
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
                msg = content["message"]
                logger_layer3.debug(
                    f'Chat {username}#{userid} (chatid#{chatid}): {msg}')
                if msg in self.suppress_messages:
                    self.suppress_messages.remove(msg)
                    logger_layer3.debug(f'Suppressing message: {msg}')
                    continue
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
                #  'type': 'room_playlist-dub',
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
                dubtype = content['dubtype']
                username = content['user']['username']
                userid = content['user']['userInfo']['userid']
                downdubs = content['playlist']['downdubs']
                updubs = content['playlist']['updubs']
                logger_layer3.debug(
                    f"Song {dubtype} by {username}#{userid}, total {updubs}U/{downdubs}D")
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
                logger_layer3.debug(
                    f'User {username}/{userid} changed personal queue')
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
                logger_layer3.debug(f'User {username}#{userid} joined')
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
                # 'user_queue': {'__v': 0,
                #                '_id': '5628ededa2d0f81300edc39a',
                #                '_user': '5628edc08d7d6a5600335d3d',
                #                'active': True,
                #                'authorized': True,
                #                'dubs': 25899,
                #                'order': 99999,
                #                'ot_token': None,
                #                'playedCount': 23897,
                #                'queuePaused': None,
                #                'roleid': '5615fa9ae596154a5c000000',
                #                'roomid': '561b1e59c90a9c0e00df610b',
                #                'skippedCount': 0,
                #                'songsInQueue': 31,
                #                'updated': 1518783663567,
                #                'userid': '5628edc08d7d6a5600335d3d',
                #                'waitLine': 0}}

                # OR

                # {'type': 'user-pause-queue',
                #  'user': {'__v': 0,
                #           '_id': '560b135c7ae1ea0300869b20',
                #           'created': 1443566427591,
                #           'dubs': 0,
                #           'profileImage': {'bytes': 444903,
                #                            'etag': '09da0f0c34e6ddf6eb75516ea66e17bc',
                #                            'format': 'gif',
                #                            'height': 245,
                #                            'overwritten': True,
                #                            'pages': 22,
                #                            'public_id': 'user/560b135c7ae1ea0300869b20',
                #                            'resource_type': 'image',
                #                            'secure_url':
                # 'https://res.cloudinary.com/hhberclba/image/upload/v1486657178/user/560b135c7ae1ea0300869b20.gif',
                #                            'tags': [],
                #                            'type': 'upload',
                #                            'url':
                # 'http://res.cloudinary.com/hhberclba/image/upload/v1486657178/user/560b135c7ae1ea0300869b20.gif',
                #                            'version': 1486657178,
                #                            'width': 245},
                #           'roleid': 1,
                #           'status': 1,
                #           'username': 'txomon'},
                #  'user_queue': {'__v': 0,
                #                 '_id': '5628db0a3883a45600b7e68f',
                #                 '_user': '560b135c7ae1ea0300869b20',
                #                 'active': True,
                #                 'authorized': True,
                #                 'dubs': 376,
                #                 'order': 99999,
                #                 'ot_token': None,
                #                 'playedCount': 1680,
                #                 'queuePaused': None,
                #                 'roleid': '52d1ce33c38a06510c000001',
                #                 'roomid': '561b1e59c90a9c0e00df610b',
                #                 'skippedCount': 0,
                #                 'songsInQueue': 0,
                #                 'updated': 1519080836290,
                #                 'userid': '560b135c7ae1ea0300869b20',
                #                 'waitLine': 0}}

                # TODO: Correct for both posibilities
                username = content['user']['username']
                userid = content['user'].get('userInfo', {}).get('userid')
                userid = userid or content['user']['_id']

                logger_layer3.debug(f'User {username}#{userid} stopped playlist')
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
                    f'User {modname}#{modid} removed from role {role}/{roletype}({", ".join(rights)}) by {username}#'
                    f'{userid}')
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
            else:
                logger_layer3.info(
                    f'Received unknown message {content_type}: {pprint.pformat(content)}')
            yield content

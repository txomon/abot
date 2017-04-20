# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import json
import logging
from typing import List

import aiohttp
from aiohttp import WSMsgType
from aiohttp.formdata import FormData
from multidict import MultiDict

logger = logging.getLogger(__name__)


class SlackException(Exception):
    pass


class SlackCallException(SlackException):
    def __init__(self, message, method):
        self.method = method
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f'Slack call {self.method}. {self.message}'


class SlackUseException(SlackException):
    pass


class SlackAPI:
    SLACK_RPC_PREFIX = 'https://slack.com/api/'
    SLACK_RTM_EVENTS = (
        'accounts_changed', 'bot_added', 'bot_changed', 'channel_archive', 'channel_created', 'channel_deleted',
        'channel_history_changed', 'channel_joined', 'channel_left', 'channel_marked', 'channel_rename',
        'channel_unarchive', 'commands_changed', 'dnd_updated', 'dnd_updated_user', 'email_domain_changed',
        'emoji_changed', 'file_change', 'file_comment_added', 'file_comment_deleted', 'file_comment_edited',
        'file_created', 'file_deleted', 'file_public', 'file_shared', 'file_unshared', 'goodbye', 'group_archive',
        'group_close', 'group_history_changed', 'group_joined', 'group_left', 'group_marked', 'group_open',
        'group_rename', 'group_unarchive', 'hello', 'im_close', 'im_created', 'im_history_changed', 'im_marked',
        'im_open', 'link_shared', 'manual_presence_change', 'message', 'message.channels', 'message.groups',
        'message.im', 'message.mpim', 'pin_added', 'pin_removed', 'pref_change', 'presence_change', 'reaction_added',
        'reaction_removed', 'reconnect_url', 'star_added', 'star_removed', 'subteam_created', 'subteam_self_added',
        'subteam_self_removed', 'subteam_updated', 'team_domain_change', 'team_join', 'team_migration_started',
        'team_plan_change', 'team_pref_change', 'team_profile_change', 'team_profile_delete', 'team_profile_reorder',
        'team_rename', 'url_verification', 'user_change', 'user_typing',)

    def __init__(self, bot_token, event_loop=None):
        self.loop = event_loop or asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.bot_token = bot_token
        self.users = []
        self.channels = []
        self.mpims = []
        self.ims = []
        self.bots = []
        self.ws_socket = None
        self.ws_ids = 1
        self.response_futures = {}

    async def request(self, method, url, data=None, headers=None):
        async with self.session.request(method=method, url=url, data=data, headers=headers) as response:
            return await response.json()

    async def call(self, method, **params):
        """
        Call an Slack Web API method

        :param method: Slack Web API method to call
        :param params: {str: object} parameters to method
        :return: dict()
        """
        url = self.SLACK_RPC_PREFIX + method
        data = FormData()
        data.add_fields(MultiDict(token=self.bot_token, charset='utf-8', **params))
        response_body = await self.request(
            method='POST',
            url=url,
            data=data
        )
        if 'warning' in response_body:
            logger.warning(f'Warnings received from API call {method}: {response_body["warning"]}')
        if 'ok' not in response_body:
            logger.error(f'No ok marker in slack API call {method} {params} => {response_body}')
            raise SlackCallException('There is no ok marker, ... strange', method=method)
        if not response_body['ok']:
            logger.error(f'Slack API call failed {method} {params} => {response_body}')
            raise SlackCallException(f'No OK response returned', method=method)
        return response_body

    def slack_name_to_id(self, recipient):
        if recipient.startswith('@'):
            username = recipient[1:]
            users = [user for user in self.users if user['names'] == username and not user['deleted']]
            if len(users) > 1 or not users:
                logger.error(f'User {username} does not exist')
                raise SlackUseException(f'User {recipient} does not exist')
            return users[0]['id']
        if recipient.startswith('#'):
            channel_name = recipient[1:]
            channels = [channel for channel in self.channels if
                        channel['names'] == channel_name and not channel['archived']]
            if len(channels) > 1 or not channels:
                logger.error(f'Channel {channel_name} does not exist')
                raise SlackUseException(f'Channel {channel_name} does not exist')
            return channels[0]['id']
        return recipient

    def userids_to_channel(self, userids):
        userids.sort()
        for mpim in self.mpims:
            if sorted(mpim['members']) == userids:
                return mpim['id']
        raise SlackUseException(f'Channel with only {userids} does not exist')

    def ws_send(self, body: dict):
        assert self.ws_socket and not self.ws_socket.closed, 'Writing to someone is only supported through ws'
        body['id'] = self.ws_ids
        self.ws_ids += 1
        logger.debug(f'Sending {body}')
        self.ws_socket.send_json(body)
        future = self.response_futures[body['id']] = asyncio.Future()
        return future

    def write_to(self, recipients: List[str] or str, message: str):
        if not isinstance(recipients, str) and len(recipients) > 1:
            recipients_ids = [self.slack_name_to_id(recipient=recipient) for recipient in recipients]
            recipient = self.userids_to_channel(userids=recipients_ids)
        else:
            recipient = recipients
        if recipient[0] in '@#':  # User cannot be addressed directly, need to do it through DM channel
            recipient = self.slack_name_to_id(recipient=recipient)
        assert recipient[0] in 'CDG'
        return self.ws_send({
            'type': 'message',
            'channel': recipient,
            'text': message,
        })

    def look_for_id(self, iterable, object_id):
        for item in iterable:
            if item['id'] == object_id:
                break
        else:
            item = None
        return item

    def handle_bot_added(self, message):
        bot_id = message['bot']['id']
        bot = self.look_for_id(self.bots, bot_id)
        if bot:
            logger.warning(f'Bot {bot_id} is to be added, but already exists, updating')
            bot.update(message['bot'])
        else:
            logger.debug(f'Adding bot {bot_id}')
            bot = {'deleted': False, 'updated': 0}
            bot.update(message['bot'])
            self.bots.append(bot)
        return message

    def handle_bot_changed(self, message):
        bot_id = message['bot']['id']
        bot = self.look_for_id(self.bots, bot_id)

        if bot:
            logger.debug(f'Bot {bot_id} changed')
            bot.update(message['bot'])
        else:
            logger.warning(f'Bot {bot_id} is to be changed, but does not exist, adding')
            bot = {'deleted': False, 'updated': 0}
            bot.update(message['bot'])
            self.bots.append(bot)
        return message

    def handle_channel_archive(self, message):
        channel_id = message['channel']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.debug(f'Bot {channel_id} has been archived. {message}')
            channel['is_archived'] = True
        else:
            logger.warning(f'Channel {channel_id} is not in the list of known channels, adding')
            self.channels.append({'id': channel_id, 'is_archived': True, "is_channel": True, })
        return message

    def handle_channel_created(self, message):
        channel_id = message['channel']['id']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.warning(f'Channel {channel_id} already exists, updating')
            channel.update(message['channel'])
        else:
            logger.debug(f'Channel {channel_id} has been created. {message["channel"]}')
            self.channels.append(dict(is_archived=False, is_channel=True, **message['channel']))
        return message

    def handle_channel_deleted(self, message):
        channel_id = message['channel']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.warning(f'Channel {channel_id} already exists, updating')
            channel.update(message['channel'])
        else:
            logger.debug(f'Channel {channel_id} has been created. {message["channel"]}')
            self.channels.append(dict(is_archived=False, is_channel=True, **message['channel']))
        return message

    def handle_channel_history_changed(self, message):
        logger.debug(f'Channel history changed. Doing nothing')
        return message

    def handle_channel_joined(self, message):
        channel_id = message['channel']['id']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.debug(f'Channel {channel_id} joined')
            channel.update(message['channel'])
        else:
            logger.warning(f'Joined previously unknown channel {channel_id}')
            self.channels.append(message['channel'])
        return message

    def handle_channel_left(self, message):
        channel_id = message['channel']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.debug(f'Left channel {channel_id}')
            channel['is_member'] = False
        else:
            logger.warning(f'Left previously unknown channel {channel_id}')
            self.channels.append(dict(id=channel_id, is_channel=True, ))
        return message

    def handle_channel_marked(self, message):
        channel_id = message['channel']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.debug(f'Channel mark event for {channel_id}, doing nothing')
        else:
            logger.warning(f'Mark on previously unknown channel {channel_id}')
            self.channels.append(dict(id=channel_id, is_channel=True, ))
        return message

    def handle_channel_rename(self, message):
        channel_id = message['channel']['id']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.debug(f'Channel {channel_id} renamed')
            channel.update(message['channel'])
        else:
            logger.warning(f'Rename of previously unknown channel {channel_id}')
            self.channels.append(dict(is_channel=True, **message['channel']))
        return message

    def handle_hello(self, message):
        logger.info('Correctly connected to RTM stream')
        return message

    def handle_presence_change(self, message):
        user_id = message['user']
        user = self.look_for_id(self.users, user_id)
        presence = message["presence"]
        if user:
            logger.debug(f'User {user_id} presence updated to {presence}')
            user['presence'] = presence
        else:
            logger.warning(f'Setting presence for previously unknown user {user_id}')
            self.users.append(dict(id=user_id, presence=presence))
        return message

    def handle_reconnect_url(self, message):
        logger.debug('Slack says that reconnect_url is experimental, doing nothing')
        return None

    def rtm_handler(self, ws_message):
        """
        Handle a message, processing it internally if required. If it's a message that should go outside the bot,
        this function will return True

        :param message:
        :return: Boolean if message should be yielded
        """
        message = json.loads(ws_message.data)
        if 'reply_to' in message:
            reply_to = message['reply_to']
            future = self.response_futures.pop(reply_to, None)
            if future is None:
                logger.error(f'This should not happen, received reply to unknown message! {message}')
                return None
            future.set_result(message)
            return None
        if 'type' not in message:
            logger.error(f'No idea what this could be {message}')
            return
        message_type = message['type']

        if hasattr(self, f'handle_{message_type}'):
            function = getattr(self, f'handle_{message_type}')
            return function(message)

        if message_type in self.SLACK_RTM_EVENTS:
            logger.debug(f'Received {message_type} but unhandled. {message}')
        else:
            logger.warning(f'Event {message_type} does not exist. {message}')
        return message

    async def rtm_api_consume(self):
        response = await self.call('rtm.start', simple_latest=False, no_unreads=False, mpim_aware=True)
        self.channels = response['channels']
        self.ims = response['ims']
        self.mpims = response['mpims']
        self.users = response['users']
        self.bots = response['bots']
        async with self.session.ws_connect(url=response['url']) as self.ws_socket:
            async for ws_message in self.ws_socket:
                if ws_message.tp == WSMsgType.text:
                    message_content = self.rtm_handler(ws_message=ws_message)
                    if message_content:
                        yield message_content
                elif ws_message.tp in (WSMsgType.closed, WSMsgType.error):
                    logger.info('Finishing ws, %s', ws_message)
                    if not self.ws_socket.closed:
                        await self.ws_socket.close()
                    break

    def __del__(self):
        asyncio.ensure_future(self.session.close(), loop=self.loop)


for method in dir(SlackAPI):
    if method.startswith('handle_'):
        handle, event_name = method.split('_', 1)
        assert event_name in SlackAPI.SLACK_RTM_EVENTS, f'SlackAPI defines unregistered handler {method}'

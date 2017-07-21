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
        'im_open', 'manual_presence_change', 'member_joined_channel', 'member_left_channel', 'message', 'pin_added',
        'pin_removed', 'pref_change', 'presence_change', 'reaction_added', 'reaction_removed', 'reconnect_url',
        'star_added', 'star_removed', 'subteam_created', 'subteam_self_added', 'subteam_self_removed',
        'subteam_updated', 'team_domain_change', 'team_join', 'team_migration_started', 'team_plan_change',
        'team_pref_change', 'team_profile_change', 'team_profile_delete', 'team_profile_reorder', 'team_rename',
        'user_change', 'user_typing',
    )
    SLACK_EVENTS_API_EVENTS = (
        'app_uninstalled', 'channel_archive', 'channel_created', 'channel_deleted', 'channel_history_changed',
        'channel_rename', 'channel_unarchive', 'dnd_updated', 'dnd_updated_user', 'email_domain_changed',
        'emoji_changed', 'file_change', 'file_comment_added', 'file_comment_deleted', 'file_comment_edited',
        'file_created', 'file_deleted', 'file_public', 'file_shared', 'file_unshared', 'grid_migration_finished',
        'grid_migration_started', 'group_archive', 'group_close', 'group_history_changed', 'group_open',
        'group_rename', 'group_unarchive', 'im_close', 'im_created', 'im_history_changed', 'im_open', 'link_shared',
        'member_joined_channel', 'member_left_channel', 'message', 'message.channels', 'message.groups', 'message.im',
        'message.mpim', 'pin_added', 'pin_removed', 'reaction_added', 'reaction_removed', 'star_added', 'star_removed',
        'subteam_created', 'subteam_members_changed', 'subteam_self_added', 'subteam_self_removed', 'subteam_updated',
        'team_domain_change', 'team_join', 'team_rename', 'tokens_revoked', 'url_verification', 'user_change'
    )

    def __init__(self, bot_token, event_loop=None):
        self.loop = event_loop or asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.bot_token = bot_token
        self.groups = []
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

    async def slack_name_to_id(self, recipient):
        new_id = recipient
        if recipient.startswith('@'):
            username = recipient[1:]
            users = [user for user in self.users if user['bot_names'] == username and not user['deleted']]
            if len(users) > 1 or not users:
                logger.error(f'User {username} does not exist')
                raise SlackUseException(f'User {recipient} does not exist')
            new_id = users[0]['id']
        if recipient.startswith('#'):
            channel_name = recipient[1:]
            channels = [channel for channel in self.channels if
                        channel['bot_names'] == channel_name and not channel['archived']]
            if len(channels) > 1 or not channels:
                logger.error(f'Channel {channel_name} does not exist')
                raise SlackUseException(f'Channel {channel_name} does not exist')
            new_id = channels[0]['id']
        if new_id.startswith('U'):
            for im in self.ims:
                if im['user'] == new_id:
                    new_id = im['id']
                    break
            else:
                channel = await self.create_im(new_id)
                new_id = channel['channel']['id']
        return new_id

    async def userids_to_channel(self, userids):
        userids.sort()
        for mpim in self.mpims:
            if sorted(mpim['members']) == userids:
                return mpim['id']
        else:
            mpim = await self.create_mpim(users=userids)
            return mpim['id']

    def ws_send(self, body: dict):
        assert self.ws_socket and not self.ws_socket.closed, 'Writing to someone is only supported through ws'
        body['id'] = self.ws_ids
        self.ws_ids += 1
        logger.debug(f'Sending {body}')
        self.ws_socket.send_json(body)
        future = self.response_futures[body['id']] = asyncio.Future()
        return future

    async def write_to(self, recipients: List[str] or str, message: str):
        if not isinstance(recipients, str) and len(recipients) > 1:
            recipients_ids = await asyncio.gather(
                self.slack_name_to_id(recipient=recipient) for recipient in recipients
            )
            recipient = await self.userids_to_channel(userids=recipients_ids)
        else:
            recipient = recipients
        if recipient[0] in '@#U':  # User cannot be addressed directly, need to do it through DM channel
            recipient = await self.slack_name_to_id(recipient=recipient)
        assert recipient[0] in 'CDG', f'Programming error, receiver should start with (C|D|G) ({recipient}'
        return self.ws_send({
            'type': 'message',
            'channel': recipient,
            'text': message,
        })

    async def create_im(self, user: str):
        channel = await self.call('im.open', user=user, return_im=True)
        return channel

    async def create_mpim(self, users: List[str]):
        channel = await self.call('mpim.open', users=users)
        return channel

    def look_for_id(self, iterable, object_id):
        for item in iterable:
            if item['id'] == object_id:
                break
        else:
            item = None
        return item

    def ignore_message(self, message):
        logger.debug(f'Ignoring {message["type"]} message. {message}')
        return message

    def get_user_by_id(self, user_id):
        return self.look_for_id(self.users, user_id)

    handle_accounts_changed = ignore_message

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
            logger.debug(f'Channel {channel_id} has been archived. {message}')
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

    handle_channel_history_changed = ignore_message

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

    def handle_channel_unarchive(self, message):
        channel_id = message['channel']
        channel = self.look_for_id(self.channels, channel_id)
        if channel:
            logger.debug(f'Channel {channel_id} has been unarchived. {message}')
            channel['is_archived'] = False
        else:
            logger.warning(f'Channel {channel_id} is not in the list of known channels, unarchiving')
            self.channels.append({'id': channel_id, 'is_archived': False, "is_channel": True, })
        return message

    handle_commands_changed = ignore_message
    handle_dnd_updated = ignore_message
    handle_dnd_updated_user = ignore_message
    handle_email_domain_changed = ignore_message
    handle_emoji_changed = ignore_message
    handle_file_change = ignore_message
    handle_file_comment_added = ignore_message
    handle_file_comment_deleted = ignore_message
    handle_file_comment_edited = ignore_message
    handle_file_created = ignore_message
    handle_file_deleted = ignore_message
    handle_file_public = ignore_message
    handle_file_shared = ignore_message
    handle_file_unshared = ignore_message
    handle_goodbye = ignore_message  # TODO: Needs to be handled
    handle_grid_migration_finished = ignore_message
    handle_grid_migration_started = ignore_message

    def handle_group_archive(self, message):
        group_id = message['channel']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.debug(f'Group {group_id} has been archived. {message}')
            group['is_archived'] = True
        else:
            logger.warning(f'Group {group_id} is not in the list of known groups, archiving')
            self.channels.append({'id': group_id, 'is_archived': True, "is_group": True, })
        return message

    def handle_group_close(self, message):
        group_id = message['channel']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.debug(f'Marking group {group_id} as closed. {message}')
            group['is_open'] = False
        else:
            logger.warning(f'Marking non existent group as closed. {message}')
            self.groups.append({'is_group': True, 'id': group_id, 'is_open': False})
        return message

    handle_group_history_changed = ignore_message

    def handle_group_joined(self, message):
        group_id = message['channel']['id']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.warning(f'Creating already existing group {group_id}. {message}')
            group.update(message['channel'])
        else:
            logger.debug(f'Joined group {group_id}. {message}')
            self.groups.append(message['channel'])
        return message

    def handle_group_left(self, message):
        group_id = message['channel']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.debug(f'Left group {group_id}')
            group['is_member'] = False
        else:
            logger.warning(f'Left previously unknown group {group_id}')
            self.groups.append(dict(id=group_id, is_group=True, ))
        return message

    def handle_group_marked(self, message):
        group_id = message['channel']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.debug(f'Channel mark event for {group_id}, doing nothing')
        else:
            logger.warning(f'Mark on previously unknown group {group_id}')
            self.groups.append(dict(id=group_id, is_group=True, ))
        return message

    def handle_group_open(self, message):
        group_id = message['channel']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.debug(f'Group {group_id} open')
            group['is_open'] = True
        else:
            logger.warning(f'Open previously unknown group {group_id}')
            self.groups.append(dict(id=group_id, is_group=True, is_open=True))
        return message

    def handle_group_rename(self, message):
        group_id = message['channel']['id']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.debug(f'Group {group_id} rename')
            group['name'] = message['channel']['name']
        else:
            logger.warning(f'Rename previously unknown group {group_id}')
            self.groups.append(dict(id=group_id, is_group=True, name=message['channel']['name']))
        return message

    def handle_group_unarchive(self, message):
        group_id = message['channel']['id']
        group = self.look_for_id(self.groups, group_id)
        if group:
            logger.debug(f'Marking group {group_id} unarchived')
            group['is_archived'] = False
        else:
            logger.warning(f'Unarchiving previously unknown group {group_id}')
            self.groups.append(dict(id=group_id, is_group=True, is_archived=False))
        return message

    def handle_hello(self, message):
        logger.info('Correctly connected to RTM stream')
        return message

    def handle_im_close(self, message):
        im_id = message['channel']
        im = self.look_for_id(self.ims, im_id)
        if im:
            logger.debug(f'Marking im {im_id} as closed. {message}')
            im['is_open'] = False
        else:
            logger.warning(f'Marking non existent im as closed. {message}')
            self.ims.append({'is_im': True, 'id': im_id, 'is_open': False})
        return message

    def handle_im_created(self, message):
        im_id = message['channel']['id']
        im = self.look_for_id(self.ims, im_id)
        if im:
            logger.warning(f'Channel {im_id} already exists, updating')
            im.update(message['im'])
        else:
            logger.debug(f'Channel {im_id} has been created. {message}')
            self.ims.append(dict(is_archived=False, is_im=True, **message['channel']))
        return message

    handle_im_history_changed = ignore_message
    handle_im_marked = ignore_message

    def handle_im_open(self, message):
        im_id = message['channel']
        im = self.look_for_id(self.ims, im_id)
        if im:
            logger.debug(f'Marking im {im_id} as closed. {message}')
            im['is_open'] = True
        else:
            logger.warning(f'Marking non existent im as closed. {message}')
            self.ims.append({'is_im': True, 'id': im_id, 'is_open': True})
        return message

    def handle_manual_presence_change(self, message):
        user_id = message['user']
        user = self.look_for_id(self.users, user_id)
        presence = message["presence"]
        if user:
            logger.debug(f'User {user_id} presence manually updated to {presence}')
            user['presence'] = presence
        else:
            logger.warning(f'Setting presence for previously unknown user {user_id}')
            self.users.append(dict(id=user_id, presence=presence))
        return message

    def handle_member_joined_channel(self, message):
        channel_id, channel_type = message['channel'], message['channel_type']
        if channel_type == 'C':
            channel = self.look_for_id(self.channels, channel_id)
        elif channel_type == 'G':
            channel = self.look_for_id(self.groups, channel_id)
        else:
            logger.warning(f'Unknown type of channel type {channel_type}, ignoring')
            return message

        user = message['user']
        if channel:
            if 'members' not in channel:
                logger.debug(f'No previously gathered members for channel {channel_id}, adding {user}')
                channel['members'] = [user]
            elif user not in channel['members']:
                logger.debug(f'Adding {user} to members')
                channel['members'].append(user)
            else:
                logger.warning(f'User {user} is already part of the members of {channel_id}')
        else:
            logger.warning(f'Adding previously unknown channel/group {channel_id} the member {user}')
            if channel_type == 'C':
                self.channels.append({'id': channel_id, 'is_channel': True, 'members': [user]})
            elif channel_type == 'G':
                self.groups.append({'id': channel_id, 'is_group': True, 'members': [user]})

        return message

    def handle_member_left_channel(self, message):
        channel_id, channel_type = message['channel'], message['channel_type']
        if channel_type == 'C':
            channel = self.look_for_id(self.channels, channel_id)
        elif channel_type == 'G':
            channel = self.look_for_id(self.groups, channel_id)
        else:
            logger.warning(f'Unknown type of channel type {channel_type}, ignoring')
            return message

        user = message['user']
        if channel:
            if 'members' not in channel:
                logger.debug(f'No previously gathered members for channel {channel_id}, creating empty (no {user})')
                channel['members'] = []
            elif user in channel['members']:
                logger.debug(f'Adding {user} to members')
                channel['members'].remove(user)
            else:
                logger.warning(f'User {user} is already not part of the members of {channel_id}')
        else:
            logger.warning(f'Adding previously unknown channel/group {channel_id} with empty members (no {user})')
            if channel_type == 'C':
                self.channels.append({'id': channel_id, 'is_channel': True, 'members': []})
            elif channel_type == 'G':
                self.groups.append({'id': channel_id, 'is_group': True, 'members': []})

        return message

    handle_pin_added = ignore_message
    handle_pin_removed = ignore_message
    handle_pref_change = ignore_message

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

    handle_reaction_added = ignore_message
    handle_reaction_removed = ignore_message
    handle_reconnect_url = ignore_message
    handle_star_added = ignore_message
    handle_star_removed = ignore_message
    handle_subteam_created = ignore_message
    handle_subteam_members_changed = ignore_message
    handle_subteam_self_added = ignore_message
    handle_subteam_self_removed = ignore_message
    handle_subteam_updated = ignore_message
    handle_team_domain_change = ignore_message

    def handle_team_join(self, message):
        user_id = message['user']['id']
        user = self.look_for_id(self.users, user_id)

        if user:
            logger.warning(f'User {user} that was just created already existed. {message}')
            user.update(message['user'])
        else:
            logger.debug(f'Adding user {user_id} changed. {message}')
            self.users.append(message['user'])
        return message

    handle_team_migration_started = ignore_message
    handle_team_plan_change = ignore_message
    handle_team_pref_change = ignore_message
    handle_team_profile_change = ignore_message
    handle_team_profile_delete = ignore_message
    handle_team_profile_reorder = ignore_message
    handle_team_rename = ignore_message

    def handle_user_change(self, message):
        user_id = message['user']['id']
        user = self.look_for_id(self.users, user_id)

        if user:
            logger.debug(f'User {user} updated. {message}')
            user.update(message['user'])
        else:
            logger.warning(f'Previously non existent user {user_id} changed. {message}')
            self.users.append(message['user'])
        return message

    handle_user_typing = ignore_message

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
            logger.debug(f'Unhandled {message_type}. {message}')
        else:
            logger.warning(f'Unknown {message_type}. {message}')
        return message

    async def rtm_api_consume(self):
        response = await self.call('rtm.start', simple_latest=False, no_unreads=False, mpim_aware=True)
        self.channels = response['channels']
        self.groups = response['groups']
        self.ims = response['ims']
        self.mpims = response['mpims']
        self.users = response['users']
        self.bots = response['bots']
        logger.debug(f'Connect url {response["url"]}')
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
        self.session.close()


for method in dir(SlackAPI):
    all_events = set()
    all_events.update(set(SlackAPI.SLACK_RTM_EVENTS))
    all_events.update(set(SlackAPI.SLACK_EVENTS_API_EVENTS))
    if method.startswith('handle_'):
        handle, event_name = method.split('_', 1)
        assert event_name in all_events, f'SlackAPI defines unregistered handler {method}'

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

    def __init__(self, bot_token, event_loop=None):
        self.loop = event_loop or asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.bot_token = bot_token
        self.users = []
        self.channels = []
        self.
        self.ws_socket = None

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
        if recipient.startswith('@'):
            username = recipient[1:]
            users = [user for user in self.users if user['name'] == username and not user['deleted']]
            if len(users) > 1 or not users:
                logger.error(f'User {username} does not exist')
                raise SlackUseException(f'User {recipient} does not exist')
            return users[0]['id']
        if recipient.startswith('#'):
            channel_name = recipient[1:]
            channels = [channel for channel in self.channels if
                        channel['name'] == channel_name and not channel['archived']]
            if len(channels) > 1 or not channels:
                logger.error(f'Channel {channel_name} does not exist')
                raise SlackUseException(f'Channel {channel_name} does not exist')
            return channels[0]['id']
        return recipient

    async def userids_to_channel(self, userids):
        for user_id in userids:
            pass

    async def write_to(self, recipients: List(str) or str, message: str):
        if len(recipients) > 1:
            recipients_ids = []
            for recipient in recipients:
                recipients_ids.append(self.slack_name_to_id(recipient=recipient))
            recipients_ids.sort()
        else:
            recipient = recipients[0]
        if recipient.startswith('U'):  # User cannot be addressed directly, need to do it through DM channel
            pass

    async def rtm_api_consume(self):
        response = await self.call('rtm.start', simple_latest=False, no_unreads=False, mpim_aware=True)
        async with self.session.ws_connect(url=response['url']) as self.ws_socket:
            async for message in self.ws_socket:
                if message.tp == WSMsgType.text:
                    logger.debug('Received %s', message)
                    yield json.loads(message)
                elif message.tp in (WSMsgType.closed, WSMsgType.error):
                    logger.debug('Finishing ws, %s', message)
                    if not self.ws_socket.closed:
                        await self.ws_socket.close()
                    break

    def __del__(self):
        asyncio.ensure_future(self.session.close(), loop=self.loop)

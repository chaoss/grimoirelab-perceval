# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import json
import logging

from grimoirelab_toolkit.datetime import datetime_to_utc, datetime_utcnow
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...errors import BaseError
from ...utils import DEFAULT_DATETIME

CATEGORY_MESSAGE = "message"

SLACK_URL = 'https://slack.com/'
MAX_ITEMS = 1000
FLOAT_FORMAT = '{:.6f}'

logger = logging.getLogger(__name__)


class Slack(Backend):
    """Slack backend.

    This class retrieves the messages sent to a Slack channel.
    To access the server an API token is required, which must
    have enough permissions to read from the given channel.

    The origin of the data will be set to the `SLACK_URL` plus the
    identifier of the channel; i.e 'https://slack.com/C01234ABC'.

    :param channel: identifier of the channel where data will be fetched
    :param api_token: token or key needed to use the API
    :param max_items: maximum number of message requested on the same query
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.9.4'

    CATEGORIES = [CATEGORY_MESSAGE]
    EXTRA_SEARCH_FIELDS = {
        'channel_name': ['channel_info', 'name'],
        'channel_id': ['channel_info', 'id']
    }

    def __init__(self, channel, api_token, max_items=MAX_ITEMS,
                 tag=None, archive=None, ssl_verify=True):
        origin = urijoin(SLACK_URL, channel)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.channel = channel
        self.api_token = api_token
        self.max_items = max_items
        self.client = None

        self._users = {}

    def fetch(self, category=CATEGORY_MESSAGE, from_date=DEFAULT_DATETIME):
        """Fetch the messages from the channel.

        This method fetches the messages stored on the channel that were
        sent since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain messages sent since this date

        :returns: a generator of messages
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date)
        latest = datetime_utcnow().timestamp()

        kwargs = {'from_date': from_date, 'latest': latest}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the messages

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        latest = kwargs['latest']

        logger.info("Fetching messages of '%s' channel from %s",
                    self.channel, str(from_date))

        raw_info = self.client.channel_info(self.channel)

        channel_info = self.parse_channel_info(raw_info)

        if channel_info['is_archived']:
            channel_info['num_members'] = None
            logger.warning("channel_info.num_members is None for archived channels %s", self.channel)
        else:
            channel_info['num_members'] = self.client.conversation_members(self.channel)

        oldest = datetime_to_utc(from_date).timestamp()

        fetching = True
        nmsgs = 0

        while fetching:
            raw_history = self.client.history(self.channel,
                                              oldest=oldest, latest=latest)
            messages, fetching = self.parse_history(raw_history)

            for message in messages:
                # Fetch user data
                user_id = None
                if 'user' in message:
                    user_id = message['user']
                elif 'comment' in message:
                    user_id = message['comment']['user']

                if user_id:
                    message['user_data'] = self.__get_or_fetch_user(user_id)

                message['channel_info'] = channel_info
                yield message

                nmsgs += 1

                if fetching:
                    latest = float(message['ts'])

        logger.info("Fetch process completed: %s message fetched", nmsgs)

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archive
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend does not support items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Slack item.

        This identifier will be the mix of two fields because Slack
        messages does not have any unique identifier. In this case,
        'ts' and 'user' values (or 'bot_id' when the message is sent by a bot)
        are combined because there have been cases where two messages were sent
        by different users at the same time.

        In the case where neither the 'user' or 'bot_id' attributes are present
        (e.g, bot deleted), the fallback option is to generate the identifier
        using the 'ts' and 'username' values.
        """
        if 'user' in item:
            nick = item['user']
        elif 'comment' in item:
            nick = item['comment']['user']
        elif 'bot_id' in item:
            nick = item['bot_id']
        else:
            nick = item['username']

        return item['ts'] + nick

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Slack item.

        The timestamp is extracted from 'ts' field and converted
        to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = float(item['ts'])

        return ts

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Slack item.

        This backend only generates one type of item which is
        'message'.
        """
        return CATEGORY_MESSAGE

    @staticmethod
    def parse_channel_info(raw_channel_info):
        """Parse a channel info JSON stream.

        This method parses a JSON stream, containing the information
        from a channel, and returns a dict with the parsed data.

        :param raw_channel_info

        :returns: a dict with the parsed information about a channel
        """
        result = json.loads(raw_channel_info)
        return result['channel']

    @staticmethod
    def parse_history(raw_history):
        """Parse a channel history JSON stream.

        This method parses a JSON stream, containing the history of
        a channel, and returns a list with the parsed data. It also
        returns if there are more messages that are not included on
        this stream.

        :param raw_history: JSON string to parse

        :returns: a tuple with a list of dicts with the parsed messages
            and 'has_more' value
        """
        result = json.loads(raw_history)
        return result['messages'], result['has_more']

    @staticmethod
    def parse_user(raw_user):
        """Parse a user's info JSON stream.

        This method parses a JSON stream, containing the information
        from a user, and returns a dict with the parsed data.

        :param raw_user: JSON string to parse

        :returns: a dict with the parsed user's information
        """
        result = json.loads(raw_user)
        return result['user']

    def _init_client(self, from_archive=False):
        """Init client"""

        return SlackClient(self.api_token, self.max_items, self.archive,
                           from_archive, self.ssl_verify)

    def __get_or_fetch_user(self, user_id):
        if user_id in self._users:
            return self._users[user_id]

        logger.debug("User %s not found on client cache; fetching it", user_id)

        raw_user = self.client.user(user_id)
        user = self.parse_user(raw_user)

        self._users[user_id] = user
        return user


class SlackClientError(BaseError):
    """Raised when an error occurs using the Slack client"""

    message = "%(error)s"


class SlackClient(HttpClient):
    """Slack API client.

    Client for fetching information from the Slack server
    using its REST API.

    :param api_token: key needed to use the API
    :param max_items: maximum number of items per request
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    URL = urijoin(SLACK_URL, 'api', '%(resource)s')

    AUTHORIZATION_HEADER = 'Authorization'
    RCONVERSATION_MEMBERS = 'conversations.members'
    RCONVERSATION_INFO = 'conversations.info'
    # conversations.history must replace channels.history after Feb 24th 2021
    RCONVERSATION_HISTORY = 'conversations.history'
    RCHANNEL_HISTORY = 'channels.history'
    RUSER_INFO = 'users.info'

    PCHANNEL = 'channel'
    PCOUNT = 'count'
    POLDEST = 'oldest'
    PLATEST = 'latest'
    PTOKEN = 'token'
    PUSER = 'user'

    def __init__(self, api_token, max_items=MAX_ITEMS, archive=None, from_archive=False, ssl_verify=True):
        super().__init__(SLACK_URL, archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        self.api_token = api_token
        self.max_items = max_items

    def conversation_members(self, conversation):
        """Fetch the number of members in a conversation, which is a supertype for public and
        private ones, DM and group DM.

        :param conversation: the ID of the conversation
        """
        members = 0

        resource = self.RCONVERSATION_MEMBERS

        params = {
            self.PCHANNEL: conversation,
        }

        raw_response = self._fetch(resource, params)
        response = json.loads(raw_response)

        members += len(response["members"])
        while 'next_cursor' in response['response_metadata'] and response['response_metadata']['next_cursor']:
            params['cursor'] = response['response_metadata']['next_cursor']
            raw_response = self._fetch(resource, params)
            response = json.loads(raw_response)
            members += len(response["members"])

        return members

    def channel_info(self, channel):
        """Fetch information about a channel."""

        resource = self.RCONVERSATION_INFO

        params = {
            self.PCHANNEL: channel,
        }

        response = self._fetch(resource, params)

        return response

    def history(self, channel, oldest=None, latest=None):
        """Fetch the history of a channel."""

        # the channels.history endpoint will be working until Feb 24th 2021
        # apps created after June 10th 2020 won't work with this endpoint
        resource = self.RCHANNEL_HISTORY

        params = {
            self.PCHANNEL: channel,
            self.PCOUNT: self.max_items
        }

        if oldest is not None:
            formatted_oldest = self.__format_timestamp(oldest, subtract=True)
            params[self.POLDEST] = formatted_oldest
        if latest is not None:
            formatted_latest = self.__format_timestamp(latest)
            params[self.PLATEST] = formatted_latest

        response = self._fetch(resource, params)

        return response

    def user(self, user_id):
        """Fetch user info."""

        resource = self.RUSER_INFO

        params = {
            self.PUSER: user_id
        }

        response = self._fetch(resource, params)

        return response

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the token information
        before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if SlackClient.AUTHORIZATION_HEADER in headers:
            headers.pop(SlackClient.AUTHORIZATION_HEADER)

        return url, headers, payload

    def _fetch(self, resource, params):
        """Fetch a resource.

        :param resource: resource to get
        :param params: dict with the HTTP parameters needed to get
            the given resource
        """
        url = self.URL % {'resource': resource}
        headers = {
            self.AUTHORIZATION_HEADER: 'Bearer {}'.format(self.api_token)
        }

        logger.debug("Slack client requests: %s params: %s",
                     resource, str(params))

        r = self.fetch(url, payload=params, headers=headers)

        # Check for possible API errors
        result = r.json()

        if not result['ok']:
            if result['error'] == 'user_not_found':
                return '{"ok":false,"user":null}'
            raise SlackClientError(error=result['error'])

        return r.text

    def __format_timestamp(self, ts, subtract=False):
        """Handle the timestamp value to be passed to the channels.history API endpoint. In
        particular, two cases are covered:

        - Since the minimum value supported by Slack is 0, the value 0.0 must be converted.
        - Slack does not include in its result the lower limit of the search if it has
          the same date of 'oldest'. To get this messages too, we subtract a low value to
          be sure the dates are not the same. To avoid precision problems it is subtracted
          by five decimals and not by six.

        :param ts: timestamp float value
        :param subtract: if True, `ts` is decreased by 0.00001
        """
        if ts == 0.0:
            return "0"

        processed = ts
        if processed > 0.0 and subtract:
            processed -= .00001

        processed = FLOAT_FORMAT.format(processed)

        return processed


class SlackCommand(BackendCommand):
    """Class to run Slack backend from the command line."""

    BACKEND = Slack

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Slack argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Backend token is required
        action = parser.parser._option_string_actions['--api-token']
        action.required = True

        # Slack options
        group = parser.parser.add_argument_group('Slack arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="Maximum number of items requested on the same query")

        # Required arguments
        parser.parser.add_argument('channel',
                                   help="Slack channel identifier")

        return parser

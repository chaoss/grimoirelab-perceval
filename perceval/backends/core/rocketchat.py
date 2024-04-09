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
#     Aditya Prajapati <aditya10699@gmail.com>
#     Animesh Kumar <animuz111@gmail.com>
#

import logging
import json

from grimoirelab_toolkit.uris import urijoin
from grimoirelab_toolkit.datetime import (datetime_utcnow,
                                          datetime_to_utc,
                                          str_to_datetime)

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient, RateLimitHandler
from ...utils import DEFAULT_DATETIME

CATEGORY_MESSAGE = "message"

API_EXTENSION = "/api/v1/"

MIN_RATE_LIMIT = 10
MAX_ITEMS = 100

logger = logging.getLogger(__name__)


class RocketChat(Backend):
    """Rocket.Chat backend.

    This class allows to fetch messages from a channel(room) on a Rocket.Chat server.
    An API token and a User Id is required to access the server.

    :param url: server url from where messages are to be fetched
    :param channel: name of the channel from where data will be fetched
    :param user_id: generated User Id using your Rocket.Chat account
    :param api_token: token needed to use the API
    :param max_items: maximum number of message requested on the same query
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_MESSAGE]
    EXTRA_SEARCH_FIELDS = {
        'channel_name': ['channel_info', 'name'],
        'channel_id': ['channel_info', '_id']
    }

    def __init__(self, url, channel, user_id, api_token, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 tag=None, archive=None, ssl_verify=True):
        origin = urijoin(url, channel)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)

        self.url = url
        self.channel = channel
        self.user_id = user_id
        self.api_token = api_token
        self.max_items = max_items
        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.client = None

    def fetch(self, category=CATEGORY_MESSAGE, from_date=DEFAULT_DATETIME, filter_classified=False):
        """Fetch the messages from the channel.

        This method fetches the messages stored on the channel that were
        sent since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain messages sent since this date
        :param filter_classified: remove classified fields from the resulting items

        :returns: a generator of messages
        """
        if not from_date:
            from_date = DEFAULT_DATETIME
        from_date = datetime_to_utc(from_date)

        kwargs = {'from_date': from_date}

        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the messages.

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        logger.info("Fetching messages of channel: %s from date: %s",
                    self.channel, from_date)

        raw_channel_info = self.client.channel_info(self.channel)
        channel_info = self.parse_channel_info(raw_channel_info)

        fetching = True
        nmsgs = 0
        offset = 0

        while fetching:
            raw_messages = self.client.messages(self.channel, from_date, offset)
            messages, total = self.parse_messages(raw_messages)

            for message in messages:
                message["channel_info"] = channel_info
                nmsgs += 1
                yield message

            offset += len(messages)

            if offset == total:
                fetching = False

        logger.info("Fetch process completed: %s message fetched", nmsgs)

    @staticmethod
    def parse_messages(raw_messages):
        """Parse a channel messages JSON stream.

        This method parses a JSON stream, containing the
        history of a channel. It returns a list of messages
        and the total messages count in that channel.

        :param raw_messages: JSON string to parse

        :returns: a tuple with a list of dicts with the parsed messages
            and a total messages count in the channel.
        """
        result = json.loads(raw_messages)
        return result['messages'], result['total']

    @staticmethod
    def parse_channel_info(raw_channel_info):
        """Parse a channel's information JSON stream.

        This method parses a JSON stream, containing the information
        of the channel, and returns a dict with the parsed data.

        :param raw_channel_info: JSON string to parse

        :returns: a dict with the parsed channel's information
        """
        result = json.loads(raw_channel_info)
        return result['channel']

    @classmethod
    def has_archiving(cls):
        """Returns whether it supports archiving items on the fetch process.

        :returns: this backend supports items archive
        """
        return True

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend supports items resuming
        """
        return True

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Rocket.Chat item."""

        return item["_id"]

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Rocket.Chat item.

        The timestamp is extracted from 'ts' field,
        and then converted into a UNIX timestamp.

        :param item: item generated by the backend

        :returns: extracted timestamp
        """
        ts = str_to_datetime(item['_updatedAt']).timestamp()
        return ts

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Rocket.Chat item.

        This backend only generates one type of item which is
        'message'.
        """
        return CATEGORY_MESSAGE

    def _init_client(self, from_archive=False):
        """Init client"""

        return RocketChatClient(self.url, self.user_id, self.api_token,
                                self.max_items, self.sleep_for_rate,
                                self.min_rate_to_sleep, from_archive, self.archive, self.ssl_verify)


class RocketChatClient(HttpClient, RateLimitHandler):
    """Rocket.Chat API client.

    Client for fetching information from the Rocket.Chat server
    using its REST API.

    :param url: server url from where messages are to be fetched
    :param user_id: generated User Id using your Rocket.Chat account
    :param api_token: token needed to use the API
    :param max_items: maximum number of message requested on the same query
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param from_archive: it tells whether to write/read the archive
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    RCHANNEL_MESSAGES = 'channels.messages'
    RCHANNEL_INFO = 'channels.info'

    HAUTH_TOKEN = 'X-Auth-Token'
    HUSER_ID = 'X-User-Id'

    PCHANNEL_NAME = 'roomName'
    PCOUNT = "count"
    POLDEST = "oldest"

    def __init__(self, url, user_id, api_token, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 from_archive=False, archive=None, ssl_verify=True):

        base_url = urijoin(url, API_EXTENSION)
        self.user_id = user_id
        self.api_token = api_token
        self.max_items = max_items

        super().__init__(base_url, archive=archive, from_archive=from_archive,
                         ssl_verify=ssl_verify)
        super().setup_rate_limit_handler(sleep_for_rate=sleep_for_rate, min_rate_to_sleep=min_rate_to_sleep)

    def calculate_time_to_reset(self):
        """Number of seconds to wait. They are contained in the rate limit reset header."""

        time_to_reset = self.rate_limit_reset_ts - (datetime_utcnow().replace(microsecond=0).timestamp() + 1) * 1000
        time_to_reset /= 1000

        if time_to_reset < 0:
            time_to_reset = 0

        return time_to_reset

    def channel_info(self, channel):
        """Fetch information about a channel."""

        params = {
            self.PCHANNEL_NAME: channel,
        }

        path = urijoin(self.base_url, self.RCHANNEL_INFO)
        response = self.fetch(path, params)

        return response

    def messages(self, channel, from_date, offset):
        """Fetch messages from a channel.

        The messages are fetch in ascending order i.e. from the oldest
        to the latest based on the time they were last updated. A query is
        also passed as a param to fetch the messages from a given date.
        """
        query = '{"_updatedAt": {"$gte": {"$date": "%s"}}}' % from_date.isoformat()

        # The 'sort' param accepts a field based on which the messages are sorted.
        # The value of the field can be 1 for ascending order or -1 for descending order.
        params = {
            "roomName": channel,
            "sort": '{"_updatedAt": 1}',
            "count": self.max_items,
            "offset": offset,
            "query": query
        }

        path = urijoin(self.base_url, self.RCHANNEL_MESSAGES)
        response = self.fetch(path, params)

        return response

    def fetch(self, url, payload=None, headers=None):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param payload: payload of the request
        :param headers: headers of the request

        :returns a response object
        """
        headers = {
            self.HAUTH_TOKEN: self.api_token,
            self.HUSER_ID: self.user_id
        }

        logger.debug("Rocket.Chat client message request with params: %s", str(payload))

        if not self.from_archive:
            self.sleep_for_rate_limit()

        response = super().fetch(url, payload, headers=headers)

        if not self.from_archive:
            self.update_rate_limit(response)

        return response.text

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the token and
         user id information before storing/retrieving archived items.

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns: url, headers and the sanitized payload
        """
        if RocketChatClient.HAUTH_TOKEN in headers:
            headers.pop(RocketChatClient.HAUTH_TOKEN)

        if RocketChatClient.HUSER_ID in headers:
            headers.pop(RocketChatClient.HUSER_ID)

        return url, headers, payload


class RocketChatCommand(BackendCommand):
    """Class to run Rocket.Chat backend from the command line."""

    BACKEND = RocketChat

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Rocket.Chat argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Backend token is required
        action = parser.parser._option_string_actions['--api-token']
        action.required = True

        parser.parser.add_argument('-u', '--user-id', dest='user_id',
                                   required=True,
                                   help="User Id to fetch messages")

        # Required positional arguments
        parser.parser.add_argument('url',
                                   help="URL of the Rocket.Chat server")

        parser.parser.add_argument('channel',
                                   help="Rocket.Chat channel(room) name")

        # Rocket.Chat options
        group = parser.parser.add_argument_group('Rocket.Chat arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="Maximum number of items requested on the same query")
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")

        return parser

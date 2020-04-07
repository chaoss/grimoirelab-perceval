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
#

import logging
import json

from grimoirelab_toolkit.uris import urijoin
from grimoirelab_toolkit.datetime import (datetime_utcnow,
                                          datetime_to_utc,
                                          str_to_datetime)

from ...errors import BaseError
from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)

from ...client import HttpClient, RateLimitHandler
from ...utils import DEFAULT_DATETIME

CATEGORY_MESSAGE = "message"

MAX_ITEMS = 100
FLOAT_FORMAT = '{:.6f}'
API_EXTENSION = "/api/v1/"

# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 10

# Time to avoid too many request exception
SLEEP_TIME = 30
MAX_RETRIES = 5

logger = logging.getLogger(__name__)


class RocketChat(Backend):
    """Rocket Chat backend.

    This class allows to fetch messages from a channel on a rocketchat server.

    :param url: server url from where messages are to be fetched
    :param user_id: generated user-id using your rocketchat account
    :param channel_name: name of the channel where data will be fetched
    :param api_token: token needed to use the API
    :param max_items: maximum number of message requested on the same query
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param sleep_time: time to sleep in case
        of connection problems
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_MESSAGE]

    def __init__(self, url, user_id, channel_name, api_token, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, sleep_time=SLEEP_TIME,
                 tag=None, archive=None, ssl_verify=True):

        super().__init__(url, tag=tag, archive=archive, ssl_verify=ssl_verify)

        self.url = url
        self.channel_name = channel_name
        self.api_token = api_token
        self.user_id = user_id

        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.max_items = max_items

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
        """Fetch the messages

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        logger.info("Fetching messages of '%s' channel from %s",
                    self.channel_name, from_date)

        raw_info = self.client.channel_info(self.channel_name)
        channel_info = self.parse_data(raw_info, "channel")

        fetching = True
        nmsgs = 0
        offset = 0
        while fetching:
            raw_messages = self.client.messages(self.channel_name, from_date, offset, self.max_items)
            messages = self.parse_data(raw_messages, "messages")

            if not messages:
                fetching = False
                continue

            for message in messages:
                message["channel_info"] = channel_info
                yield message
                nmsgs += 1

            offset += 1

        logger.info("Fetch process completed: %s message fetched", nmsgs)

    @staticmethod
    def parse_data(raw_data, attribute):
        """Parse a channel messages/channel info JSON stream.

        This method parses a JSON stream, containing the data of
        a channel, and returns a list with the parsed data.

        :param raw_data: JSON string to parse
        :param attribute: type of data it is (supported types channel info, user and messages)

        :returns: a tuple with a list of dicts with the parsed messages
        """
        result = json.loads(raw_data)

        return result[attribute]

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Rocket chat item.

        This backend only generates one type of item which is
        'message'.
        """
        return CATEGORY_MESSAGE

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a RocketChat item."""

        return item["_id"]

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a RocketChat item.

        The timestamp is extracted from 'ts' field,
        and then converted into a UNIX timestamp.

        :param item: item generated by the backend

        :returns: extracted timestamp
        """
        ts = str_to_datetime(item['_updatedAt']).timestamp()
        return ts

    def _init_client(self, from_archive=False):
        """Init client"""

        return RocketChatClient(self.url, self.user_id, self.api_token, self.max_items, self.archive,
                                from_archive, self.ssl_verify)


class RocketChatClient(HttpClient, RateLimitHandler):
    """RocketChat API client.

    Client for fetching information from the RocketChat server
    using its REST API.

    :param url: server url from where messages are to be fetched
    :param user_id: generated user-id using your rocketchat account
    :param api_token: token needed to use the API
    :param max_items: maximum number of message requested on the same query
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param sleep_time: time to sleep in case
        of connection problems
    :param from_archive:
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    CHANNEL_MESSAGES = 'channels.messages'
    CHANNEL_NAME = 'roomName'
    CHANNEL_INFO = 'channels.info'
    AUTH_TOKEN = 'X-Auth-Token'
    USER_ID = 'X-User-Id'

    PCOUNT = "count"
    POLDEST = "oldest"

    def __init__(self, url, user_id, api_token, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, sleep_time=SLEEP_TIME,
                 from_archive=False, archive=None, ssl_verify=True):
        self.api_token = api_token
        self.max_items = max_items
        self.user_id = user_id

        super().__init__(url, sleep_time=sleep_time, max_retries=max_retries,
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        super().setup_rate_limit_handler(sleep_for_rate=sleep_for_rate, min_rate_to_sleep=min_rate_to_sleep)

    def calculate_time_to_reset(self):
        """Number of seconds to wait. They are contained in the rate limit reset header"""

        time_to_reset = self.rate_limit_reset_ts - (datetime_utcnow().replace(microsecond=0).timestamp() + 1) * 1000
        time_to_reset /= 1000

        if time_to_reset < 0:
            time_to_reset = 0

        return time_to_reset

    def channel_info(self, channel):
        """Fetch information about a channel."""

        resource = self.CHANNEL_INFO
        params = {
            self.CHANNEL_NAME: channel,
        }

        response = self._fetch(resource, params)

        return response.text

    def messages(self, channel, from_date, offset, max_items):
        """Fetch messages from a channel"""

        resource = self.CHANNEL_MESSAGES
        query = '{"_updatedAt": {"$gte": {"$date": "%s"}}}' % from_date.isoformat()

        params = {
            "roomName": channel,
            "sort": '{"_updatedAt": 1}',
            "count": max_items,
            "offset": offset * max_items,
            "query": query
        }

        if not self.from_archive:
            self.sleep_for_rate_limit()

        response = self._fetch(resource, params)

        if not self.from_archive:
            self.update_rate_limit(response)

        return response.text

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the token information
        before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns: url, headers and the sanitized payload
        """
        if not headers:
            return url, headers, payload

        if RocketChatClient.AUTH_TOKEN in headers:
            headers.pop(RocketChatClient.AUTH_TOKEN)

        if RocketChatClient.USER_ID in headers:
            headers.pop(RocketChatClient.USER_ID)

        return url, headers, payload

    def _fetch(self, resource, params):
        """Fetch a resource.

        :param resource: resource to get
        :param params: dict with the HTTP parameters needed to get
            the given resource

        :returns: Data fetched from the server
        """
        url = urijoin(self.base_url, API_EXTENSION, resource)

        headers = {
            self.AUTH_TOKEN: self.api_token,
            self.USER_ID: self.user_id
        }

        logger.debug("RocketChat client requests: %s params: %s",
                     resource, str(params))

        r = self.fetch(url, payload=params, headers=headers)
        response = r.json()
        # Check for possible API errors
        if r.status_code != 200:
            raise RocketChatClientError(error=response['error'])
        elif r.status_code == 200 and response["success"] is False:
            raise RocketChatClientError(error=response['error'])

        return r


class RocketChatClientError(BaseError):
    """Raised when an error occurs using the RocketChat client"""

    message = "%(error)s"


class RocketChatCommand(BackendCommand):
    """Class to run RocketChat backend from the command line."""

    BACKEND = RocketChat

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Rocket Chat argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Required arguments
        parser.parser.add_argument('user_id',
                                   help="User identifier to fetch messages")

        parser.parser.add_argument('url',
                                   help="URL of the RocketChat server")

        parser.parser.add_argument('channel_name',
                                   help="Name of the channel to retrieve data from")

        # Rocket Chat options
        group = parser.parser.add_argument_group('Rocket.chat arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="Maximum number of items requested on the same query")
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=SLEEP_TIME, type=int,
                           help="minimum sleeping time to avoid too many request exception")

        return parser
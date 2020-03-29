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
#     Animesh Kumar <animuz111@gmail.com>
#

import logging
from grimoirelab_toolkit.datetime import str_to_datetime, datetime_utcnow
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        BackendError)
from ...client import HttpClient, RateLimitHandler
from ...utils import DEFAULT_DATETIME

CATEGORY_MESSAGE = "message"

GITTER_URL = 'https://gitter.im/'
GITTER_API_URL = 'https://api.gitter.im/v1'
DEFAULT_SEARCH_FIELD = 'item_id'

MAX_ITEMS = 100
MIN_RATE_LIMIT = 10

logger = logging.getLogger(__name__)


class Gitter(Backend):
    """Gitter backend.

    This class retrieves the messages sent to a Gitter room.
    To access the server an API token is required.

    The origin of the data will be set to the `GITTER_URL` plus the
    identifier of the room; i.e 'https://gitter.im/{group}/{room}'.

    :param group: group to which the room belongs
    :param room: identifier of the room from which the messages are to be fetched
    :param api_token: token or key needed to use the API
    :param max_items: maximum number of message requested on the same query
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_MESSAGE]

    def __init__(self, group=None, room=None, api_token=None, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 tag=None, archive=None, ssl_verify=True):
        origin = urijoin(GITTER_URL, group, room)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.group = group
        self.room = room
        self.api_token = api_token
        self.max_items = max_items
        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.client = None
        self.room_id = None

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id`,`group`,`room`
        and 'room_id'.

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item),
            'group': self.group,
            'room': self.room,
            'room_id': self.room_id

        }

        return search_fields

    def fetch(self, category=CATEGORY_MESSAGE, from_date=DEFAULT_DATETIME):
        """Fetch the messages from the room.

        This method fetches the messages sent in the room that were
        sent since the given date.

        :param category: the category of items to fetch
        :param from_date: date from which messages are to be fetched

        :returns: a generator of messages
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = from_date.strftime('%Y-%m-%d')
        kwargs = {
            'from_date': from_date,
        }

        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the messages.

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        logger.debug("Get Gitter message paginated items of room: %s from date: %s", self.room, from_date)

        from_date = str_to_datetime(from_date).timestamp()
        fetching = True
        before_id = None
        num_msgs = 0
        page = 0
        room = urijoin(self.group, self.room)

        self.room_id = self.client.get_room_id(room)

        if not self.room_id:
            msg = "Room id not found for room %s" % room
            logger.error(msg)

            raise BackendError(cause=msg)

        logger.debug("Room id of room: %s is %s", self.room, self.room_id)

        while fetching:
            page += 1
            logger.debug("Page: %i" % page)
            message_group = self.client.message_page(self.room_id, before_id)

            message_group = message_group.json()

            if not message_group:
                fetching = False
                continue

            for raw_message in message_group:

                if str_to_datetime(raw_message['sent']).timestamp() > from_date:
                    num_msgs += 1
                    yield raw_message
                else:
                    fetching = False

            before_id = message_group[0]['id']

        logger.debug("Fetch process completed: %s messages fetched", num_msgs)

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
        """Extracts the identifier from a Gitter item."""

        return item['id']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the sent time of a message
        from a Gitter item.

        The timestamp is extracted from 'sent' field and
        converted to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = str_to_datetime(item['sent'])

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Gitter item.

        This backend only generates one type of item which is
        'message'.
        """
        return CATEGORY_MESSAGE

    def _init_client(self, from_archive=False):
        """Init client"""

        return GitterClient(self.api_token, self.max_items, self.archive,
                            self.sleep_for_rate, self.min_rate_to_sleep,
                            from_archive, self.ssl_verify)


class GitterClient(HttpClient, RateLimitHandler):
    """Gitter API client.

    Client for fetching information from the Gitter server
    using its REST API.

    :param api_token: key needed to use the API
    :param max_items: maximum number of items per request
    :param archive: an archive to store/read fetched data
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    # API resources
    RMESSAGES = 'chatMessages'
    RROOMS = 'rooms'

    # API headers
    HAUTHORIZATION = 'Authorization'

    # Resource parameters
    PLIMIT = 'limit'
    PBEFORE_ID = 'beforeId'

    def __init__(self, api_token, max_items=MAX_ITEMS, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 from_archive=False, ssl_verify=True):

        base_url = GITTER_API_URL
        self.api_token = api_token
        self.max_items = max_items

        super().__init__(base_url, archive=archive, from_archive=from_archive,
                         ssl_verify=ssl_verify)
        super().setup_rate_limit_handler(sleep_for_rate=sleep_for_rate, min_rate_to_sleep=min_rate_to_sleep)

    def calculate_time_to_reset(self):
        """Number of seconds to wait. They are contained in the rate limit reset header"""

        current_epoch = (datetime_utcnow().replace(microsecond=0).timestamp() + 1) * 1000
        time_to_reset = (self.rate_limit_reset_ts - current_epoch) / 1000

        if time_to_reset < 0:
            time_to_reset = 0

        return time_to_reset

    def fetch(self, url, payload=None, headers=None):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param payload: payload of the request
        :param headers: headers of the request

        :returns a response object
        """
        headers = {
            self.HAUTHORIZATION: 'Bearer {}'.format(self.api_token)
        }

        logger.debug("Gitter client message request with params: %s", str(payload))

        if not self.from_archive:
            self.sleep_for_rate_limit()

        response = super().fetch(url, payload, headers=headers)

        if not self.from_archive:
            self.update_rate_limit(response)

        return response

    def message_page(self, room_id, before_id):
        """Fetch a page of messages."""

        payload = {
            self.PLIMIT: self.max_items,
        }

        if before_id:
            payload[self.PBEFORE_ID] = before_id

        path = urijoin(GITTER_API_URL, self.RROOMS,
                       room_id, self.RMESSAGES)

        return self.fetch(path, payload)

    def get_room_id(self, room):
        """Fetch the room id of a room."""

        path = urijoin(GITTER_API_URL, self.RROOMS)
        rooms = self.fetch(path)
        rooms = rooms.json()
        for raw_room in rooms:
            if raw_room['name'] == room:
                return raw_room['id']

        return None

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the token information
        before storing/retrieving archived items.

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if GitterClient.HAUTHORIZATION in headers:
            headers.pop(GitterClient.HAUTHORIZATION)

        return url, headers, payload


class GitterCommand(BackendCommand):
    """Class to run Gitter backend from the command line."""

    BACKEND = Gitter

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Gitter argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Backend token is required
        action = parser.parser._option_string_actions['--api-token']
        action.required = True

        # Gitter options
        group = parser.parser.add_argument_group('Gitter arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="Maximum number of items requested on the same query")
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")

        # Required arguments
        parser.parser.add_argument('group',
                                   help="Gitter group")
        parser.parser.add_argument('room',
                                   help="Gitter room")

        return parser

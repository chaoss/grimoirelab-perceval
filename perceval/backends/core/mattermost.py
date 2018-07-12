# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
# along with this program; if not, write to the Free Software
# Foundation, 51 Franklin Street, Fifth Floor, Boston, MA 02110-1335, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging

from grimoirelab_toolkit.datetime import datetime_to_utc, datetime_utcnow
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient, RateLimitHandler
from ...utils import DEFAULT_DATETIME


logger = logging.getLogger(__name__)

CATEGORY_POST = "post"

MAX_ITEMS = 60

# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 10
MAX_RATE_LIMIT = 500

# Default sleep time to deal with connection/server problems
DEFAULT_SLEEP_TIME = 1


class Mattermost(Backend):
    """Mattermost backend.

    This class retrieves the posts sent to a Mattermost channel.
    To access the server an API token is required, which must
    have enough permissions to read from the given channel.

    To initialize this class the URL of the server must be provided.
    The origin of data will be set using this `url` plus the
    channel from data is obtained (i.e: https://mattermost.example.com/abcdefg).

    :param url: URL of the server
    :param channel: identifier of the channel where data will be fetched
    :param api_token: token or key needed to use the API
    :param max_items: maximum number of message requested on the same query
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    :param sleep_time: minimun waiting time to avoid too many request
         exception
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_POST]

    def __init__(self, url, channel, api_token, max_items=MAX_ITEMS,
                 tag=None, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=DEFAULT_SLEEP_TIME):
        origin = urijoin(url, channel)

        super().__init__(origin, tag=tag, archive=archive)
        self.url = url
        self.channel = channel
        self.api_token = api_token
        self.max_items = max_items
        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep
        self.sleep_time = sleep_time
        self.client = None

        self._users = {}

    def fetch(self, category=CATEGORY_POST, from_date=DEFAULT_DATETIME):
        """Fetch the posts from the channel.

        This method fetches the posts stored on the channel that were
        sent since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain posts sent since this date

        :returns: a generator of posts
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

        logger.info("Fetching messages of '%s' - '%s' channel from %s",
                    self.url, self.channel, str(from_date))

        fetching = True
        page = 0
        nposts = 0

        # Convert timestamp to integer for comparing
        since = int(from_date.timestamp() * 1000)

        while fetching:
            raw_posts = self.client.posts(self.channel, page=page)

            posts_before = nposts

            for post in self._parse_posts(raw_posts):
                if post['update_at'] < since:
                    fetching = False
                    break

                # Fetch user data
                user_id = post['user_id']
                user = self._get_or_fetch_user(user_id)
                post['user_data'] = user

                yield post
                nposts += 1

            if fetching:
                # If no new posts were fetched; stop the process
                if posts_before == nposts:
                    fetching = False
                else:
                    page += 1

        logger.info("Fetch process completed: %s posts fetched", nposts)

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
        """Extracts the identifier from a Mattermost item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and converts the update time from a Metadata item.

        The timestamp is extracted from 'update_at' field. This field
        is already a UNIX timestamp but it needs to be converted to
        float.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = float(item['update_at'] / 1000.0)

        return ts

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Mattermost item.

        This backend only generates one type of item which is
        'post'.
        """
        return CATEGORY_POST

    @staticmethod
    def parse_json(raw_json):
        """Parse a Mattermost JSON stream.

        The method parses a JSON stream and returns a
        dict with the parsed data.

        :param raw_json: JSON string to parse

        :returns: a dict with the parsed data
        """
        result = json.loads(raw_json)
        return result

    def _init_client(self, from_archive=False):
        """Init client"""

        return MattermostClient(self.url, self.api_token,
                                max_items=self.max_items,
                                sleep_for_rate=self.sleep_for_rate,
                                min_rate_to_sleep=self.min_rate_to_sleep,
                                sleep_time=self.sleep_time,
                                archive=self.archive, from_archive=from_archive)

    def _parse_posts(self, raw_posts):
        """Parse posts and returns in order."""

        parsed_posts = self.parse_json(raw_posts)

        # Posts are not sorted. The order is provided by
        # 'order' key.
        for post_id in parsed_posts['order']:
            yield parsed_posts['posts'][post_id]

    def _get_or_fetch_user(self, user_id):
        if user_id in self._users:
            return self._users[user_id]

        logger.debug("User %s not found on client cache; fetching it", user_id)

        raw_user = self.client.user(user_id)
        user = self.parse_json(raw_user)

        self._users[user_id] = user
        return user


class MattermostClient(HttpClient, RateLimitHandler):
    """Mattermost API client.

    Client for fetching information from a Mattermost server
    using its REST API.

    :param base_url: URL of the Mattermost server
    :param api_key: key needed to use the API
    :param max_items: maximum number of items fetched per request
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    :param sleep_time: time to sleep in case
        of connection problems
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    """
    API_URL = urijoin('%(base_url)s', 'api', 'v4', '%(entrypoint)s')

    RCHANNELS = 'channels'
    RPOSTS = 'posts'
    RUSERS = 'users'

    PPAGE = 'page'
    PPER_PAGE = 'per_page'

    def __init__(self, base_url, api_token, max_items=MAX_ITEMS,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=DEFAULT_SLEEP_TIME,
                 archive=None, from_archive=False):
        self.api_token = api_token
        self.max_items = max_items

        super().__init__(base_url.rstrip('/'),
                         sleep_time=sleep_time,
                         extra_headers=self._set_extra_headers(),
                         archive=archive, from_archive=from_archive)
        super().setup_rate_limit_handler(sleep_for_rate=sleep_for_rate,
                                         min_rate_to_sleep=min_rate_to_sleep)

    def posts(self, channel, page=None):
        """Fetch the history of a channel."""

        entrypoint = self.RCHANNELS + '/' + channel + '/' + self.RPOSTS

        params = {
            self.PPER_PAGE: self.max_items
        }

        if page is not None:
            params[self.PPAGE] = page

        response = self._fetch(entrypoint, params)

        return response

    def user(self, user):
        """Fetch user data."""

        entrypoint = self.RUSERS + '/' + user
        response = self._fetch(entrypoint, None)

        return response

    def fetch(self, url, payload=None, headers=None,
              method=HttpClient.GET, stream=False, verify=True):
        """Override fetch method to handle API rate limit.

        :param url: link to the resource
        :param payload: payload of the request
        :param headers: headers of the request
        :param method: type of request call (GET or POST)
        :param stream: defer downloading the response body until the response
            content is available

        :returns a response object
        """
        if not self.from_archive:
            self.sleep_for_rate_limit()

        response = super().fetch(url, payload, headers, method, stream, verify)

        if not self.from_archive:
            self.update_rate_limit(response)

        return response

    def calculate_time_to_reset(self):
        """Number of seconds to wait.

        The time is obtained by the different between the current date
        and the next date when the token is fully regenerated.
        """
        current_epoch = datetime_utcnow().replace(microsecond=0).timestamp() + 1
        time_to_reset = self.rate_limit_reset_ts - current_epoch

        if time_to_reset < 0:
            time_to_reset = 0

        return time_to_reset

    def _fetch(self, entry_point, params):
        """Fetch a resource.

        :param entrypoint: entrypoint to access
        :param params: dict with the HTTP parameters needed to access the
            given entry point
        """
        url = self.API_URL % {'base_url': self.base_url, 'entrypoint': entry_point}

        logger.debug("Mattermost client requests: %s params: %s",
                     entry_point, str(params))

        r = self.fetch(url, payload=params)

        return r.text

    def _set_extra_headers(self):
        """Set authentication tokens."""

        headers = {
            'Authorization': 'Bearer ' + self.api_token
        }
        return headers


class MattermostCommand(BackendCommand):
    """Class to run Mattermost backend from the command line."""

    BACKEND = Mattermost

    @staticmethod
    def setup_cmd_parser():
        """Returns the Meetup argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              token_auth=True,
                                              archive=True)

        # Mattermost options
        group = parser.parser.add_argument_group('Mattermost arguments')
        group.add_argument('--max-items', dest='max_items',
                           type=int, default=MAX_ITEMS,
                           help="maximum number of items requested on the same query")
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=DEFAULT_SLEEP_TIME, type=int,
                           help="minimun sleeping time to avoid too many request exception")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of Mattermost server")
        parser.parser.add_argument('channel',
                                   help="channel name")

        return parser

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
#     J. Manrique López de la Fuente <jsmanrique@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Alvaro del Castillo <acs@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import json
import logging

from grimoirelab_toolkit.datetime import datetime_to_utc, str_to_datetime
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...errors import BackendError, HttpClientError
from ...utils import DEFAULT_DATETIME


DEFAULT_SLEEP_TIME = 5
MAX_RETRIES = 10

CATEGORY_TOPIC = "topic"

logger = logging.getLogger(__name__)


class Discourse(Backend):
    """Discourse backend for Perceval.

    This class retrieves the topics posted in a Discourse board.
    To initialize this class the URL must be provided. The `url`
    will be set as the origin of the data.

    :param url: Discourse URL
    :param api_username: Discourse API username
    :param api_token: Discourse API access token
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param ssl_verify: enable/disable SSL verification
    """
    version = '1.0.0'

    CATEGORIES = [CATEGORY_TOPIC]
    EXTRA_SEARCH_FIELDS = {
        'category_id': ['category_id']
    }

    def __init__(self, url, api_username=None, api_token=None, tag=None, archive=None,
                 max_retries=MAX_RETRIES, sleep_time=DEFAULT_SLEEP_TIME, ssl_verify=True):
        origin = url

        if (api_username and not api_token) or (api_token and not api_username):
            raise BackendError(cause="Api token and username must be defined together")

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url
        self.api_username = api_username
        self.api_token = api_token
        self.max_retries = max_retries
        self.sleep_time = sleep_time

        self.client = None

    def fetch(self, category=CATEGORY_TOPIC, from_date=DEFAULT_DATETIME):
        """Fetch the topics from the Discurse board.

        The method retrieves, from a Discourse board the topics
        updated since the given date.

        :param category: the category of items to fetch
        :param from_date: obtain topics updated since this date

        :returns: a generator of topics
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date)

        kwargs = {'from_date': from_date}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the topics

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """

        from_date = kwargs['from_date']

        logger.info("Looking for topics at '%s', updated from '%s'",
                    self.url, str(from_date))

        ntopics = 0

        topics_ids = self.__fetch_and_parse_topics_ids(from_date)

        for topic_id in topics_ids:
            topic = self.__fetch_and_parse_topic(topic_id)
            ntopics += 1
            yield topic

        logger.info("Fetch process completed: %s topics fetched",
                    ntopics)

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
        """Extracts the identifier from a Discourse item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Discourse item.

        The timestamp used is extracted from 'last_posted_at' field.
        This date is converted to UNIX timestamp format taking into
        account the timezone of the date.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['last_posted_at']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Discourse item.

        This backend only generates one type of item which is
        'topic'.
        """
        return CATEGORY_TOPIC

    def _init_client(self, from_archive=False):
        """Init client"""

        return DiscourseClient(self.url, self.api_username, self.api_token,
                               self.sleep_time, self.max_retries,
                               archive=self.archive, from_archive=from_archive)

    def __fetch_and_parse_topics_ids(self, from_date):
        logger.debug("Fetching and parsing topics ids from %s",
                     str(from_date))

        candidates = []
        page = 0
        fetching = True

        while fetching:
            response = self.client.topics_page(page)
            topics = self.__parse_topics_page(response)

            if not topics:
                fetching = False

            # Topics are sorted by updated date from the newest
            # to the oldest. When a date is older than 'from_date'
            # we have reached to the end. Pinned topics are
            # ignored but added to the list if the date is in range.
            for topic in topics:
                # Pinned
                if topic[2] and topic[1] < from_date:
                    continue
                elif topic[1] < from_date:
                    fetching = False
                    break
                else:
                    candidates.append(topic)

            page += 1

        # Sort topics by date and in reverse order to fetch them from
        # the oldest to the newest
        candidates = sorted(candidates, key=lambda x: x[1])
        topics_ids = [topic[0] for topic in candidates]

        return topics_ids

    def __fetch_and_parse_topic(self, topic_id):
        logger.debug("Fetching and parsing topic %s", topic_id)

        raw_topic = self.client.topic(topic_id)

        topic = json.loads(raw_topic)

        # There are posts that could not included in the topic.
        # When post_count is greater than chunk_size, we have
        # to fetch the remaining posts
        posts_sz = topic['posts_count']
        chunk_sz = topic['chunk_size']

        if posts_sz > chunk_sz:
            posts_ids = topic['post_stream']['stream']
            posts_ids = posts_ids[chunk_sz:]

            for post_id in posts_ids:
                logger.debug("Fetching and parsing post %s", post_id)
                post = self.__fetch_and_parse_post(post_id)
                topic['post_stream']['posts'].append(post)

        return topic

    def __fetch_and_parse_post(self, post_id):
        logger.debug("Fetching and parsing post %s", post_id)
        raw_post = self.client.post(post_id)
        post = json.loads(raw_post)
        return post

    def __parse_topics_page(self, raw_json):
        """Parse a topics page stream.

        The result of parsing process is a generator of tuples. Each
        tuple contains de identifier of the topic, the last date
        when it was updated and whether is pinned or not.

        :param raw_json: JSON stream to parse

        :returns: a generator of parsed bugs
        """
        topics_page = json.loads(raw_json)

        topics_ids = []

        for topic in topics_page['topic_list']['topics']:
            topic_id = topic['id']
            if topic['last_posted_at'] is None:
                logger.warning("Topic %s with last_posted_at null. Ignoring it.", topic['title'])
                continue
            updated_at = str_to_datetime(topic['last_posted_at'])
            pinned = topic['pinned']
            topics_ids.append((topic_id, updated_at, pinned))

        return topics_ids


class DiscourseClient(HttpClient):
    """Discourse API client.

    This class implements a simple client to retrieve topics from
    any Discourse board.

    :param base_url: URL of the Discourse site
    :param api_username: Discourse API username
    :param api_key: Discourse API access token
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param archive: collect issues already retrieved from an archive
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification

    :raises HTTPError: when an error occurs doing the request
    """
    EXTRA_STATUS_FORCELIST = [429]

    # Static resources
    ALL_TOPICS = None  # Topics do not need a resource
    TOPICS_SUMMARY = 'latest'
    TOPIC = 't'
    POSTS = 'posts'

    # Headers
    HKEY = 'Api-Key'
    HUSER = 'Api-Username'

    # Params
    PPAGE = 'page'

    # Data type
    TJSON = '.json'

    def __init__(self, base_url, api_username=None, api_key=None,
                 sleep_time=DEFAULT_SLEEP_TIME, max_retries=MAX_RETRIES,
                 archive=None, from_archive=False, ssl_verify=True):
        self.api_username = api_username
        self.api_key = api_key

        if (self.api_username and not self.api_key) or (self.api_key and not self.api_username):
            raise HttpClientError(cause="Api key and username must be defined together")

        super().__init__(base_url, sleep_time=sleep_time, max_retries=max_retries,
                         extra_headers=self._set_extra_headers(),
                         extra_status_forcelist=self.EXTRA_STATUS_FORCELIST,
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)

    def topics_page(self, page=None):
        """Retrieve the #page summaries of the latest topics.

        :param page: number of page to retrieve
        """
        params = {
            self.PPAGE: page
        }

        # http://example.com/latest.json
        response = self._call(self.ALL_TOPICS, self.TOPICS_SUMMARY,
                              params=params)

        return response

    def topic(self, topic_id):
        """Retrive the topic with `topic_id` identifier.

        :param topic_id: identifier of the topic to retrieve
        """
        # http://example.com/t/8.json
        response = self._call(self.TOPIC, topic_id)

        return response

    def post(self, post_id):
        """Retrieve the post whit `post_id` identifier.

        :param post_id: identifier of the post to retrieve
        """
        # http://example.com/posts/10.json
        response = self._call(self.POSTS, post_id)

        return response

    def _set_extra_headers(self):
        """Set extra headers for session"""

        headers = {}

        if self.api_key and self.api_username:
            headers[self.HKEY] = self.api_key
            headers[self.HUSER] = self.api_username

        return headers

    def _call(self, res, res_id, params=None):
        """Run an API command.

        :param res: type of resource to fetch
        :param res_id: identifier of the resource
        :param params: dict with the HTTP parameters needed to run
            the given command
        """
        if res:
            url = urijoin(self.base_url, res, res_id)
        else:
            url = urijoin(self.base_url, res_id)
        url += self.TJSON

        logger.debug("Discourse client calls resource: %s %s params: %s",
                     res, res_id, str(params))

        r = self.fetch(url, payload=params)
        return r.text

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the user
        and key information before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if not headers:
            return url, headers, payload

        if DiscourseClient.HUSER and DiscourseClient.HKEY in headers:
            headers.pop(DiscourseClient.HUSER, None)
            headers.pop(DiscourseClient.HKEY, None)

        return url, headers, payload


class DiscourseCommand(BackendCommand):
    """Class to run Discourse backend from the command line."""

    BACKEND = Discourse

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Discourse argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the Discourse server")

        # Discourse options
        group = parser.parser.add_argument_group('Discourse arguments')
        # Generic client options
        group.add_argument('--api-username', dest='api_username',
                           type=str, help="API username ")
        group.add_argument('--max-retries', dest='max_retries',
                           default=MAX_RETRIES, type=int,
                           help="number of API call retries")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=DEFAULT_SLEEP_TIME, type=int,
                           help="sleeping time between API call retries")

        return parser

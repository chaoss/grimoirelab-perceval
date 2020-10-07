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
#     Valerio Cosentino <valcos@bitergia.com>
#     Quan Zhou <quan@bitergia.com>
#

import logging

import requests

from grimoirelab_toolkit.datetime import str_to_datetime
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        DEFAULT_SEARCH_FIELD)
from ...client import HttpClient, RateLimitHandler
from ...utils import DEFAULT_DATETIME

# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 10
# Default sleep time and retries to deal with connection/server problems
DEFAULT_SLEEP_TIME = 1
MAX_RETRIES = 5

CATEGORY_CHANGE = "changes"


logger = logging.getLogger(__name__)


class Weblate(Backend):
    """Weblate backend for Perceval.

    This class retrieves the activities from Weblate API.

    :param url: the URL of a Weblate instance
    :param project: a Weblate project
    :param api_token: Weblate API token
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimum rate needed to sleep until
         it will be reset
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_CHANGE]

    def __init__(self, url, project=None, api_token=None, tag=None, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 max_retries=MAX_RETRIES, sleep_time=DEFAULT_SLEEP_TIME, ssl_verify=True):

        super().__init__(url, tag=tag, archive=archive, ssl_verify=ssl_verify)

        self.api_token = api_token
        self.project = project
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.sleep_for_rate = sleep_for_rate
        self.min_rate_to_sleep = min_rate_to_sleep

        self.client = None

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` plus the `project`.

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item)
        }

        return search_fields

    def fetch(self, category=CATEGORY_CHANGE, from_date=DEFAULT_DATETIME):
        """Fetch changes from Weblate API.

        The method retrieves the activity that occurred on a project via the Weblate API.

        :param category: the category of items to fetch

        :returns: a generator of data
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        kwargs = {
            'from_date': from_date
        }
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch change items

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        logger.info("Fetching %s items on '%s' from '%s", category, self.origin, from_date)

        changes_groups = self.client.changes(from_date=from_date)
        for changes in changes_groups:
            for change in changes:
                user = change.get('user', None)
                change['user_data'] = None
                if user:
                    payload = {
                        'id': change['id'],
                        'type': 'user'
                    }
                    change['user_data'] = self.client.user(user, payload=payload)
                author = change.get('author', None)
                change['author_data'] = None
                if author:
                    payload = {
                        'id': change['id'],
                        'type': 'author'
                    }
                    change['author_data'] = self.client.user(author, payload=payload)
                unit = change.get('unit', None)
                change['unit_data'] = None
                if unit:
                    change['unit_data'] = self.client.unit(unit)
                yield change

        logger.info("Fetch process completed")

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
        """Extracts the identifier from an item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from an item.

        The timestamp used is extracted from 'timestamp' field.
        This date is converted to UNIX timestamp format taking into
        account the timezone of the date.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['timestamp']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Weblate item.

        This backend only generates one type of item which is
        'changes'.
        """
        return CATEGORY_CHANGE

    def _init_client(self, from_archive=False):
        """Init client"""

        return WeblateClient(self.origin, self.api_token, self.project,
                             self.sleep_for_rate, self.min_rate_to_sleep, self.sleep_time, self.max_retries,
                             archive=self.archive, from_archive=from_archive, ssl_verify=True)


class WeblateClient(HttpClient, RateLimitHandler):
    """WeblateClient API client.

    Client for fetching activities data from Weblate API.

    :param origin: URL of a Weblate instance
    :param api_token: Weblate API token
    :param project: a Weblate project
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    :param sleep_time: time (in seconds) to sleep in case
        of connection problems
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    # Resource parameters
    PAFTER = 'timestamp_after'

    def __init__(self, origin, api_token, project=None, sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 sleep_time=DEFAULT_SLEEP_TIME, max_retries=MAX_RETRIES,
                 archive=None, from_archive=False, ssl_verify=True):

        url = urijoin(origin, 'api')
        self.api_token = api_token
        self.project = project

        super().__init__(url, sleep_time=sleep_time, max_retries=max_retries,
                         extra_headers=self._set_extra_headers(),
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        super().setup_rate_limit_handler(sleep_for_rate=sleep_for_rate, min_rate_to_sleep=min_rate_to_sleep)

    def _set_extra_headers(self):
        """Set extra headers for session"""

        headers = {}
        if self.api_token:
            headers = {'Authorization': "Token %s" % self.api_token}

        return headers

    def unit(self, url):
        """Fetch unit data"""

        try:
            response = self.fetch(url)
            unit = response.json()
            return unit
        except requests.exceptions.HTTPError as error:
            logger.error("Error fetching {}: {}".format(url, error))
            raise error

    def user(self, url, payload=None):
        """Fetch user data"""

        user = {}
        try:
            response = self.fetch(url, payload=payload)
            user = response.json()
        except requests.exceptions.HTTPError as error:
            # The endpoint users returns a list of users if you have permissions to see
            # manage users (details at https://docs.weblate.org/en/latest/api.html#get--api-users-). If not, then
            # you get to see only your own details.
            # The except block covers the case of a token which lacks of permission to see users' detail. Due to
            # the specificity of this backend (tailored to a specific customer), one of the requirements of the
            # backend could be to have a token with the proper permission and get rid of this except block. In
            # the case that the backend should work with any token, it probably makes sense to avoid adding
            # a log message here, since the except block will be triggered for any document collected by Perceval.
            pass  # FIXME

        return user

    def changes(self, from_date=None):
        """Fetch changes of a project."""

        payload = {}

        if from_date:
            payload[self.PAFTER] = from_date.isoformat()

        if self.project:
            path = urijoin(self.base_url, 'projects', self.project, 'changes')
        else:
            path = urijoin(self.base_url, 'changes')

        return self.fetch_items(path, payload)

    def fetch_items(self, path, payload):
        """Return the items from Weblate API using links pagination"""

        current_page = 1  # current page
        fetch = True
        url_next = path
        logger.debug("Get Weblate paginated items from " + url_next)
        response = self.fetch(url_next, payload=payload)

        while fetch:
            page = response.json()
            results = page.get('results', [])

            logger.debug("Count: %i/%i, page %s" % (len(results), page['count'], current_page))

            yield results

            if not page['next']:
                fetch = False
                continue

            current_page += 1
            url_next = page['next']
            response = self.fetch(url_next)

    def calculate_time_to_reset(self):
        """Number of seconds to wait. They are contained in the rate limit reset header"""

        time_to_reset = 0 if self.rate_limit_reset_ts / 1000 < 0 else self.rate_limit_reset_ts / 1000
        return time_to_reset

    def fetch(self, url, payload=None, headers=None, method=HttpClient.GET, stream=False, auth=None):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param payload: payload of the request
        :param headers: headers of the request
        :param method: type of request call (GET or POST)
        :param stream: defer downloading the response body until the response content is available
        :param auth: auth of the request

        :returns a response object
        """
        if not self.from_archive:
            self.sleep_for_rate_limit()

        response = super().fetch(url, payload, headers, method, stream, auth)

        if not self.from_archive:
            self.update_rate_limit(response)

        return response


class WeblateCommand(BackendCommand):
    """Class to run Weblate backend from the command line."""

    BACKEND = Weblate

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Weblate argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              archive=True,
                                              from_date=True,
                                              ssl_verify=True,
                                              token_auth=True)

        # Weblate options
        group = parser.parser.add_argument_group('Weblate arguments')
        group.add_argument('--sleep-for-rate', dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument('--min-rate-to-sleep', dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")
        group.add_argument('--project', dest='project', help="Weblate project")

        # Generic client options
        group.add_argument('--max-retries', dest='max_retries',
                           default=MAX_RETRIES, type=int,
                           help="number of API call retries")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=DEFAULT_SLEEP_TIME, type=int,
                           help="sleeping time between API call retries")

        # Positional arguments
        parser.parser.add_argument('url',
                                   help="Weblate URL")

        return parser

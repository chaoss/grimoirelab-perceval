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

import json
import logging
import requests
from grimoirelab_toolkit.datetime import (str_to_datetime)
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        DEFAULT_SEARCH_FIELD)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME, DEFAULT_LAST_DATETIME
from datetime import datetime

CATEGORY_ISSUE = "issue"

PAGURE_URL = "https://pagure.io/"
PAGURE_API_URL = "https://pagure.io/api/0"

MAX_CATEGORY_ITEMS_PER_PAGE = 100
PER_PAGE = 100

# Default sleep time and retries to deal with connection/server problems
DEFAULT_SLEEP_TIME = 1
MAX_RETRIES = 5

logger = logging.getLogger(__name__)


class Pagure(Backend):
    """Pagure backend for Perceval.

    This class allows the fetch the issues stored in a Pagure
    repository.

    :param namespace: Pagure namespace
    :param repository: Pagure repository
    :param api_token: Pagure API token to access the API
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param max_items: max number of category items (e.g., issues,
        pull requests) per query
    :param sleep_time: time to sleep in case
        of connection problems
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.1.2'

    CATEGORIES = [CATEGORY_ISSUE]

    def __init__(self, namespace=None, repository=None,
                 api_token=None,
                 tag=None, archive=None,
                 max_retries=MAX_RETRIES, sleep_time=DEFAULT_SLEEP_TIME,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, ssl_verify=True):
        origin = PAGURE_URL

        # In case the repository is under a namespace add the namespace as well to the origin
        origin = urijoin(origin, namespace, repository) if namespace else urijoin(origin, repository)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)

        self.namespace = namespace
        self.repository = repository
        self.api_token = api_token
        self.max_retries = max_retries
        self.sleep_time = sleep_time
        self.max_items = max_items

        self.client = None

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` plus the `namespace` and `repo`.

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item),
            'namespace': self.namespace,
            'repo': self.repository
        }

        return search_fields

    def fetch(self, category=CATEGORY_ISSUE, from_date=DEFAULT_DATETIME, to_date=DEFAULT_LAST_DATETIME,
              filter_classified=False):
        """Fetch the issues from the repository.

        The method retrieves, from a Pagure repository,
        the issues updated since/until the given date.

        :param category: the category of items to fetch
        :param from_date: obtain issues updated since this date
        :param to_date: obtain issues until a until a specific date (included)
        :param filter_classified: remove classified fields from the resulting items

        :returns: a generator of issues
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        if not to_date:
            to_date = DEFAULT_LAST_DATETIME

        from_date = from_date.strftime('%Y-%m-%d')
        to_date = to_date.strftime('%Y-%m-%d')
        kwargs = {
            'from_date': from_date,
            'to_date': to_date
        }
        items = super().fetch(category,
                              filter_classified=filter_classified,
                              **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the items (issues)

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']
        to_date = kwargs['to_date']
        items = self.__fetch_issues(from_date, to_date)
        return items

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
        """Extracts the identifier from a Pagure item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Pagure item.

        The timestamp used is extracted from 'last_updated' field.
        This date is converted to UNIX timestamp format. As Pagure
        dates are in timestamp format the conversion is straightforward.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = int(item['last_updated'])
        ts = datetime.fromtimestamp(ts).timestamp()

        return ts

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Pagure item.

        This backend generates one type of item which is
        'issue'.
        """
        category = CATEGORY_ISSUE

        return category

    def _init_client(self, from_archive=False):
        """Init client"""

        return PagureClient(self.namespace, self.repository, self.api_token,
                            self.sleep_time, self.max_retries, self.max_items,
                            self.archive, from_archive, self.ssl_verify)

    def __fetch_issues(self, from_date, to_date):
        """Fetch the issues
        :param from_date: starting date from which issues are fetched
        :param to_date: ending date till which issues are fetched

        :returns: an issue object
        """
        issues_groups = self.client.issues(from_date=from_date)

        for raw_issues in issues_groups:
            issues = json.loads(raw_issues)
            issues = issues['issues']
            for issue in issues:

                if int(issue['last_updated']) > str_to_datetime(to_date).timestamp():
                    return

                yield issue


class PagureClient(HttpClient):
    """Client for retrieving information from Pagure API

    :param namespace: Pagure namespace
    :param repository: Pagure repository
    :param token: Pagure API token to access the API
    :param sleep_time: time to sleep in case
        of connection problems
    :param max_retries: number of max retries to a data source
        before raising a RetryError exception
    :param max_items: max number of category items per query
    :param archive: collect issues already retrieved from an archive
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    # API resources
    RISSUES = 'issues'

    # API headers
    HAUTHORIZATION = 'Authorization'

    # Resource parameters
    PSTATUS = 'status'
    PPER_PAGE = 'per_page'
    PORDER = 'order'
    PSINCE = 'since'

    # Predefined values
    VSTATUS_ALL = 'all'
    VORDER_ASC = 'asc'

    def __init__(self, namespace, repository, token,
                 sleep_time=DEFAULT_SLEEP_TIME, max_retries=MAX_RETRIES,
                 max_items=MAX_CATEGORY_ITEMS_PER_PAGE, archive=None, from_archive=False, ssl_verify=True):
        self.namespace = namespace
        self.repository = repository
        self.token = token
        self.max_items = max_items

        # URL to fetch the data from
        base_url = PAGURE_API_URL

        super().__init__(base_url, sleep_time=sleep_time, max_retries=max_retries,
                         extra_headers=self._set_extra_headers(),
                         archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)

    def issues(self, from_date=None):
        """Fetch the issues from the repository.

        The method retrieves, from a Pagure repository, the issues
        updated since the given date.

        :param from_date: obtain issues updated since this date

        :returns: a generator of issues
        """
        payload = {
            self.PSTATUS: self.VSTATUS_ALL,
            self.PPER_PAGE: self.max_items,
            self.PORDER: self.VORDER_ASC
        }

        if from_date:
            payload[self.PSINCE] = from_date

        path = urijoin(self.RISSUES)
        return self.fetch_items(path, payload)

    def fetch(self, url, payload=None, headers=None):
        """Fetch the data from a given URL.

        :param url: link to the resource
        :param payload: payload of the request
        :param headers: headers of the request

        :returns a response object
        """
        try:
            response = super().fetch(url, payload, headers)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == 404 and str(error.response.reason).upper() == 'NOT FOUND':
                logger.warning("The issue tracker is disabled please enable the feature for the repository")
                return None
            else:
                raise error

        return response

    def fetch_items(self, path, payload):
        """Return the items from Pagure API using links pagination

        :param path: Path from which the item is to be fetched
        :param payload: Payload to be added to the request

        :returns: a generator of items
        """
        page = 0  # current page
        last_page = None  # last page
        url_next = self.__get_url_item(path)
        logger.debug("Get Pagure paginated items from " + url_next)

        response = self.fetch(url_next, payload=payload)
        if not response:
            return []

        items = response.text
        page += 1

        if 'last' in response.links:
            last_url = response.links['last']['url']
            last_page = last_url.split('&page=')[1].split('&')[0]
            last_page = int(last_page)
            logger.debug("Page: %i/%i" % (page, last_page))

        while items:
            yield items

            items = None

            if 'next' in response.links:
                url_next = response.links['next']['url']
                response = self.fetch(url_next, payload=payload)
                page += 1

                items = response.text
                logger.debug("Page: %i/%i" % (page, last_page))

    def _set_extra_headers(self):
        """Set extra headers for session"""

        headers = {}
        if self.token:
            headers = {self.HAUTHORIZATION: "token %s" % self.token}

        return headers

    def __get_url_item(self, path):
        """Returns the url from which the item is to be fetched"""

        if self.namespace:  # if project is under a namespace
            url = self.__get_url_namespace_repository()
        else:  # if project is created without a namespace
            url = self.__get_url_repository()

        return urijoin(url, path)

    def __get_url_namespace_repository(self):
        """Build URL for a repository within a namespace"""

        return urijoin(self.base_url, self.namespace, self.repository)

    def __get_url_repository(self):
        """Build URL for a repository"""

        return urijoin(self.base_url, self.repository)

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the
        token information before storing/retrieving archived items

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """
        if not headers:
            return url, headers, payload

        if PagureClient.HAUTHORIZATION in headers:
            headers.pop(PagureClient.HAUTHORIZATION, None)

        return url, headers, payload


class PagureCommand(BackendCommand):
    """Class to run Pagure backend from the command line."""

    BACKEND = Pagure

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Pagure argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              to_date=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        group = parser.parser.add_argument_group('Pagure arguments')

        # Generic client options
        group.add_argument('--max-items', dest='max_items',
                           default=MAX_CATEGORY_ITEMS_PER_PAGE, type=int,
                           help="Max number of category items per query.")
        group.add_argument('--max-retries', dest='max_retries',
                           default=MAX_RETRIES, type=int,
                           help="number of API call retries")
        group.add_argument('--sleep-time', dest='sleep_time',
                           default=DEFAULT_SLEEP_TIME, type=int,
                           help="sleeping time between API call retries")

        # Positional arguments

        # A project be created directly or within a namespace
        # hence API call supports the access based on usecase. e.g.
        # GET /api/0/<repo>/issues
        # GET /api/0/<namespace>/<repo>/issues
        parser.parser.add_argument('namespace', nargs='?',
                                   help="Pagure namespace")
        parser.parser.add_argument('repository',
                                   help="Pagure repository")
        return parser

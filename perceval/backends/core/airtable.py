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
from grimoirelab_toolkit.datetime import str_to_datetime, datetime_to_utc
from grimoirelab_toolkit.uris import urijoin
from requests.exceptions import HTTPError
from requests.utils import quote

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME

CATEGORY_RECORD = "record"

AIRTABLE_URL = 'https://airtable.com/'
AIRTABLE_API_URL = 'https://api.airtable.com/v0'
DEFAULT_SEARCH_FIELD = 'item_id'

logger = logging.getLogger(__name__)


class Airtable(Backend):
    """Airtable backend.

    This class retrieves the records created in an Airtable table.
    To access the server an API token is required.

    The origin of the data will be set to the `AIRTABLE_URL` plus the
    identifier of the table; i.e 'https://airtable.com/{table}'.

    :param workspace_id: ID of the workspace containing the table
    :param table: identifier of the table from which the records are to be fetched
    :param api_token: token or key needed to use the API
    :param max_items: maximum number of records requested on the same query
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.1.0'

    CATEGORIES = [CATEGORY_RECORD]

    def __init__(self, workspace_id=None, table=None, api_token=None, max_items=None,
                 tag=None, archive=None, ssl_verify=True):

        # Table name may have non URL format (e.g. include spaces)
        table = quote(table)
        origin = urijoin(AIRTABLE_URL, table)

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.workspace_id = workspace_id
        self.table = table
        self.api_token = api_token
        self.max_items = max_items
        self.client = None

    def search_fields(self, item):
        """Add search fields to an item.

        It adds the values of `metadata_id` and `table`

        :param item: the item to extract the search fields values

        :returns: a dict of search fields
        """
        search_fields = {
            DEFAULT_SEARCH_FIELD: self.metadata_id(item),
            'table': self.table,
        }

        return search_fields

    def fetch(self, category=CATEGORY_RECORD, from_date=DEFAULT_DATETIME):
        """Fetch the records from the table.

        This method fetches the records that were created in the table
        since the given date.

        :param category: the category of items to fetch
        :param from_date: date from which records are to be fetched

        :returns: a generator of records
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date).isoformat()
        kwargs = {
            'from_date': from_date,
        }

        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the records.

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        logger.debug("Get Airtable records paginated items of table: %s from date: %s", self.table, from_date)

        from_date = str(from_date)
        fetching = True
        offset = None
        num_records = 0
        page = 0

        while fetching:
            page += 1
            logger.debug("Page: %i" % page)
            raw_record_group = self.client.record_page(self.workspace_id, self.table, offset, from_date)
            raw_record_group = raw_record_group.json()

            if "offset" in raw_record_group:
                offset = raw_record_group["offset"]
            else:
                fetching = False

            record_group = raw_record_group["records"]

            if not record_group:
                fetching = False
                continue

            for raw_record in record_group:
                num_records += 1
                yield raw_record

        logger.debug("Fetch process completed: %s records fetched", num_records)

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
        """Extracts the identifier from an Airtable item."""

        return item['id']

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and converts the created time of a record
        from an Airtable item.

        The timestamp is extracted from 'createdTime' field and
        converted to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = str_to_datetime(item['createdTime'])

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from an Airtable item.

        This backend only generates one type of item which is
        'record'.
        """
        return CATEGORY_RECORD

    def _init_client(self, from_archive=False):
        """Init client"""

        return AirtableClient(self.api_token, self.max_items, self.archive,
                              from_archive, self.ssl_verify)


class AirtableClient(HttpClient):
    """Airtable API client.

    Client for fetching information from the Airtable server
    using its REST API.

    :param api_token: key needed to use the API
    :param max_items: maximum number of items per request
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification
    """
    # API headers
    HAUTHORIZATION = 'Authorization'

    # Resource parameters
    PMAX_RECORDS = 'maxRecords'
    POFFSET = 'offset'
    PFILTER_BY_FORMULA = 'filterByFormula'

    # Predefined values
    VCREATED_TIME = 'CREATED_TIME()'

    def __init__(self, api_token, max_items=None, archive=None,
                 from_archive=False, ssl_verify=True):

        base_url = AIRTABLE_API_URL
        self.api_token = api_token
        self.max_items = max_items

        super().__init__(base_url, archive=archive, from_archive=from_archive,
                         ssl_verify=ssl_verify)

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

        logger.debug("Airtable client records request with params: %s", str(payload))

        try:
            response = super().fetch(url, payload, headers=headers)
        except HTTPError as e:
            logger.error("Fetching of records from URL %s was unsuccessful due to error %s",
                         url, str(e.response.text))
            raise e

        logger.debug("Records fetched from URL %s", url)

        return response

    def record_page(self, workspace_id, table, offset, from_date):
        """Fetch a page of records."""

        payload = self.__build_payload(offset, from_date)

        path = urijoin(AIRTABLE_API_URL, workspace_id, table)

        return self.fetch(path, payload)

    def __build_payload(self, offset, from_date):

        payload = {
            self.PFILTER_BY_FORMULA: self.VCREATED_TIME + '>' + '\'' + from_date + '\''
        }

        if self.max_items:
            payload[self.PMAX_RECORDS] = self.max_items

        if offset:
            payload[self.POFFSET] = offset

        return payload

    @staticmethod
    def sanitize_for_archive(url, headers, payload):
        """Sanitize payload of a HTTP request by removing the workspace ID and token
        information before storing/retrieving archived items.

        :param: url: HTTP url request
        :param: headers: HTTP headers request
        :param: payload: HTTP payload request

        :returns url, headers and the sanitized payload
        """

        url_items = str(url).split('/')
        url = str(url).replace(url_items[-2] + '/', "")

        if AirtableClient.HAUTHORIZATION in headers:
            headers.pop(AirtableClient.HAUTHORIZATION)

        return url, headers, payload


class AirtableCommand(BackendCommand):
    """Class to run Airtable backend from the command line."""

    BACKEND = Airtable

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Airtable argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # Backend token is required
        action = parser.parser._option_string_actions['--api-token']
        action.required = True

        # Airtable options
        group = parser.parser.add_argument_group('Airtable arguments')
        group.add_argument('--max-items', dest='max_items', type=int,
                           help="Maximum number of items requested on the same query")

        # Required arguments
        parser.parser.add_argument('workspace_id',
                                   help="Airtable workspace(base) ID ")
        parser.parser.add_argument('table',
                                   help="Airtable table name")

        return parser

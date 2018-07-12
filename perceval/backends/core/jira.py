# -*- coding: utf-8 -*-
#
# Copyright (C) 2016-2017 Bitergia
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
#     Alberto Martín <alberto.martin@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging

import requests

from requests.packages.urllib3.exceptions import InsecureRequestWarning

from grimoirelab_toolkit.datetime import datetime_to_utc, str_to_datetime
from grimoirelab_toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser)
from ...client import HttpClient
from ...utils import DEFAULT_DATETIME

CATEGORY_ISSUE = "issue"

MAX_ISSUES = 100  # Maximum number of issues per query

logger = logging.getLogger(__name__)


def map_custom_field(custom_fields, fields):
    """Add extra information for custom fields.

    :param custom_fields: set of custom fields with the extra information
    :param fields: fields of the issue where to add the extra information

    :returns: an set of items with the extra information mapped
    """
    def build_cf(cf, v):
        return {'id': cf['id'], 'name': cf['name'], 'value': v}

    return {
        k: build_cf(custom_fields[k], v)
        for k, v in fields.items()
        if k in custom_fields
    }


def filter_custom_fields(fields):
    """Filter custom fields from a given set of fields.

    :param fields: set of fields

    :returns: an object with the filtered custom fields
    """

    custom_fields = {}

    sorted_fields = [field for field in fields if field['custom'] is True]

    for custom_field in sorted_fields:
        custom_fields[custom_field['id']] = custom_field

    return custom_fields


class Jira(Backend):
    """JIRA backend for Perceval.

    This class retrieves the issues stored in JIRA issue tracking
    system. To initialize this class the URL must be provided.
    The `url` will be set as the origin of the data.

    :param url: JIRA's endpoint
    :param project: filter issues by project
    :param user: Jira user
    :param password: Jira user password
    :param verify: allows to disable SSL verification
    :param cert: SSL certificate path (PEM)
    :param max_issues: max number of issues per query
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    """
    version = '0.11.4'

    CATEGORIES = [CATEGORY_ISSUE]

    def __init__(self, url, project=None,
                 user=None, password=None,
                 verify=True, cert=None,
                 max_issues=MAX_ISSUES, tag=None,
                 archive=None):
        origin = url

        super().__init__(origin, tag=tag, archive=archive)
        self.url = url
        self.project = project
        self.user = user
        self.password = password
        self.verify = verify
        self.cert = cert
        self.max_issues = max_issues
        self.client = None

    def fetch(self, category=CATEGORY_ISSUE, from_date=DEFAULT_DATETIME):
        """Fetch the issues from the site.

        The method retrieves, from a JIRA site, the
        issues updated since the given date.

        :param category: the category of items to fetch
        :param from_date: retrieve issues updated from this date

        :returns: a generator of issues
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        from_date = datetime_to_utc(from_date)

        kwargs = {'from_date': from_date}
        items = super().fetch(category, **kwargs)

        return items

    def fetch_items(self, category, **kwargs):
        """Fetch the issues

        :param category: the category of items to fetch
        :param kwargs: backend arguments

        :returns: a generator of items
        """
        from_date = kwargs['from_date']

        logger.info("Looking for issues at site '%s', in project '%s' and updated from '%s'",
                    self.url, self.project, str(from_date))

        whole_pages = self.client.get_issues(from_date)

        fields = json.loads(self.client.get_fields())
        custom_fields = filter_custom_fields(fields)

        for whole_page in whole_pages:
            issues = self.parse_issues(whole_page)
            for issue in issues:
                mapping = map_custom_field(custom_fields, issue['fields'])
                for k, v in mapping.items():
                    issue['fields'][k] = v
                yield issue

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
        """Extracts the identifier from a Jira item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Jira item.

        The timestamp used is extracted from 'updated' field.
        This date is converted to UNIX timestamp format taking
        into account the timezone of the date.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['fields']['updated']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Jira item.

        This backend only generates one type of item which is
        'issue'.
        """
        return CATEGORY_ISSUE

    @staticmethod
    def parse_issues(raw_page):
        """Parse a JIRA API raw response.

        The method parses the API response retrieving the
        issues from the received items

        :param items: items from where to parse the issues

        :returns: a generator of issues
        """
        raw_issues = json.loads(raw_page)
        issues = raw_issues['issues']
        for issue in issues:
            yield issue

    def _init_client(self, from_archive=False):
        """Init client"""

        return JiraClient(self.url, self.project, self.user, self.password,
                          self.verify, self.cert, self.max_issues,
                          self.archive, from_archive)


class JiraClient(HttpClient):
    """JIRA API client.

    This class implements a simple client to retrieve issues from
    any JIRA issue tracking system.

    :param URL: URL of the JIRA server
    :param project: filter issues by project
    :param user: JIRA's username
    :param password: JIRA's password
    :param verify: allows to disable SSL verification
    :param cert: SSL certificate
    :param max_issues: max number of issues per query
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive

    :raises HTTPError: when an error occurs doing the request
    """

    EXPAND = 'renderedFields,transitions,operations,changelog'
    VERSION_API = '2'
    RESOURCE = 'rest/api'

    def __init__(self, url, project, user, password, verify, cert, max_issues=MAX_ISSUES,
                 archive=None, from_archive=False):
        super().__init__(url, archive=archive, from_archive=from_archive)
        self.project = project
        self.user = user
        self.password = password
        self.verify = verify
        self.cert = cert
        self.max_issues = max_issues

        if not from_archive:
            self.__init_session()

    def get_issues(self, from_date):
        """Retrieve all the issues from a given date.

        :param from_date: obtain issues updated since this date
        """
        start_at = 0

        url = urijoin(self.base_url, self.RESOURCE, self.VERSION_API, 'search')
        req = self.fetch(url, payload=self.__build_payload(start_at, from_date))
        issues = req.text

        data = req.json()
        tissues = data['total']
        nissues = data['maxResults']

        start_at += min(nissues, tissues)
        self.__log_status(start_at, tissues)

        while issues:
            yield issues
            issues = None

            if data['startAt'] + nissues < tissues:
                req = self.fetch(url, payload=self.__build_payload(start_at, from_date))

                data = req.json()
                start_at += nissues
                issues = req.text
                self.__log_status(start_at, tissues)

    def get_fields(self):
        """Retrieve all the fields available."""

        url = urijoin(self.base_url, self.RESOURCE, self.VERSION_API, 'field')
        req = self.fetch(url)

        return req.text

    def __build_jql_query(self, from_date):
        AND_OP = 'AND'
        UPDATED_OP = 'updated >'
        PROJECT_OP = 'project ='
        ORDER_BY_OP = 'order by'
        ASC_OP = 'asc'

        # Convert datetime to milliseconds since 1970-01-01.
        # This allows us to use the timezone of the given date
        strdate = str(int(from_date.timestamp() * 1000))

        if self.project:
            jql_query = ' '.join([PROJECT_OP, self.project, AND_OP,
                                  UPDATED_OP, strdate])
        else:
            jql_query = ' '.join([UPDATED_OP, strdate])

        jql_query += ' '.join(['', ORDER_BY_OP, 'updated', ASC_OP])

        return jql_query

    def __build_payload(self, start_at, from_date):
        payload = {
            'jql': self.__build_jql_query(from_date),
            'startAt': start_at,
            'expand': self.EXPAND,
            'maxResults': self.max_issues
        }
        return payload

    def __log_status(self, max_issues, total):
        if (total != 0):
            nissues = min(max_issues, total)
            logger.info("Fetching issues: %s/%s" % (nissues,
                                                    total))
        else:
            logger.info("No issues were found.")

    def __init_session(self):
        if (self.user and self.password) is not None:
            self.session.auth = (self.user, self.password)

        if self.cert:
            self.session.cert = self.cert

        if self.verify is not True:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            self.session.verify = False


class JiraCommand(BackendCommand):
    """Class to run Jira backend from the command line."""

    BACKEND = Jira

    @staticmethod
    def setup_cmd_parser():
        """Returns the Jira argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              basic_auth=True,
                                              archive=True)

        # JIRA options
        group = parser.parser.add_argument_group('JIRA arguments')
        group.add_argument('--project',
                           help="filter issues by Project")
        group.add_argument('--verify', default=True,
                           help="Value 'False' disables SSL verification")
        group.add_argument('--cert',
                           help="SSL certificate path (PEM)")
        group.add_argument('--max-issues', dest='max_issues',
                           type=int, default=MAX_ISSUES,
                           help="Maximum number of issues requested in the same query")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="JIRA's url")

        return parser

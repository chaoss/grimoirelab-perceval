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
#     Alberto Martín <alberto.martin@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Jesus M. Gonzalez-Barahona <jgb@gsyc.es>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import base64
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
MAX_RESULTS = 100  # Maximum number of results per query

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

    Note that when fetching data with an authenticated access (i.e.,
    user and password), information about issue transitions and
    operations (e.g., edit-issue, comment-issue) is included in the
    JSON documents produced by the backend.

    :param url: JIRA's endpoint
    :param project: filter issues by project
    :param user: Jira user
    :param password: Jira user password
    :param api_token: Jira user's personal access token or api token
    :param cert: SSL certificate path (PEM)
    :param max_results: max number of results per query
    :param tag: label used to mark the data
    :param archive: archive to store/retrieve items
    :param ssl_verify: enable/disable SSL verification
    """
    version = '0.15.0'

    CATEGORIES = [CATEGORY_ISSUE]
    EXTRA_SEARCH_FIELDS = {
        'project_id': ['fields', 'project', 'id'],
        'project_key': ['fields', 'project', 'key'],
        'project_name': ['fields', 'project', 'name'],
        'issue_key': ['key']
    }

    def __init__(self, url, project=None,
                 user=None, password=None, api_token=None,
                 cert=None, max_results=MAX_RESULTS,
                 tag=None, archive=None, ssl_verify=True):
        origin = url

        super().__init__(origin, tag=tag, archive=archive, ssl_verify=ssl_verify)
        self.url = url
        self.project = project
        self.user = user
        self.password = password
        self.api_token = api_token
        self.cert = cert
        self.max_results = max_results
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

                comments_data = self.__get_issue_comments(issue['id'])
                issue['comments_data'] = comments_data

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
                          self.cert, self.api_token, self.max_results,
                          self.archive, from_archive, self.ssl_verify)

    def __get_issue_comments(self, issue_id):
        """Get issue comments"""

        comments = []
        page_comments = self.client.get_comments(issue_id)

        for page_comment in page_comments:
            raw_comments = json.loads(page_comment)

            comments.extend(raw_comments['comments'])

        return comments


class JiraClient(HttpClient):
    """JIRA API client.

    This class implements a simple client to retrieve issues from
    any JIRA issue tracking system.

    :param URL: URL of the JIRA server
    :param project: filter issues by project
    :param user: JIRA's username
    :param password: JIRA's password
    :param api_token: JIRA user's personal access token or api token
    :param cert: SSL certificate
    :param max_results: max number of results per query
    :param archive: an archive to store/read fetched data
    :param from_archive: it tells whether to write/read the archive
    :param ssl_verify: enable/disable SSL verification

    :raises HTTPError: when an error occurs doing the request
    """
    VERSION_API = '2'
    RESOURCE = 'rest/api'

    # API resources
    RISSUE = 'issue'
    RCOMMENT = 'comment'
    RFIELD = 'field'
    RSEARCH = 'search'

    # Resource parameters
    PJQL = 'jql'
    PSTART_AT = 'startAt'
    PEXPAND = 'expand'
    PMAX_RESULTS = 'maxResults'

    # Predefined values
    VEXPAND = 'renderedFields,transitions,operations,changelog'

    def __init__(self, url, project, user, password, cert, api_token=None,
                 max_results=MAX_RESULTS, archive=None, from_archive=False,
                 ssl_verify=True):
        super().__init__(url, archive=archive, from_archive=from_archive, ssl_verify=ssl_verify)
        self.project = project
        self.user = user
        self.password = password
        self.api_token = api_token
        self.cert = cert
        self.max_results = max_results

        if not from_archive:
            self.__init_session()

    def get_items(self, from_date, url, expand_fields=True):
        """Retrieve all the items from a given date.

        :param url: endpoint API url
        :param from_date: obtain items updated since this date
        :param expand_fields: if True, it includes the expand fields in the payload
        """
        start_at = 0

        req = self.fetch(url, payload=self.__build_payload(start_at, from_date, expand_fields))
        issues = req.text

        data = req.json()
        titems = data['total']
        nitems = data['maxResults']

        start_at += min(nitems, titems)
        self.__log_status(start_at, titems, url)

        while issues:
            yield issues
            issues = None

            if data['startAt'] + nitems < titems:
                req = self.fetch(url, payload=self.__build_payload(start_at, from_date, expand_fields))

                data = req.json()
                start_at += nitems
                issues = req.text
                self.__log_status(start_at, titems, url)

    def get_issues(self, from_date):
        """Retrieve all the issues from a given date.

        :param from_date: obtain issues updated since this date
        """
        url = urijoin(self.base_url, self.RESOURCE, self.VERSION_API, self.RSEARCH)
        issues = self.get_items(from_date, url)

        return issues

    def get_comments(self, issue_id):
        """Retrieve all the comments of a given issue.

        :param issue_id: ID of the issue
        """
        url = urijoin(self.base_url, self.RESOURCE, self.VERSION_API, self.RISSUE, issue_id, self.RCOMMENT)
        comments = self.get_items(DEFAULT_DATETIME, url, expand_fields=False)

        return comments

    def get_fields(self):
        """Retrieve all the fields available."""

        url = urijoin(self.base_url, self.RESOURCE, self.VERSION_API, self.RFIELD)
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

    def __build_payload(self, start_at, from_date, expand=True):
        payload = {
            self.PJQL: self.__build_jql_query(from_date),
            self.PSTART_AT: start_at,
            self.PEXPAND: self.VEXPAND,
            self.PMAX_RESULTS: self.max_results
        }

        if not expand:
            payload.pop(self.PEXPAND)

        return payload

    def __log_status(self, max_items, total, url):
        if total != 0:
            nitems = min(max_items, total)
            logger.info("Fetching %s/%s items from %s" % (nitems, total, url))
        else:
            logger.info("No items were found for %s." % url)

    def __init_session(self):
        if (self.user and self.password) is not None:
            self.session.auth = (self.user, self.password)
        elif self.api_token is not None:
            auth_header = {}
            if self.user is None:
                # Jira Core/Software (8.14 and later), Jira Service Management (4.15 and later)
                # Data Center and server editions can use personal access tokens without a username
                # See https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html
                auth_header = {'Authorization': 'Bearer ' + self.api_token}
            else:
                # For Jira Cloud, username and token are required
                # See https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/
                auth_encoded = base64.b64encode((self.user + ':' + self.api_token).encode('utf-8')).decode('utf-8')
                auth_header = {'Authorization': 'Basic ' + auth_encoded}
            self.session.headers.update(auth_header)

        if self.cert:
            self.session.cert = self.cert

        if self.ssl_verify is not True:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            self.session.verify = False


class JiraCommand(BackendCommand):
    """Class to run Jira backend from the command line."""

    BACKEND = Jira

    @classmethod
    def setup_cmd_parser(cls):
        """Returns the Jira argument parser."""

        parser = BackendCommandArgumentParser(cls.BACKEND,
                                              from_date=True,
                                              basic_auth=True,
                                              token_auth=True,
                                              archive=True,
                                              ssl_verify=True)

        # JIRA options
        group = parser.parser.add_argument_group('JIRA arguments')
        group.add_argument('--project',
                           help="filter issues by Project")
        group.add_argument('--cert',
                           help="SSL certificate path (PEM)")
        group.add_argument('--max-results', dest='max_results',
                           type=int, default=MAX_RESULTS,
                           help="Maximum number of results requested in the same query")

        # Required arguments
        parser.parser.add_argument('url',
                                   help="JIRA's url")

        return parser

# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Bitergia
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Alberto Martín <alberto.martin@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging
import os.path

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from ...backend import Backend, BackendCommand, metadata
from ...cache import Cache
from ...errors import CacheError
from ...utils import (DEFAULT_DATETIME,
                      datetime_to_utc,
                      str_to_datetime,
                      urljoin)

MAX_ISSUES = 100  # Maximum number of issues per query

logger = logging.getLogger(__name__)


def map_custom_field(custom_fields, fields):
    """Add extra information for custom fields.

    :param custom_fields: set of custom fields with the extra information
    :param fields: fields of the issue where to add the extra information

    :returns: an set of items with the extra information mapped
    """
    build_cf = lambda cf, v: {'id': cf['id'], 'name': cf['name'], 'value': v}

    return {k: build_cf(custom_fields[k], v) for k, v in fields.items() if k in custom_fields}

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
    :param verify: allows to disable SSL verification
    :param cert: SSL certificate path (PEM)
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.6.1'

    def __init__(self, url, project=None, backend_user=None,
                 backend_password=None, verify=None,
                 cert=None, max_issues=None,
                 tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.project = project
        self.backend_user = backend_user
        self.backend_password = backend_password
        self.verify = verify
        self.cert = cert
        self.max_issues = max_issues
        self.client = JiraClient(url, project, backend_user,
                                 backend_password, verify, cert, max_issues)

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the issues from the site.

        The method retrieves, from a JIRA site, the
        issues updated since the given date.

        :param from_date: retrieve issues updated from this date

        :returns: a generator of issues
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        logger.info("Looking for issues at site '%s', in project '%s' and updated from '%s'",
                    self.url, self.project, str(from_date))

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)

        whole_pages = self.client.get_issues(from_date)

        fields = json.loads(self.client.get_fields())
        custom_fields = filter_custom_fields(fields)

        for whole_page in whole_pages:
            self._push_cache_queue(whole_page)
            self._flush_cache_queue()
            issues = self.parse_issues(whole_page)
            for issue in issues:
                mapping = map_custom_field(custom_fields, issue['fields'])
                for k, v in mapping.items():
                    issue['fields'][k] = v
                yield issue

    @metadata
    def fetch_from_cache(self):
        """Fetch the issues from the cache.

        :returns: a generator of issues

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        for items in cache_items:
            issues = self.parse_issues(items)
            for issue in issues:
                yield issue

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend supports items cache
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
        return 'issue'

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


class JiraClient:
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

    :raises HTTPError: when an error occurs doing the request
    """

    EXPAND = 'renderedFields,transitions,operations,changelog'
    VERSION_API = '2'
    RESOURCE = 'rest/api'

    def __init__(self, url, project, user, password, verify, cert, max_issues):
        self.url = url
        self.project = project
        self.user = user
        self.password = password
        self.verify = verify
        self.cert = cert
        self.max_issues = max_issues

    def __build_base_url(self, type='search'):
        base_api_url = self.url
        base_api_url = urljoin(base_api_url, self.RESOURCE, self.VERSION_API, type)
        return base_api_url

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
        session = requests.Session()

        if (self.user and self.password) is not None:
            session.auth = (self.user, self.password)

        if self.cert:
            session.cert = self.cert

        if self.verify is not True:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            session.verify = False

        return session

    def get_issues(self, from_date):
        """Retrieve all the issues from a given date.

        :param from_date: obtain issues updated since this date
        """
        session = self.__init_session()

        start_at = 0
        req = session.get(self.__build_base_url(),
                          params=self.__build_payload(start_at, from_date))
        req.raise_for_status()
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
                req = session.get(self.__build_base_url(),
                                  params=self.__build_payload(start_at, from_date))
                req.raise_for_status()
                data = req.json()
                start_at += nissues
                issues = req.text
                self.__log_status(start_at, tissues)

    def get_fields(self):
        """Retrieve all the fields available.  """
        session = self.__init_session()

        req = session.get(self.__build_base_url('field'))
        req.raise_for_status()
        return req.text


class JiraCommand(BackendCommand):
    """Class to run Jira backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)
        self.url = self.parsed_args.url
        self.project = self.parsed_args.project
        self.verify = self.parsed_args.verify
        self.cert = self.parsed_args.cert
        self.max_issues = self.parsed_args.max_issues
        self.backend_user = self.parsed_args.backend_user
        self.backend_password = self.parsed_args.backend_password
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.tag = self.parsed_args.tag
        self.outfile = self.parsed_args.outfile

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path

            cache_path = os.path.join(base_path, self.url)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = Jira(self.url, self.project,
                            self.backend_user, self.backend_password,
                            self.verify, self.cert, self.max_issues,
                            tag=self.tag, cache=cache)

    def run(self):
        """Fetch and print the issues.

        This method runs the backend to fetch the issues (plus all
        its answers and comments) of a given JIRA site.
        Issues are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            issues = self.backend.fetch_from_cache()
        else:
            issues = self.backend.fetch(from_date=self.from_date)

        try:
            for issue in issues:
                obj = json.dumps(issue, indent=4, sort_keys=True)
                self.outfile.write(obj)
                self.outfile.write('\n')
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(str(e.response.json()))
        except requests.exceptions.SSLError as e:
            logging.error('SSL ERROR: Try adding a --cert or use --verify False')
            raise requests.exceptions.SSLError(e)
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Jira argument parser."""

        parser = super().create_argument_parser()

        # JIRA options
        group = parser.add_argument_group('JIRA arguments')
        group.add_argument("--project",
                           help="filter issues by Project")
        group.add_argument("--verify", default=True,
                           help="Value 'False' disables SSL verification")
        group.add_argument("--cert",
                           help="SSL certificate path (PEM)")
        group.add_argument('--max-issues', dest='max_issues',
                           type=int, default=MAX_ISSUES,
                           help="Maximum number of issues requested in the same query")

        # Required arguments
        parser.add_argument("url", help="JIRA's url")

        return parser

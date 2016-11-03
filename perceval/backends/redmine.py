# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging
import os.path

import requests

from ..backend import Backend, BackendCommand, metadata
from ..cache import Cache
from ..errors import CacheError
from ..utils import (DEFAULT_DATETIME,
                     datetime_to_utc,
                     str_to_datetime,
                     urljoin)


logger = logging.getLogger(__name__)


MAX_ISSUES = 100  # Maximum number of issues per query
USER_FIELDS = ['assigned_to', 'author']


class Redmine(Backend):
    """Redmine backend.

    This class allows to fetch the issues stored on a Redmine
    server. Initialize this class passing the URL of this server.
    Some servers require authentication to get access to some
    data, if this is the case, pass the API token to `api_token`
    parameter.

    :param url: URL of the server
    :param api_token: token needed to use the API
    :param max_issues:  maximum number of issues requested on the same query
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.5.0'

    def __init__(self, url, api_token=None, max_issues=MAX_ISSUES,
                 tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.max_issues = max_issues
        self.client = RedmineClient(url, api_token=api_token)
        self._users = {}

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the issues from the server.

        This method fetches the issues stored on the server that were
        updated since the given date. Data about attachments, journals
        and watchers (among others) are included within each issue.

        :param from_date: obtain issues updated since this date

        :returns: a generator of issues
        """
        logger.info("Fetching issues of '%s' from %s",
                    self.url, str(from_date))

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)

        nissues = 0

        for issue_id in self.__fetch_issues_ids(from_date):
            issue = self.__fetch_and_parse_issue(issue_id)

            for key in USER_FIELDS:
                if not key in issue:
                    continue

                user = self.__get_or_fetch_user(issue[key]['id'])
                issue[key + '_data'] = user

            for journal in issue['journals']:
                if not 'user' in journal:
                    continue

                user = self.__get_or_fetch_user(journal['user']['id'])
                journal['user_data'] = user

            # Checkpoint
            self._push_cache_queue('{}')

            yield issue
            nissues += 1
            self._flush_cache_queue()

        logger.info("Fetch process completed: %s issues fetched", nissues)

    @metadata
    def fetch_from_cache(self):
        """Fetch the issues from the cache.

        It returns the issues stored in the cache object, provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of issues

        :raises CacheError: raised when an error occurs accesing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        logger.info("Retrieving cached tasks: '%s'", self.url)

        nissues = 0

        for issue in self.__fetch_from_cache():
            yield issue
            nissues += 1

        logger.info("Retrieval process completed: %s bugs retrieved from cache",
                    nissues)

    def __fetch_issues_ids(self, from_date):
        offset = 0
        issues = self.__fetch_and_parse_issues_page(from_date, offset,
                                                    self.max_issues)

        while issues:
            issue = issues.pop(0)
            issue_id = issue['id']
            yield issue_id

            if not issues:
                offset += self.max_issues
                issues = self.__fetch_and_parse_issues_page(from_date, offset,
                                                            self.max_issues)

    def __get_or_fetch_user(self, user_id):
        if user_id in self._users:
            return self._users[user_id]

        logger.debug("User %s not found on client cache; fetching it", user_id)
        user = self.__fetch_and_parse_user(user_id)
        self._users[user_id] = user

        return user

    def __fetch_from_cache(self):
        cache_items = self.cache.retrieve()

        while True:
            try:
                raw_issue = next(cache_items)
            except StopIteration:
                break

            issue = self.parse_issue_data(raw_issue)

            for cache_user in self.__fetch_users_from_cache(cache_items):
                self._users[cache_user['id']] = cache_user

            for key in USER_FIELDS:
                if not key in issue:
                    continue

                user_id = issue[key]['id']

                try:
                    issue[key + '_data'] = self._users[user_id]
                except KeyError:
                    # Fatal error. Keys must exist.
                    cause = "invalid cached data, user id %s not found" % user_id
                    raise CacheError(cause=cause)

            for journal in issue['journals']:
                if not 'user' in journal:
                    continue

                user_id = journal['user']['id']

                try:
                    journal['user_data'] = self._users[user_id]
                except KeyError:
                    # Fatal error. Keys must exist.
                    cause = "invalid cached data, user id %s not found" % user_id
                    raise CacheError(cause=cause)

            yield issue

    def __fetch_users_from_cache(self, cache_items):
        fetch_user = True

        while fetch_user:
            try:
                raw_user = next(cache_items)
            except StopIteration:
                # Fatal error. The code should not reach here.
                # Cache should had reaeched a checkpoint
                cause = "cache is exhausted but more items were expected"
                raise CacheError(cause=cause)

            if raw_user == '{}':
                fetch_user = False
            else:
                user = self.parse_user_data(raw_user)
                yield user

    def __fetch_and_parse_issues_page(self, from_date, offset, max_issues):
        logger.debug("Fetching and parsing issues page from %s (offset: %s)",
                     str(from_date), str(offset))
        raw_json = self.client.issues(from_date=from_date, offset=offset,
                                      max_issues=max_issues)
        issues = self.parse_issues(raw_json)
        return [issue for issue in issues]

    def __fetch_and_parse_issue(self, issue_id):
        logger.debug("Fetching and parsing issue #%s", issue_id)
        raw_issue = self.client.issue(issue_id)
        self._push_cache_queue(raw_issue)
        return self.parse_issue_data(raw_issue)

    def __fetch_and_parse_user(self, user_id):
        logger.debug("Fetching and parsing user #%s", user_id)
        raw_user = self.client.user(user_id)
        self._push_cache_queue(raw_user)
        return self.parse_user_data(raw_user)

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
        """Extracts the identifier from a Redmine item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Redmine item.

        The timestamp is extracted from 'updated_on' field and converted
        to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['updated_on']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Redmine item.

        This backend only generates one type of item which is
        'issue'.
        """
        return 'issue'

    @staticmethod
    def parse_issues(raw_json):
        """Parse a Redmine issues JSON stream.

        The method parses a JSON stream and returns a list iterator.
        Each item is a dictionary that contains the issue parsed data.

        :param raw_json: JSON string to parse

        :returns: a generator of parsed issues
        """
        results = json.loads(raw_json)

        issues = results['issues']
        for issue in issues:
            yield issue

    @staticmethod
    def parse_issue_data(raw_json):
        """Parse a Redmine issue JSON stream.

        The method parses a JSON stream and returns a dictionary
        with the parsed data for the given issue.

        :param raw_json: JSON string to parse

        :returns: a dictionary with the parsed issue data
        """
        result = json.loads(raw_json)
        return result['issue']

    @staticmethod
    def parse_user_data(raw_json):
        """Parse a Redmine user JSON stream.

        The method parses a JSON stream and returns a dictionary
        with the parsed data for the given user.

        :param raw_json: JSON string to parse

        :returns: a dictionary with the parsed user data
        """
        result = json.loads(raw_json)
        return result['user']


class RedmineCommand(BackendCommand):
    """Class to run Redmine backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.url = self.parsed_args.url
        self.backend_token = self.parsed_args.backend_token
        self.max_issues = self.parsed_args.max_issues
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

        self.backend = Redmine(self.url,
                               api_token=self.backend_token,
                               max_issues=self.max_issues,
                               tag=self.tag,
                               cache=cache)

    def run(self):
        """Fetch and print the issues.

        This method runs the backend to fetch the issues from the given
        repository. Issues are converted to JSON objects and printed to the
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
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the Redmine argument parser."""

        parser = super().create_argument_parser()

        # Redmine options
        group = parser.add_argument_group('Redmine arguments')
        group.add_argument('--max-issues', dest='max_issues',
                           type=int, default=MAX_ISSUES,
                           help="Maximum number of issues requested on the same query")

        # Required arguments
        parser.add_argument('url',
                            help="URL of the Redmine server")

        return parser


class RedmineClient:
    """Redmine API client.

    This class implements a client that retrieves issues from
    a Redmine server. Remine servers provides a REST API that
    returns its results in JSON format.

    :param base_url: URL of the Phabricator server
    :param api_token: token to get access to restricted data
        stored in the server
    """
    URL = '%(base)s/%(resource)s'

    RISSUES = 'issues'
    RUSERS = 'users'

    PINCLUDE = 'include'
    PKEY = 'key'
    PLIMIT = 'limit'
    POFFSET = 'offset'
    PSORT = 'sort'
    PSTATUS_ID = 'status_id'
    PUPDATED_ON = 'updated_on'

    CJSON = '.json'
    CATTACHMENTS = 'attachments'
    CCHANGESETS = 'changesets'
    CCHILDREN = 'children'
    CJOURNALS = 'journals'
    CRELATIONS = 'relations'
    CWATCHERS = 'watchers'

    def __init__(self, base_url, api_token=None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token

    def issues(self, from_date=DEFAULT_DATETIME,
               offset=None, max_issues=MAX_ISSUES):
        """Get the information of a list of issues.

        :param from_date: retrieve issues that where updated from that date;
            dates are converted to UTC
        :param offset: starting position for the search
        :param max_issues: maximum number of issues to reteurn per query
        """
        resource = self.RISSUES + self.CJSON

        ts = datetime_to_utc(from_date)
        ts = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

        # By default, Redmine returns open issues only.
        # Parameter 'status_id' is set to get all the statuses.
        params = {
            self.PSTATUS_ID : '*',
            self.PSORT : self.PUPDATED_ON,
            self.PUPDATED_ON : '>=' + ts,
            self.PLIMIT : max_issues
        }

        if offset is not None:
            params[self.POFFSET] = offset

        response = self._call(resource, params)

        return response

    def issue(self, issue_id):
        """Get the information of the given issue.

        :param issue_id: issue identifier
        """
        resource = urljoin(self.RISSUES, str(issue_id) + self.CJSON)

        params = {
            self.PINCLUDE : ','.join([self.CATTACHMENTS, self.CCHANGESETS,
                                      self.CCHILDREN, self.CJOURNALS,
                                      self.CRELATIONS, self.CWATCHERS])
        }

        response = self._call(resource, params)

        return response

    def user(self, user_id):
        """Get the information of the given user.

        :param user_id: user identifier
        """
        resource = urljoin(self.RUSERS, str(user_id) + self.CJSON)

        params = {}

        response = self._call(resource, params)

        return response

    def _call(self, resource, params):
        """Call to get a resource.

        :param method: resource to get
        :param params: dict with the HTTP parameters needed to get
            the given resource
        """
        url = self.URL % {'base' : self.base_url, 'resource' : resource}

        if self.api_token:
            params[self.PKEY] = self.api_token

        logger.debug("Redmine client requests: %s params: %s",
                     resource, str(params))

        r = requests.get(url, params=params, verify=False)
        r.raise_for_status()

        return r.text

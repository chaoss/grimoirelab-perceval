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
#     Alvaro del Castillo San Felix <acs@bitergia.com>
#

import json
import logging
import os.path

import requests

from ...backend import Backend, BackendCommand, metadata
from ...cache import Cache
from ...errors import BackendError, CacheError
from ...utils import (DEFAULT_DATETIME,
                      datetime_to_utc,
                      str_to_datetime,
                      urljoin)


logger = logging.getLogger(__name__)


MAX_BUGS = 500 # Maximum number of bugs per query
MAX_CONTENTS = 25 # Maximum number of bug contents (history, comments) per query


class BugzillaREST(Backend):
    """Bugzilla backend that uses its API REST.

    This class allows the fetch the bugs stored in Bugzilla
    server (version 5.0 or later). To initialize this class
    the URL of the server must be provided. The `url` will be
    set as the origin of the data.

    :param url: Bugzilla server URL
    :param user: Bugzilla user
    :param password: Bugzilla user password
    :param api_token: Bugzilla token
    :param max_bugs: maximum number of bugs requested on the same query
    :param tag: label used to mark the data
    :param cache: cache object to store raw data
    """
    version = '0.5.0'

    def __init__(self, url, user=None, password=None, api_token=None,
                 max_bugs=MAX_BUGS, tag=None, cache=None):
        origin = url

        super().__init__(origin, tag=tag, cache=cache)
        self.url = url
        self.max_bugs = max(1, max_bugs)
        self.client = BugzillaRESTClient(url, user=user, password=password,
                                         api_token=api_token)

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the bugs from the repository.

        The method retrieves, from a Bugzilla repository, the bugs
        updated since the given date.

        :param from_date: obtain bugs updated since this date

        :returns: a generator of bugs
        """
        if not from_date:
            from_date = DEFAULT_DATETIME

        logger.info("Looking for bugs: '%s' updated from '%s'",
                    self.url, str(from_date))

        self._purge_cache_queue()

        nbugs = 0
        for bug in self.__fetch_and_parse_bugs(from_date):
            nbugs += 1
            yield bug

        logger.info("Fetch process completed: %s bugs fetched", nbugs)

    @metadata
    def fetch_from_cache(self):
        """Fetch bugs from the cache.

        :returns: a generator of bugs

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        logger.info("Retrieving cached bugs: '%s'", self.url)
        nbugs = 0

        for bug in self.__retrieve_bugs_from_cache():
            nbugs += 1
            yield bug

        logger.info("Retrieval process completed: %s bugs retrieved from cache",
                    nbugs)

    def __fetch_and_parse_bugs(self, from_date):
        max_contents = min(MAX_CONTENTS, self.max_bugs)
        offset = 0

        while True:
            logger.debug("Fetching and parsing bugs from: %s, offset: %s, limit: %s ",
                         str(from_date), offset, self.max_bugs)
            raw_bugs = self.client.bugs(from_date=from_date, offset=offset,
                                        max_bugs=self.max_bugs)
            self._push_cache_queue(raw_bugs)

            data = json.loads(raw_bugs)
            buglist = data['bugs']

            tbugs = len(buglist)

            if tbugs == 0:
                break

            for i in range(0, tbugs, max_contents):
                chunk = buglist[i:i + max_contents]
                bug_ids = [b['id'] for b in chunk]

                comments = self.__fetch_and_parse_comments(*bug_ids)
                histories = self.__fetch_and_parse_histories(*bug_ids)
                attachments = self.__fetch_and_parse_attachments(*bug_ids)

                for bug in chunk:
                    bug_id = str(bug['id'])
                    bug['comments'] = comments[bug_id]
                    bug['history'] = histories[bug_id]
                    bug['attachments'] = attachments[bug_id]
                    yield bug

            self._flush_cache_queue()
            offset += self.max_bugs

    def __fetch_and_parse_comments(self, *bug_ids):
        logger.debug("Fetching and parsing comments")
        raw_comments = self.client.comments(*bug_ids)
        self._push_cache_queue(raw_comments)
        return self.__parse_comments(raw_comments)

    def __fetch_and_parse_histories(self, *bug_ids):
        logger.debug("Fetching and parsing histories")
        raw_histories = self.client.history(*bug_ids)
        self._push_cache_queue(raw_histories)
        return self.__parse_histories(raw_histories)

    def __fetch_and_parse_attachments(self, *bug_ids):
        logger.debug("Fetching and parsing attachments")
        raw_attachments = self.client.attachments(*bug_ids)
        self._push_cache_queue(raw_attachments)
        return self.__parse_attachments(raw_attachments)

    def __retrieve_bugs_from_cache(self):
        def recover_extra_data(cache_items):
            try:
                comments = self.__parse_comments(next(cache_items))
                histories = self.__parse_histories(next(cache_items))
                attachments = self.__parse_attachments(next(cache_items))
            except StopIteration:
                # Fatal error. The code should not reach here.
                # Cache should had stored an activity item per parsed bug.
                cause = "cache is exhausted but more items were expected"
                raise CacheError(cause=cause)
            return comments, histories, attachments

        cache_items = self.cache.retrieve()

        while True:
            try:
                raw_bugs = next(cache_items)
            except StopIteration:
                break

            bugs = json.loads(raw_bugs)['bugs']

            if len(bugs) == 0:
                continue

            comments, histories, attachments = recover_extra_data(cache_items)

            while bugs:
                bug = bugs.pop(0)
                bug_id = str(bug['id'])

                try:
                    bug['comments'] = comments.pop(bug_id)
                    bug['history'] = histories.pop(bug_id)
                    bug['attachments'] = attachments.pop(bug_id)
                except KeyError:
                    # Fatal error. Keys must exist.
                    cause = "invalid cached data, bug id %s not found" % bug_id
                    raise CacheError(cause=cause)

                yield bug

                if bugs and (len(comments) + len(histories) + len(attachments) == 0):
                    comments, histories, attachments = recover_extra_data(cache_items)

    @staticmethod
    def __parse_comments(raw_comments):
        contents = json.loads(raw_comments)['bugs']
        comments = {k : v['comments'] for k, v in contents.items()}
        return comments

    @staticmethod
    def __parse_histories(raw_histories):
        contents = json.loads(raw_histories)['bugs']
        history = {str(c['id']) : c['history'] for c in contents}
        return history

    @staticmethod
    def __parse_attachments(raw_attachments):
        contents = json.loads(raw_attachments)['bugs']
        attachments = {k : v for k, v in contents.items()}
        return attachments

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
        """Extracts the identifier from a Bugzilla item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a Bugzilla item.

        The timestamp used is extracted from 'last_change_time' field.
        This date is converted to UNIX timestamp format taking into
        account the timezone of the date.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['last_change_time']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Bugzilla item.

        This backend only generates one type of item which is
        'bug'.
        """
        return 'bug'


class BugzillaRESTClient:
    """Bugzilla REST API client.

    This class implements a simple client to retrieve distinct
    kind of data from a Bugzilla > 5.0 repository using its
    REST API.

    When `user` and `password` parameters are given it logs in
    the server. Further requests will use the token obtained
    during the sign in phase.

    :param base_url: URL of the Bugzilla server
    :param user: Bugzilla user
    :param password: user password
    :param api_token: api token for user; when this is provided
        `user` and `password` parameters will be ignored

    :raises BackendError: when an error occurs initilizing the
        client
    """
    URL = "%(base)s/rest/%(resource)s"

    # API resources
    RBUG = 'bug'
    RATTACHMENT = 'attachment'
    RCOMMENT = 'comment'
    RHISTORY = 'history'
    RLOGIN = 'login'

    # Resource parameters
    PBUGZILLA_LOGIN = 'login'
    PBUGZILLA_PASSWORD = 'password'
    PBUGZILLA_TOKEN = 'token'
    PIDS = 'ids'
    PLAST_CHANGE_TIME = 'last_change_time'
    PLIMIT = 'limit'
    POFFSET = 'offset'
    PORDER = 'order'
    PINCLUDE_FIELDS = 'include_fields'
    PEXCLUDE_FIELDS = 'exclude_fields'

    # Predefined values
    VCHANGE_DATE_ORDER = 'changeddate'
    VINCLUDE_ALL = '_all'
    VEXCLUDE_ATTCH_DATA = 'data'

    def __init__(self, base_url, user=None, password=None, api_token=None):
        self.base_url = base_url
        self.api_token = api_token if api_token else None

        if user is not None and password is not None:
            self.login(user, password)

    def login(self, user, password):
        """Authenticate a user in the server.

        :param user: Bugzilla user
        :param password: user password
        """
        params = {
            self.PBUGZILLA_LOGIN : user,
            self.PBUGZILLA_PASSWORD : password
        }

        try:
            r = self.call(self.RLOGIN, params)
        except requests.exceptions.HTTPError as e:
            cause = ("Bugzilla REST client could not authenticate user %s. "
                "See exception: %s") % (user, str(e))
            raise BackendError(cause=cause)

        data = json.loads(r)
        self.api_token = data['token']

    def bugs(self, from_date=DEFAULT_DATETIME, offset=None, max_bugs=MAX_BUGS):
        """Get the information of a list of bugs.

        :param from_date: retrieve bugs that where updated from that date;
            dates are converted to UTC
        :param offset: starting position for the search; i.e to return 11th
            element, set this value to 10.
        :param max_bugs: maximum number of bugs to reteurn per query
        """
        date = datetime_to_utc(from_date)
        date = date.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            self.PLAST_CHANGE_TIME : date,
            self.PLIMIT : max_bugs,
            self.PORDER : self.VCHANGE_DATE_ORDER,
            self.PINCLUDE_FIELDS : self.VINCLUDE_ALL
        }

        if offset:
            params[self.POFFSET] = offset

        response = self.call(self.RBUG, params)

        return response

    def comments(self, *bug_ids):
        """Get the comments of the given bugs.

        :param bug_ids: list of bug identifiers
        """
        # Hack. The first value must be a valid bug id
        resource = urljoin(self.RBUG, bug_ids[0], self.RCOMMENT)

        params = {
            self.PIDS : bug_ids
        }

        response = self.call(resource, params)

        return response

    def history(self, *bug_ids):
        """Get the history of the given bugs.

        :param bug_ids: list of bug identifiers
        """
        resource = urljoin(self.RBUG, bug_ids[0], self.RHISTORY)

        params = {
            self.PIDS : bug_ids
        }

        response = self.call(resource, params)

        return response

    def attachments(self, *bug_ids):
        """Get the attachments of the given bugs.

        :param bug_id: list of bug identifiers
        """
        resource = urljoin(self.RBUG, bug_ids[0], self.RATTACHMENT)

        params = {
            self.PIDS : bug_ids,
            self.PEXCLUDE_FIELDS : self.VEXCLUDE_ATTCH_DATA
        }

        response = self.call(resource, params)

        return response

    def call(self, resource, params):
        """Retrive the given resource.

        :param resource: resource to retrieve
        :param params: dict with the HTTP parameters needed to retrieve
            the given resource
        """
        url = self.URL % {'base' : self.base_url, 'resource' : resource}

        if self.api_token:
            params[self.PBUGZILLA_TOKEN] = self.api_token

        logger.debug("Bugzilla REST client requests: %s params: %s",
                     resource, str(params))

        r = requests.get(url, params=params)
        r.raise_for_status()

        return r.text


class BugzillaRESTCommand(BackendCommand):
    """Class to run BugzillaREST backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.url = self.parsed_args.url
        self.backend_user = self.parsed_args.backend_user
        self.backend_password = self.parsed_args.backend_password
        self.backend_token = self.parsed_args.backend_token
        self.max_bugs = self.parsed_args.max_bugs
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

        self.backend = BugzillaREST(self.url,
                                    user=self.backend_user,
                                    password=self.backend_password,
                                    api_token=self.backend_token,
                                    max_bugs=self.max_bugs,
                                    tag=self.tag,
                                    cache=cache)

    def run(self):
        """Fetch and print the bugs.

        This method runs the backend to fetch the bugs from the given
        repository. Bugs are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            bugs = self.backend.fetch_from_cache()
        else:
            bugs = self.backend.fetch(from_date=self.from_date)

        try:
            for bug in bugs:
                obj = json.dumps(bug, indent=4, sort_keys=True)
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
        """Returns the BugzillaREST argument parser."""

        parser = super().create_argument_parser()

        # BugzillaREST options
        group = parser.add_argument_group('Bugzilla REST arguments')
        group.add_argument('--max-bugs', dest='max_bugs',
                           type=int, default=MAX_BUGS,
                           help="Maximum number of bugs requested on the same query")

        # Required arguments
        parser.add_argument('url',
                            help="URL of the Bugzilla server")

        return parser

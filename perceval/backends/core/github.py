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
#     Alvaro del Castillo San Felix <acs@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Alberto Martín <alberto.martin@bitergia.com>
#

import json
import logging
import os.path
import time

import requests

from ...backend import Backend, BackendCommand, metadata
from ...cache import Cache
from ...errors import CacheError, BaseError
from ...utils import (DEFAULT_DATETIME,
                      datetime_to_utc,
                      str_to_datetime,
                      urljoin)


GITHUB_URL = "https://github.com/"
GITHUB_API_URL = "https://api.github.com"

# Range before sleeping until rate limit reset
MIN_RATE_LIMIT = 10
MAX_RATE_LIMIT = 500


logger = logging.getLogger(__name__)


class RateLimitError(BaseError):

    message = "%(cause)s %(seconds_to_reset)s seconds for rate reset"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._seconds_to_reset = kwargs['seconds_to_reset']

    @property
    def seconds_to_reset(self):
        return self._seconds_to_reset


class GitHub(Backend):
    """GitHub backend for Perceval.

    This class allows the fetch the issues stored in GitHub
    repository.

    :param owner: GitHub owener
    :param repository: GitHub repository from the owner
    :param backend_token: GitHub auth token to access the API
    :param base_url: GitHub URL in enterprise edition case;
        when no value is set the backend will be fetch the data
        from the GitHub public site.
    :param tag: label used to mark the data
    :param cache: use issues already retrieved in cache
    :param sleep_for_rate: sleep until rate limit is reset
    :param min_rate_to_sleep: minimun rate needed to sleep until
         it will be reset
    """
    version = '0.5.0'

    def __init__(self, owner=None, repository=None,
                 backend_token=None, base_url=None,
                 tag=None, cache=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT):
        origin = base_url if base_url else GITHUB_URL
        origin = urljoin(origin, owner, repository)

        super().__init__(origin, tag=tag, cache=cache)
        self.owner = owner
        self.repository = repository
        self.backend_token = backend_token
        self.client = GitHubClient(owner, repository, backend_token, base_url,
                                   sleep_for_rate, min_rate_to_sleep)
        self._users = {}  # internal users cache

    def __get_user(self, login):
        """ Get user and org data for the login """

        user = {}

        if not login:
            return user

        user_raw = self.client.get_user(login)
        user = json.loads(user_raw)
        self._push_cache_queue(user_raw)
        user_orgs_raw = \
            self.client.get_user_orgs(login)
        user['organizations'] = json.loads(user_orgs_raw)
        self._push_cache_queue(user_orgs_raw)
        self._flush_cache_queue()

        return user

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME):
        """Fetch the issues from the repository.

        The method retrieves, from a GitHub repository, the issues
        updated since the given date.

        :param from_date: obtain issues updated since this date

        :returns: a generator of issues
        """

        self._purge_cache_queue()

        from_date = datetime_to_utc(from_date)

        issues_groups = self.client.get_issues(from_date)

        for raw_issues in issues_groups:
            self._push_cache_queue(raw_issues)
            self._flush_cache_queue()
            issues = json.loads(raw_issues)
            for issue in issues:
                for field in ['user', 'assignee']:
                    if issue[field]:
                        issue[field+"_data"] = self.__get_user(issue[field]['login'])
                    else:
                        issue[field+"_data"] = {}
                yield issue

    @metadata
    def fetch_from_cache(self):
        """Fetch the issues from the cache.

        It returns the issues stored in the cache object provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of items

        :raises CacheError: raised when an error occurs accessing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        issues = None

        while True:
            try:
                raw_item = next(cache_items)
            except StopIteration:
                if issues:
                    for issue in self.__build_issues(issues):
                        yield issue
                break

            item = json.loads(raw_item)

            if 'login' in item:
                try:
                    raw_orgs = next(cache_items)
                except StopIteration:
                    # Fatal error. Cache should had stored an organizations item
                    # per parsed user.
                    cause = "cache is exhausted but more items were expected"
                    raise CacheError(cause=cause)

                item['organizations'] = json.loads(raw_orgs)
                self._users[item['login']] = item
                continue

            # A new set of issues has been read. It means we already
            # have the enough information to build and return the
            # previous set
            if issues:
                for issue in self.__build_issues(issues):
                    yield issue

            # Next issues to parse
            issues = item

    def __build_issues(self, issues):
        for issue in issues:
            for field in ['user', 'assignee']:
                issue[field + '_data'] = {}
                if issue[field]:
                    issue[field + '_data'] = \
                        self._users[issue[field]['login']]
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
        """Extracts the identifier from a GitHub item."""

        return str(item['id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts the update time from a GitHub item.

        The timestamp used is extracted from 'updated_at' field.
        This date is converted to UNIX timestamp format. As GitHub
        dates are in UTC the conversion is straightforward.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['updated_at']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a GitHub item.

        This backend only generates one type of item which is
        'issue'.
        """
        return 'issue'


class GitHubClient:
    """ Client for retieving information from GitHub API """

    _users = {}       # users cache
    _users_orgs = {}  # users orgs cache

    def __init__(self, owner, repository, token, base_url=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT):
        self.owner = owner
        self.repository = repository
        self.token = token
        self.base_url = base_url
        self.rate_limit = None
        self.rate_limit_reset_ts = None
        self.sleep_for_rate = sleep_for_rate

        if min_rate_to_sleep > MAX_RATE_LIMIT:
            msg = "Minimum rate to sleep value exceeded (%d)."
            msg += "High values might cause the client to sleep forever."
            msg += "Reset to %d."
            logger.warning(msg, min_rate_to_sleep, MAX_RATE_LIMIT)

        self.min_rate_to_sleep = min(min_rate_to_sleep, MAX_RATE_LIMIT)

    def __get_url(self):
        github_api = GITHUB_API_URL
        if self.base_url:
            github_api = self.base_url
        github_api_repos = github_api + "/repos"
        url_repo = github_api_repos + "/" + self.owner + "/" + self.repository
        return url_repo

    def __get_issues_url(self, startdate=None):
        url_issues = self.__get_url() + "/issues"
        return url_issues

    def __get_payload(self, startdate=None):
        # 100 in other items. 20 for pull requests. 30 issues
        payload = {'per_page': 30,
                   'state': 'all',
                   'sort': 'updated',
                   'direction': 'asc'}
        if startdate:
            startdate = startdate.isoformat()
            payload['since'] = startdate
        return payload

    def __get_headers(self):
        if self.token:
            headers = {'Authorization': 'token ' + self.token}
            return headers

    def __send_request(self, url, params=None, headers=None):
        """ GET HTTP caring of rate limit """

        if self.rate_limit is not None and self.rate_limit <= self.min_rate_to_sleep:
            seconds_to_reset = self.rate_limit_reset_ts - int(time.time()) + 1
            cause = "GitHub rate limit exhausted."
            if self.sleep_for_rate:
                logger.info("%s Waiting %i secs for rate limit reset.", cause, seconds_to_reset)
                time.sleep(seconds_to_reset)
            else:
                raise RateLimitError(cause=cause, seconds_to_reset=seconds_to_reset)

        r = requests.get(url, params=params, headers=headers)
        r.raise_for_status()
        self.rate_limit = int(r.headers['X-RateLimit-Remaining'])
        self.rate_limit_reset_ts = int(r.headers['X-RateLimit-Reset'])
        logger.debug("Rate limit: %s" % (self.rate_limit))
        return r

    def get_issues(self, start=None):
        """ Return the items from github API using links pagination """

        page = 0  # current page
        last_page = None  # last page
        url_next = self.__get_issues_url(start)

        logger.debug("Get GitHub issues from " + url_next)
        r = self.__send_request(url_next, self.__get_payload(start),
                              self.__get_headers())
        issues = r.text
        page += 1

        if 'last' in r.links:
            last_url = r.links['last']['url']
            last_page = last_url.split('&page=')[1].split('&')[0]
            last_page = int(last_page)
            logger.debug("Page: %i/%i" % (page, last_page))

        while issues:
            yield issues

            issues = None

            if 'next' in r.links:
                url_next = r.links['next']['url']  # Loving requests :)
                r = self.__send_request(url_next, self.__get_payload(start), self.__get_headers())
                page += 1
                issues = r.text
                logger.debug("Page: %i/%i" % (page, last_page))

    def get_user(self, login):
        user = None

        if login in self._users:
            return self._users[login]

        url_user = GITHUB_API_URL + "/users/" + login

        logging.info("Getting info for %s" % (url_user))
        r = self.__send_request(url_user, headers=self.__get_headers())
        user = r.text
        self._users[login] = user

        return user

    def get_user_orgs(self, login):
        # Get the public organizations also

        if login in self._users_orgs:
            return self._users_orgs[login]

        url = GITHUB_API_URL + "/users/" + login + "/orgs"
        r = self.__send_request(url, headers=self.__get_headers())
        orgs = r.text

        self._users_orgs[login] = orgs

        return orgs


class GitHubCommand(BackendCommand):
    """Class to run GitHub backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.owner = self.parsed_args.owner
        self.repository = self.parsed_args.repository
        self.backend_token = self.parsed_args.backend_token
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.tag = self.parsed_args.tag
        self.outfile = self.parsed_args.outfile
        self.sleep_for_rate = self.parsed_args.sleep_for_rate
        self.min_rate_to_sleep = self.parsed_args.min_rate_to_sleep

        if not self.parsed_args.no_cache:
            if not self.parsed_args.cache_path:
                base_path = os.path.expanduser('~/.perceval/cache/')
            else:
                base_path = self.parsed_args.cache_path
            # TODO: add get_id for backend to return the unique id
            cache_path = os.path.join(base_path, self.owner + "_" +
                                      self.repository)

            cache = Cache(cache_path)

            if self.parsed_args.clean_cache:
                cache.clean()
            else:
                cache.backup()
        else:
            cache = None

        self.backend = GitHub(self.owner, self.repository,
                              backend_token=self.backend_token,
                              tag=self.tag, cache=cache,
                              sleep_for_rate=self.sleep_for_rate,
                              min_rate_to_sleep=self.min_rate_to_sleep)

    def run(self):
        """Fetch and print the issues.

        This method runs the backend to fetch the issues from the given
        repository. Bugs are converted to JSON objects and printed to the
        defined output.
        """
        if self.parsed_args.fetch_cache:
            issues = self.backend.fetch_from_cache()
        else:
            issues = self.backend.fetch(from_date=self.from_date)

        try:
            for issue in issues:
                obj = json.dumps(issue, indent=4, sort_keys=True)
                # self.outfile.write(issue['url']+"\n")
                self.outfile.write(obj)
                self.outfile.write('\n')
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(str(e.response.json()))
        except IOError as e:
            raise RuntimeError(str(e))
        except Exception as e:
            if self.backend.cache:
                self.backend.cache.recover()
            raise RuntimeError(str(e))

    @classmethod
    def create_argument_parser(cls):
        """Returns the GitHub argument parser."""

        parser = super().create_argument_parser()

        # GitHub options
        group = parser.add_argument_group('GitHub arguments')

        group.add_argument("--owner", required=True,
                           help="GitHub owner")
        group.add_argument("--repository", required=True,
                           help="GitHub repository")
        group.add_argument("--sleep-for-rate", dest='sleep_for_rate',
                           action='store_true',
                           help="sleep for getting more rate")
        group.add_argument("--min-rate-to-sleep", dest='min_rate_to_sleep',
                           default=MIN_RATE_LIMIT, type=int,
                           help="sleep until reset when the rate limit reaches this value")

        return parser

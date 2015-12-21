# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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
#   Alvaro del Castillo San Felix <acs@bitergia.com>
#

'''GitHub backend for Perseval'''


import json
import logging
import os.path

import requests

from ..backend import Backend, BackendCommand
from ..cache import Cache
from ..errors import CacheError
from ..utils import DEFAULT_DATETIME, str_to_datetime


class GitHub(Backend):

    name = "github"
    users = {}

    def __init__(self, owner=None, repository=None, token=None,
                 cache=None):
        super().__init__(cache=cache)
        self.owner = owner
        self.repository = repository
        self.client = GitHubClient(owner, repository, token)

    def get_id(self):

        _id = "%s_%s" % (self.owner, self.repository)

        return _id.lower()

    def get_field_unique_id(self):
        return "id"

    def fetch(self, from_date=DEFAULT_DATETIME):

        self._purge_cache_queue()

        issues = self.client.get_issues(from_date)

        self._push_cache_queue(issues)
        self._flush_cache_queue()

        while issues:
            issue = issues.pop(0)
            yield issue

            if not issues:
                issues = self.client.get_issues()
                if issues and len(issues)>0:
                    self._push_cache_queue(issues)
                    self._flush_cache_queue()

    def fetch_from_cache(self):
        """Fetch the bugs from the cache.

        It returns the bugs stored in the cache object provided during
        the initialization of the object. If this method is called but
        no cache object was provided, the method will raise a `CacheError`
        exception.

        :returns: a generator of items

        :raises CacheError: raised when an error occurs accesing the
            cache
        """
        if not self.cache:
            raise CacheError(cause="cache instance was not provided")

        cache_items = self.cache.retrieve()

        for issues in cache_items:
            for issue in issues:
                yield issue


class GitHubClient:

    def __init__(self, owner, repository, token):
        self.owner = owner
        self.repository = repository
        self.auth_token = token
        self.last_page = self.page = 1  # pagination in items downloading

    def _get_url(self):
        github_api = "https://api.github.com"
        github_api_repos = github_api + "/repos"
        url_repo = github_api_repos + "/" + self.owner + "/" + self.repository
        return url_repo

    def get_issues_url(self, startdate=None):
        # 100 in other items. 20 for pull requests. 30 issues
        github_per_page = 30

        url_issues = self._get_url() + "/issues"

        url_params = "?per_page=" + str(github_per_page)
        url_params += "&state=all"  # open and close pull requests
        url_params += "&sort=updated"  # sort by last updated
        url_params += "&direction=asc"  # first older pull request
        if startdate:
            startdate = startdate.isoformat()
            url_params += "&since=" + startdate

        url = url_issues + url_params

        return url

    def get_issues(self, start=None):
        ''' Return the items from github API in iterations '''

        if self.page == 1:
            self.url_next = self.get_issues_url(start)

        else:
            if not self.url_next:
                self.page = 1
                return

        logging.debug("Get GitHub issues from " + self.url_next)
        r = requests.get(self.url_next, verify=False,
                         headers={'Authorization': 'token ' + self.auth_token})
        issues = r.json()

        logging.debug("Rate limit: %s" %
                      (r.headers['X-RateLimit-Remaining']))

        self.url_next = None
        if 'next' in r.links:
            self.url_next = r.links['next']['url']  # Loving requests :)

        if self.last_page == 1:
            if 'last' in r.links:
                last_url = r.links['last']['url']
                self.last_page = last_url.split('&page=')[1].split('&')[0]
                self.last_page = int(self.last_page)

        logging.debug("Page: %i/%i" % (self.page, self.last_page))

        self.page += 1

        return issues


class GitHubCommand(BackendCommand):
    """Class to run GitHub backend from the command line."""

    def __init__(self, *args):
        super().__init__(*args)

        self.owner = self.parsed_args.owner
        self.repository = self.parsed_args.repository
        self.token = self.parsed_args.token
        self.from_date = str_to_datetime(self.parsed_args.from_date)
        self.outfile = self.parsed_args.outfile

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
                              self.token, cache=cache)

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
                self.outfile.write(bug['url']+"\n")
                # obj = json.dumps(bug, indent=4, sort_keys=True)
                # self.outfile.write(obj)
                # self.outfile.write('\n')
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
                           help="github owner")
        group.add_argument("--repository", required=True,
                           help="github repository")
        group.add_argument("--token", required=True,
                           help="github access token")

        return parser

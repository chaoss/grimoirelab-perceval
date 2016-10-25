#!/usr/bin/env python3
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
#     Quan Zhou <quan@bitergia.com>
#

import argparse
import datetime
import json
import shutil
import sys
import tempfile
import time
import unittest

import httpretty
import requests

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.github import GitHub, GitHubCommand, GitHubClient, RateLimitError


GITHUB_API_URL = "https://api.github.com"
GITHUB_ISSUES_URL = GITHUB_API_URL + "/repos/zhquan_example/repo/issues"
GITHUB_USER_URL = GITHUB_API_URL + "/users/zhquan_example"
GITHUB_ORGS_URL = GITHUB_API_URL + "/users/zhquan_example/orgs"
GITHUB_COMMAND_URL = GITHUB_API_URL + "/command"


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestGitHubBackend(unittest.TestCase):
    """ GitHub backend tests """

    def test_initialization(self):
        """Test whether attributes are initializated"""

        github = GitHub('zhquan_example', 'repo', 'aaa', tag='test')

        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'test')

        # When tag is empty or None it will be set to
        # the value in origin
        github = GitHub('zhquan_example', 'repo', 'aaa')
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')

        github = GitHub('zhquan_example', 'repo', 'aaa', tag='')
        self.assertEqual(github.owner, 'zhquan_example')
        self.assertEqual(github.repository, 'repo')
        self.assertEqual(github.origin, 'https://github.com/zhquan_example/repo')
        self.assertEqual(github.tag, 'https://github.com/zhquan_example/repo')

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(GitHub.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(GitHub.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """ Test whether a list of issues is returned """

        body = read_file('data/github_request')
        login = read_file('data/github_login')
        orgs = read_file('data/github_orgs')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_USER_URL,
                              body=login, status=200,
                              forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                              })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        github = GitHub("zhquan_example", "repo", "aaa")
        issues = [issues for issues in github.fetch()]

        self.assertEqual(len(issues), 1)

        expected = json.loads(read_file('data/github_request_expected'))
        self.assertEqual(issues[0]['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issues[0]['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(issues[0]['updated_on'], 1454328801.0)
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], 'https://github.com/zhquan_example/repo')
        self.assertDictEqual(issues[0]['data'], expected)

    @httpretty.activate
    def test_fetch_more_issues(self):
        """ Test when return two issues """

        login = read_file('data/github_login')
        issue_1 = read_file('data/github_issue_1')
        issue_2 = read_file('data/github_issue_2')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '5',
                                    'Link': '<'+GITHUB_ISSUES_URL+'/?&page=2>; rel="next", <'+GITHUB_ISSUES_URL+'/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL+'/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '5'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_USER_URL,
                              body=login, status=200,
                              forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '5'
                              })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '5'
                               })

        github = GitHub("zhquan_example", "repo", "aaa")
        issues = [issues for issues in github.fetch()]

        self.assertEqual(len(issues), 2)

        expected_1 = json.loads(read_file('data/github_issue_expected_1'))
        self.assertEqual(issues[0]['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issues[0]['uuid'], '58c073fd2a388c44043b9cc197c73c5c540270ac')
        self.assertEqual(issues[0]['updated_on'], 1458035782.0)
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], 'https://github.com/zhquan_example/repo')
        self.assertDictEqual(issues[0]['data'], expected_1)

        expected_2 = json.loads(read_file('data/github_issue_expected_2'))
        self.assertEqual(issues[1]['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issues[1]['uuid'], '4236619ac2073491640f1698b5c4e169895aaf69')
        self.assertEqual(issues[1]['updated_on'], 1458054569.0)
        self.assertEqual(issues[1]['category'], 'issue')
        self.assertEqual(issues[1]['tag'], 'https://github.com/zhquan_example/repo')
        self.assertDictEqual(issues[1]['data'], expected_2)

    @httpretty.activate
    def test_fetch_from_date(self):
        """ Test when return from date """

        login = read_file('data/github_login')
        body = read_file('data/github_issue_2')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_USER_URL,
                              body=login, status=200,
                              forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                              })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        from_date = datetime.datetime(2016, 3, 1)
        github = GitHub("zhquan_example", "repo", "aaa")

        issues = [issues for issues in github.fetch(from_date=from_date)]
        self.assertEqual(len(issues), 1)

        expected = json.loads(read_file('data/github_issue_expected_2'))
        self.assertEqual(issues[0]['origin'], 'https://github.com/zhquan_example/repo')
        self.assertEqual(issues[0]['uuid'], '4236619ac2073491640f1698b5c4e169895aaf69')
        self.assertEqual(issues[0]['updated_on'], 1458054569.0)
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], 'https://github.com/zhquan_example/repo')
        self.assertDictEqual(issues[0]['data'], expected)

    @httpretty.activate
    def test_feth_empty(self):
        """ Test when return empty """

        body = ""
        login = read_file('data/github_login')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_USER_URL,
                              body=login, status=200,
                              forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                              })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        from_date = datetime.datetime(2016, 1, 1)
        github = GitHub("zhquan_example", "repo", "aaa")

        issues = [issues for issues in github.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 0)


class TestGitHubBackendCache(unittest.TestCase):
    """GitHub backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """ Test whether a list of issues is returned from cache """

        body = read_file('data/github_request')
        login = read_file('data/github_login')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_USER_URL,
                              body=login, status=200,
                              forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': '15'
                              })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        # First, we fetch the bugs from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        github = GitHub("zhquan_example", "repo", "aaa", cache=cache)

        issues = [issues for issues in github.fetch()]

        # Now, we get the bugs from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cache_issues = [cache_issues for cache_issues in github.fetch_from_cache()]

        del issues[0]['timestamp']
        del cache_issues[0]['timestamp']
        self.assertDictEqual(issues[0], cache_issues[0])
        self.assertEqual(len(issues), len(cache_issues))

    def test_fetch_from_empty_cache(self):
        """Test if there are not any issues returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        github = GitHub("zhquan_example", "repo", "aaa", cache=cache)

        cache_issues = [cache_issues for cache_issues in github.fetch_from_cache()]

        self.assertEqual(len(cache_issues), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        github = GitHub("zhquan_example", "repo", "aaa")

        with self.assertRaises(CacheError):
            _ = [cache_issues for cache_issues in github.fetch_from_cache()]


class TestGitHubClient(unittest.TestCase):
    """ GitHub API client tests """

    @httpretty.activate
    def test_get_issues(self):
        """ Test get_issues API call """

        issue = read_file('data/github_request')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '5',
                                    'X-RateLimit-Reset': '5'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
        raw_issues = [issues for issues in client.get_issues()]
        self.assertEqual(len(raw_issues), 1)
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
                     'per_page': ['30'],
                     'state': ['all'],
                     'direction': ['asc'],
                     'sort': ['updated']
                   }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_from_date_issues(self):
        """ Test get_from_issues API call """

        issue = read_file('data/github_request_from_2016_03_01')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        from_date = datetime.datetime(2016, 3, 1)
        client = GitHubClient("zhquan_example", "repo", "aaa", None)

        raw_issues = [issues for issues in client.get_issues(from_date)]
        self.assertEqual(len(raw_issues), 1)
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
                     'per_page': ['30'],
                     'state': ['all'],
                     'direction': ['asc'],
                     'since': ['2016-03-01T00:00:00'],
                     'sort': ['updated']
                   }
        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_page_issues(self):
        """ Test get_page_issue API call """

        issue_1 = read_file('data/github_issue_1')
        issue_2 = read_file('data/github_issue_2')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15',
                                    'Link': '<'+GITHUB_ISSUES_URL+'/?&page=2>; rel="next", <'+GITHUB_ISSUES_URL+'/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL+'/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa")

        issues = [issues for issues in client.get_issues()]

        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0], issue_1)
        self.assertEqual(issues[1], issue_2)

        # Check requests
        expected = {
                     'per_page': ['30'],
                     'page': ['2'],
                     'state': ['all'],
                     'direction': ['asc'],
                     'sort': ['updated']
                   }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_empty_issues(self):
        """ Test when issue is empty API call """

        issue = read_file('data/github_empty_request')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)

        raw_issues = [issues for issues in client.get_issues()]
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
                     'per_page': ['30'],
                     'state': ['all'],
                     'direction': ['asc'],
                     'sort': ['updated']
                   }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_user(self):
        """ Test get_user API call """

        login = read_file('data/github_login')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_USER_URL,
                               body=login, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
        response = client.get_user("zhquan_example")
        self.assertEqual(response, login)

    @httpretty.activate
    def test_get_user_orgs(self):
        """ Test get_user_orgs API call """

        orgs = read_file('data/github_orgs')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
        response = client.get_user_orgs("zhquan_example")

        self.assertEqual(response, orgs)

    @httpretty.activate
    def test_http_wrong_status(self):
        """Test if a error is raised when the http status was not 200"""

        issue = ""

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=500,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in client.get_issues()]

        # Check requests
        expected = {
                     'per_page': ['30'],
                     'state': ['all'],
                     'direction': ['asc'],
                     'sort': ['updated']
                   }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_sleep_for_rate(self):
        """ Test get_page_issue API call """

        issue_1 = read_file('data/github_empty_request')
        issue_2 = read_file('data/github_empty_request')

        wait = 1
        reset = int(time.time() + wait)

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '0',
                                    'X-RateLimit-Reset': reset,
                                    'Link': '<'+GITHUB_ISSUES_URL+'/?&page=2>; rel="next", <'+GITHUB_ISSUES_URL+'/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL+'/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '20',
                                    'X-RateLimit-Reset': '15'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", sleep_for_rate=True)

        before = int(time.time())
        issues = [issues for issues in client.get_issues()]
        after = int(time.time())
        dif = after-before

        self.assertGreaterEqual(dif, wait)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0], issue_1)
        self.assertEqual(issues[1], issue_2)

        # Check requests
        expected = {
                     'per_page': ['30'],
                     'page': ['2'],
                     'state': ['all'],
                     'direction': ['asc'],
                     'sort': ['updated']
                   }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_rate_limit_error(self):
        """ Test get_page_issue API call """

        issue = read_file('data/github_empty_request')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '0',
                                    'X-RateLimit-Reset': '0',
                                    'Link': '<'+GITHUB_ISSUES_URL+'/?&page=2>; rel="next", <'+GITHUB_ISSUES_URL+'/?&page=3>; rel="last"'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", sleep_for_rate=False)

        with self.assertRaises(RateLimitError):
            _ = [issues for issues in client.get_issues()]

        # Check requests
        expected = {
                     'per_page': ['30'],
                     'state': ['all'],
                     'direction': ['asc'],
                     'sort': ['updated']
                   }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

class TestGitHubCommand(unittest.TestCase):
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--owner', 'zhquan_example',
                '--repository', 'repo',
                '--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--tag', 'test']

        cmd = GitHubCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.owner, "zhquan_example")
        self.assertEqual(cmd.parsed_args.repository, "repo")
        self.assertEqual(cmd.parsed_args.sleep_for_rate, True)
        self.assertEqual(cmd.parsed_args.min_rate_to_sleep, 1)
        self.assertEqual(cmd.parsed_args.tag, 'test')


    @httpretty.activate
    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = GitHubCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

if __name__ == "__main__":
    unittest.main(warnings='ignore')

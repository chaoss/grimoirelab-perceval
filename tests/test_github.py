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
import shutil
import sys
import tempfile
import unittest

import httpretty
import requests

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import BackendError, CacheError, ParseError
from perceval.backends.github import GitHub, GitHubCommand, GitHubClient


GITHUB_API_URL = "https://api.github.com"
GITHUB_ISSUES_URL = GITHUB_API_URL + "/repos/zhquan_example/repo/issues"
GITHUB_LOGIN_URL = GITHUB_API_URL + "/users/zhquan_example"
GITHUB_ORGS_URL = GITHUB_API_URL + "/users/zhquan_example/orgs"
GITHUB_COMMAND_URL = GITHUB_API_URL + "/command"


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class TestGitHubBackend(unittest.TestCase):
    """ GitHub backend tests """

    @httpretty.activate
    def test_fetch(self):
        """ Test whether a list of issues is returned """

        command = ""
        body = read_file('data/github_request')
        login = read_file('data/github_login')
        orgs = read_file('data/github_orgs')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_COMMAND_URL,
                               body=command, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_LOGIN_URL,
                              body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200)

        github = GitHub("zhquan_example", "repo", "aaa", None)
        issues = [issues for issues in github.fetch()]

        # Check requests
        expected = {
            "backend_name": "GitHub",
            "data": {
                "user": {
                    "organizations_url": "https://api.github.com/users/zhquan_example/orgs",
                    "login": "zhquan_example",
                    "url": "https://api.github.com/users/zhquan_example",
                    "id": 1
                },
                "repository_url": "https://api.github.com/repos/zhquan_example/repo",
                "title": "Title 1",
                "updated_at": "2016-02-01T12:13:21Z",
                "url": "https://api.github.com/repos/zhquan_example/repo/issues/1",
                "body": "Body",
                "user_data": {
                    "type": "User",
                    "organizations_url": "https://api.github.com/users/zhquan_example/orgs",
                    "repos_url": "https://api.github.com/users/zhquan_example/repos",
                    "organizations": [
                        {
                            "login": "Orgs_1",
                            "members_url": "https://api.github.com/orgs/Orgs_1/members{/member}",
                            "avatar_url": "",
                            "events_url": "https://api.github.com/orgs/Orgs_1/events",
                            "hooks_url": "https://api.github.com/orgs/Orgs_1/hooks",
                            "id": 1,
                            "public_members_url": "https://api.github.com/orgs/Orgs_1/public_members{/member}",
                            "repos_url": "https://api.github.com/orgs/Orgs_1/repos",
                            "issues_url": "https://api.github.com/orgs/Orgs_1/issues",
                            "url": "https://api.github.com/orgs/Orgs_1",
                            "description": None
                        },
                        {
                            "login": "Orgs_2",
                            "members_url": "https://api.github.com/orgs/Orgs_2/members{/member}",
                            "avatar_url": "",
                            "events_url": "https://api.github.com/orgs/Orgs_2/events",
                            "hooks_url": "https://api.github.com/orgs/Orgs_2/hooks",
                            "id": 2,
                            "public_members_url": "https://api.github.com/orgs/Orgs_2/public_members{/member}",
                            "repos_url": "https://api.github.com/orgs/Orgs_2/repos",
                            "issues_url": "https://api.github.com/orgs/Orgs_2/issues",
                            "url": "https://api.github.com/orgs/Orgs_2",
                            "description": None
                        }
                    ],
                    "name": "zhquan_example",
                    "url": "https://api.github.com/users/zhquan_example",
                    "created_at": "2016-01-01T00:00:00Z",
                    "updated_at": "2016-01-01T01:00:00Z",
                    "login": "zhquan_example",
                    "id": 1
                },
                "created_at": "2016-02-01T07:10:24Z",
                "closed_at": "2016-02-01T12:13:21Z",
                "id": 1
            },
            "perceval_version": "0.1.0",
            "updated_on": 1454328801,
            "origin": "https://github.com/zhquan_example/repo",
            "uuid": "58c073fd2a388c44043b9cc197c73c5c540270ac",
            "backend_version": "0.1.0"
        }

        for key in expected:
            if (key == "data"):
                for data_key in expected[key]:
                    if (data_key == "user"):
                        for user_key in expected[key][data_key]:
                            self.assertEqual(issues[0][key][data_key][user_key], expected[key][data_key][user_key])
                    elif (data_key == "user_data"):
                        for user_key in expected[key][data_key]:
                            self.assertEqual(issues[0][key][data_key][user_key], expected[key][data_key][user_key])
                    else:
                        self.assertEqual(issues[0][key][data_key], expected[key][data_key])
            else:
                self.assertEqual(issues[0][key], expected[key])

    @httpretty.activate
    def test_fetch_more_issues(self):
        """ Test when return two issues """

        command = ""
        login = read_file('data/github_login')
        issue_1 = read_file('data/github_issue_1')
        issue_2 = read_file('data/github_issue_2')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_COMMAND_URL,
                               body=command, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986',
                                    'Link': '<'+GITHUB_ISSUES_URL+'/?&page=2>; rel="next", <'+GITHUB_ISSUES_URL+'/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL+'/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_LOGIN_URL,
                              body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200)

        github = GitHub("zhquan_example", "repo", "aaa", None)
        issues = [issues for issues in github.fetch()]

        self.assertEqual(len(issues), 2)

        expected = {
            "backend_name": "GitHub",
            "data": {
                "user": {
                    "organizations_url": "https://api.github.com/users/zhquan_example/orgs",
                    "login": "zhquan_example",
                    "url": "https://api.github.com/users/zhquan_example",
                    "id": 11757159
                },
                "repository_url": "https://api.github.com/repos/zhquan_example/repo",
                "title": "title 2",
                "updated_at": "2016-03-15T15:09:29Z",
                "url": "https://api.github.com/repos/zhquan_example/repo/issues/278",
                "body": "body",
                "user_data": {
                    "type": "User",
                    "organizations_url": "https://api.github.com/users/zhquan_example/orgs",
                    "repos_url": "https://api.github.com/users/zhquan_example/repos",
                    "organizations": [
                        {
                            "login": "Orgs_1",
                            "members_url": "https://api.github.com/orgs/Orgs_1/members{/member}",
                            "avatar_url": "",
                            "events_url": "https://api.github.com/orgs/Orgs_1/events",
                            "hooks_url": "https://api.github.com/orgs/Orgs_1/hooks",
                            "id": 1,
                            "public_members_url": "https://api.github.com/orgs/Orgs_1/public_members{/member}",
                            "repos_url": "https://api.github.com/orgs/Orgs_1/repos",
                            "issues_url": "https://api.github.com/orgs/Orgs_1/issues",
                            "url": "https://api.github.com/orgs/Orgs_1",
                            "description": None
                        },
                        {
                            "login": "Orgs_2",
                            "members_url": "https://api.github.com/orgs/Orgs_2/members{/member}",
                            "avatar_url": "",
                            "events_url": "https://api.github.com/orgs/Orgs_2/events",
                            "hooks_url": "https://api.github.com/orgs/Orgs_2/hooks",
                            "id": 2,
                            "public_members_url": "https://api.github.com/orgs/Orgs_2/public_members{/member}",
                            "repos_url": "https://api.github.com/orgs/Orgs_2/repos",
                            "issues_url": "https://api.github.com/orgs/Orgs_2/issues",
                            "url": "https://api.github.com/orgs/Orgs_2",
                            "description": None
                        }
                    ],
                    "name": "zhquan_example",
                    "url": "https://api.github.com/users/zhquan_example",
                    "created_at": "2016-01-01T00:00:00Z",
                    "updated_at": "2016-01-01T01:00:00Z",
                    "login": "zhquan_example",
                    "id": 1
                },
                "created_at": "2016-01-22T09:54:47Z",
                "closed_at": "2016-03-15T15:09:29Z",
                "id": 2
            },
            "perceval_version": "0.1.0",
            "updated_on": 1458054569.0,
            "origin": "https://github.com/zhquan_example/repo",
            "uuid": "4236619ac2073491640f1698b5c4e169895aaf69",
            "backend_version": "0.1.0"
        }

        for key in expected:
            if (key == "data"):
                for data_key in expected[key]:
                    if (data_key == "user"):
                        for user_key in expected[key][data_key]:
                            self.assertEqual(issues[1][key][data_key][user_key], expected[key][data_key][user_key])
                    elif (data_key == "user_data"):
                        for user_key in expected[key][data_key]:
                            self.assertEqual(issues[1][key][data_key][user_key], expected[key][data_key][user_key])
                    else:
                        self.assertEqual(issues[1][key][data_key], expected[key][data_key])
            else:
                self.assertEqual(issues[1][key], expected[key])

    @httpretty.activate
    def test_fetch_from_date(self):
        """ Test when return from date """

        requests = []
        command = ""
        login = read_file('data/github_login')
        body = read_file('data/github_issue_2')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_COMMAND_URL,
                               body=command, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_LOGIN_URL,
                              body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200)

        from_date = datetime.datetime(2016, 3, 1)
        github = GitHub("zhquan_example", "repo", "aaa", None)

        issues = [issues for issues in github.fetch(from_date=from_date)]

        expected = {
            "backend_name": "GitHub",
            "data": {
                "user": {
                    "organizations_url": "https://api.github.com/users/zhquan_example/orgs",
                    "login": "zhquan_example",
                    "url": "https://api.github.com/users/zhquan_example",
                    "id": 11757159
                },
                "repository_url": "https://api.github.com/repos/zhquan_example/repo",
                "title": "title 2",
                "updated_at": "2016-03-15T15:09:29Z",
                "url": "https://api.github.com/repos/zhquan_example/repo/issues/278",
                "body": "body",
                "user_data": {
                    "type": "User",
                    "organizations_url": "https://api.github.com/users/zhquan_example/orgs",
                    "repos_url": "https://api.github.com/users/zhquan_example/repos",
                    "organizations": [
                        {
                            "login": "Orgs_1",
                            "members_url": "https://api.github.com/orgs/Orgs_1/members{/member}",
                            "avatar_url": "",
                            "events_url": "https://api.github.com/orgs/Orgs_1/events",
                            "hooks_url": "https://api.github.com/orgs/Orgs_1/hooks",
                            "id": 1,
                            "public_members_url": "https://api.github.com/orgs/Orgs_1/public_members{/member}",
                            "repos_url": "https://api.github.com/orgs/Orgs_1/repos",
                            "issues_url": "https://api.github.com/orgs/Orgs_1/issues",
                            "url": "https://api.github.com/orgs/Orgs_1",
                            "description": None
                        },
                        {
                            "login": "Orgs_2",
                            "members_url": "https://api.github.com/orgs/Orgs_2/members{/member}",
                            "avatar_url": "",
                            "events_url": "https://api.github.com/orgs/Orgs_2/events",
                            "hooks_url": "https://api.github.com/orgs/Orgs_2/hooks",
                            "id": 2,
                            "public_members_url": "https://api.github.com/orgs/Orgs_2/public_members{/member}",
                            "repos_url": "https://api.github.com/orgs/Orgs_2/repos",
                            "issues_url": "https://api.github.com/orgs/Orgs_2/issues",
                            "url": "https://api.github.com/orgs/Orgs_2",
                            "description": None
                        }
                    ],
                    "name": "zhquan_example",
                    "url": "https://api.github.com/users/zhquan_example",
                    "created_at": "2016-01-01T00:00:00Z",
                    "updated_at": "2016-01-01T01:00:00Z",
                    "login": "zhquan_example",
                    "id": 1
                },
                "created_at": "2016-01-22T09:54:47Z",
                "closed_at": "2016-03-15T15:09:29Z",
                "id": 2
            },
            "perceval_version": "0.1.0",
            "updated_on": 1458054569.0,
            "origin": "https://github.com/zhquan_example/repo",
            "uuid": "4236619ac2073491640f1698b5c4e169895aaf69",
            "backend_version": "0.1.0"
        }

        for key in expected:
            if (key == "data"):
                for data_key in expected[key]:
                    if (data_key == "user"):
                        for user_key in expected[key][data_key]:
                            self.assertEqual(issues[0][key][data_key][user_key], expected[key][data_key][user_key])
                    elif (data_key == "user_data"):
                        for user_key in expected[key][data_key]:
                            self.assertEqual(issues[0][key][data_key][user_key], expected[key][data_key][user_key])
                    else:
                        self.assertEqual(issues[0][key][data_key], expected[key][data_key])
            else:
                self.assertEqual(issues[0][key], expected[key])

    @httpretty.activate
    def test_feth_empty(self):
        """ Test when return empty """

        command = ""
        body = ""
        login = read_file('data/github_login')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_COMMAND_URL,
                               body=command, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_LOGIN_URL,
                              body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200)

        from_date = datetime.datetime(2016, 1, 1)
        github = GitHub("zhquan_example", "repo", "aaa", None)

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

        command = ""
        body = read_file('data/github_request')
        login = read_file('data/github_login')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_COMMAND_URL,
                               body=command, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=body, status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })
        httpretty.register_uri(httpretty.GET,
                              GITHUB_LOGIN_URL,
                              body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body="[]", status=200)

        # First, we fetch the bugs from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        github = GitHub("zhquan_example", "repo", "aaa", None, cache=cache)

        issues = [issues for issues in github.fetch()]

        # Now, we get the bugs from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cache_issues = [cache_issues for cache_issues in github.fetch_from_cache()]
        for key in issues[0]:
            if (key != "timestamp"):
                self.assertEqual(issues[0][key], cache_issues[0][key])

    def test_fetch_from_empty_cache(self):
        """Test if there are not any issues returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        github = GitHub("zhquan_example", "repo", "aaa", None, cache=cache)

        cache_issues = [cache_issues for cache_issues in github.fetch_from_cache()]

        self.assertEqual(len(cache_issues), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        github = GitHub("zhquan_example", "repo", "aaa", None)

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
                                    'X-RateLimit-Remaining': '4986'
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
    def test_get_from_date_issues(self):
        """ Test get_from_issues API call """

        issue = read_file('data/github_request_from_2016_03_01')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })

        from_date = datetime.datetime(2016, 3, 1)
        client = GitHubClient("zhquan_example", "repo", "aaa", None)

        raw_issues = [issues for issues in client.get_issues(from_date)]
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
                                    'X-RateLimit-Remaining': '4986',
                                    'Link': '<'+GITHUB_ISSUES_URL+'/?&page=2>; rel="next", <'+GITHUB_ISSUES_URL+'/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL+'/?&page=2',
                               body=issue_2,
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4985'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
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
                                    'X-RateLimit-Remaining': '4986'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)

        raw_issues = [issues for issues in client.get_issues()]
        self.assertEqual(raw_issues[0], '[]\n')

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
                               GITHUB_LOGIN_URL,
                               body=login, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body="",
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
        response = client.get_user("zhquan_example")
        self.assertEqual(response, login)

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
    def test_get_user_orgs(self):
        """ Test get_user_orgs API call """

        orgs = read_file('data/github_orgs')

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ORGS_URL,
                               body=orgs, status=200)
        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body="",
                               status=200,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
                               })

        client = GitHubClient("zhquan_example", "repo", "aaa", None)
        response = client.get_user_orgs("zhquan_example")

        self.assertEqual(response, orgs)

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
    def test_http_wrong_status(self):
        """Test if a error is raised when the http status was not 200"""

        issue = ""

        httpretty.register_uri(httpretty.GET,
                               GITHUB_ISSUES_URL,
                               body=issue,
                               status=500,
                               forcing_headers={
                                    'X-RateLimit-Remaining': '4986'
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

class TestGitHubCommand(unittest.TestCase):
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--owner', 'zhquan_example',
                '--repository', 'repo',
                '--from-date', '2016-01-03',
                '-t', 'aaa']

        cmd = GitHubCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.owner, "zhquan_example")
        self.assertEqual(cmd.parsed_args.repository, "repo")
        self.assertEqual(cmd.parsed_args.backend_token, "aaa")

    @httpretty.activate
    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = GitHubCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

if __name__ == "__main__":
    unittest.main(warnings='ignore')

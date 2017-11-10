#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
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
#     Quan Zhou <quan@bitergia.com>
#

import datetime
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

import httpretty
import pkg_resources
import requests


from perceval.backend import BackendCommandArgumentParser
from perceval.cache import Cache
from perceval.errors import CacheError, RateLimitError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.gitlab import (GitLab,
                                           GitLabCommand,
                                           GitLabClient, GITLAB_URL)

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))
pkg_resources.declare_namespace('perceval.backends')

GITLAB_API_URL = "https://gitlab.com/api/v4"
GITLAB_ISSUES_URL = GITLAB_API_URL + "/projects/fdroid%2Ffdroiddata/issues"

GITLAB_ENTERPRISE_URL = "https://gitlab.ow2.org"
GITLAB_ENTERPRISE_API_URL = GITLAB_ENTERPRISE_URL + "/api/v4"
GITLAB_ENTERPRISE_ISSUES_URL = \
     GITLAB_ENTERPRISE_API_URL + "/projects/am%2Ftest/issues"
GITLAB_ENTERPRISE_USER_URL = \
    GITLAB_ENTERPRISE_API_URL + "/users?username=zhquan"


def setup_http_server():

    page_1 = read_file('data/gitlab/issue_page_1')
    page_2 = read_file('data/gitlab/issue_page_2')

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL,
                           body=page_1,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20',
                               'Link': '<' + GITLAB_ISSUES_URL +
                                       '/?&page=2>; rel="next", <' +
                                       GITLAB_ISSUES_URL +
                                       '/?&page=3>; rel="last"'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + '/?&page=2',
                           body=page_2,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    issue_1_notes = read_file('data/gitlab/issue_1_notes')
    issue_2_notes = read_file('data/gitlab/issue_2_notes')
    issue_3_notes = read_file('data/gitlab/issue_3_notes')
    issue_4_notes = read_file('data/gitlab/issue_4_notes')

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/1/notes",
                           body=issue_1_notes,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/2/notes",
                           body=issue_2_notes,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/3/notes",
                           body=issue_3_notes,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/4/notes",
                           body=issue_4_notes,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    emoji = read_file('data/gitlab/emoji')
    empty_emoji = read_file('data/gitlab/empty_emoji')

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/3/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/4/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/1/notes/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/1/notes/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/2/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/3/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })

    httpretty.register_uri(httpretty.GET,
                           GITLAB_ISSUES_URL + "/4/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers={
                               'RateLimit-Remaining': '20'
                           })


def read_file(filename, mode='r'):
    with open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestGitLabBackend(unittest.TestCase):
    """ GitLab backend tests """

    def test_initialization(self):
        """Test whether attributes are initializated"""

        gitlab = GitLab('zhquan_example',
                        'repo',
                        'aaa',
                        tag='test'
                        )

        self.assertEqual(gitlab.owner, 'zhquan_example')
        self.assertEqual(gitlab.repository, 'repo')
        self.assertEqual(gitlab.origin,
                         GITLAB_URL + 'zhquan_example/repo')
        self.assertEqual(gitlab.tag, 'test')

        # When tag is empty or None it will be set to
        # the value in origin
        gitlab = GitLab('zhquan_example',
                        'repo',
                        'aaa'
                        )

        self.assertEqual(gitlab.owner, 'zhquan_example')
        self.assertEqual(gitlab.repository, 'repo')
        self.assertEqual(gitlab.origin,
                         GITLAB_URL + 'zhquan_example/repo')
        self.assertEqual(gitlab.tag,
                         GITLAB_URL + 'zhquan_example/repo')

        gitlab = GitLab('zhquan_example',
                        'repo',
                        'aaa',
                        GITLAB_ENTERPRISE_URL,
                        tag='')

        self.assertEqual(gitlab.owner, 'zhquan_example')
        self.assertEqual(gitlab.repository, 'repo')
        self.assertEqual(gitlab.origin,
                         'https://gitlab.ow2.org/zhquan_example/repo')
        self.assertEqual(gitlab.tag,
                         'https://gitlab.ow2.org/zhquan_example/repo')

        # test if enterprise-url is taken into account, so
        # the value in origin is this url and not default one
        gitlab = GitLab('zhquan_example',
                        'repo',
                        'aaa',
                        GITLAB_ENTERPRISE_URL)

        self.assertEqual(gitlab.owner, 'zhquan_example')
        self.assertEqual(gitlab.repository, 'repo')
        self.assertEqual(gitlab.origin,
                         'https://gitlab.ow2.org/zhquan_example/repo')
        self.assertEqual(gitlab.tag,
                         'https://gitlab.ow2.org/zhquan_example/repo')

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(GitLab.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(GitLab.has_resuming(), True)

    @httpretty.activate
    def test_fetch_enterprise(self):
        """Test if it fetches issues from a GitLab Enterprise server"""

        setup_http_server()

        gitlab = GitLab("fdroid", "fdroiddata", "your-token")

        issues = [issues for issues in gitlab.fetch()]

        self.assertEqual(len(issues), 4)

        self.assertEqual(
            issues[0]['origin'], GITLAB_URL + 'fdroid/fdroiddata')
        self.assertEqual(
            issues[0]['updated_on'], 1489848259.566)
        self.assertEqual(
            issues[0]['category'], 'issue')
        self.assertEqual(
            issues[0]['tag'], GITLAB_URL + 'fdroid/fdroiddata')
        self.assertEqual(
            issues[0]['data']['web_url'],
            'https://gitlab.com/fdroid/fdroiddata/issues/639')
        self.assertEqual(
            issues[0]['data']['author']['id'], 1)
        self.assertEqual(
            issues[0]['data']['author']['username'], 'redfish64')

    @httpretty.activate
    def test_fetch_from_date(self):
        """ Test when return from date """

        print("TODO")

    @httpretty.activate
    def test_fetch_empty(self):
        """ Test when return empty """

        print("TODO")

#===============================================================================
#     def test_live(self):
#         from_date = datetime.datetime(2017, 4, 10)
# #        backend = GitLab("fdroid", "fdroiddata", "5pJ4_4dxuNA7iXZsEqK8")
#         backend = GitLab("sat4j", "sat4j",
#                          "xxxxxxxxxxxx", GITLAB_ENTERPRISE_URL)
#         issues = [issues for issues in backend.fetch(from_date=from_date)]
#===============================================================================


class TestGitHubBackendCache(unittest.TestCase):
    """GitHub backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """ Test whether a list of issues is returned from cache """

        print("TODO")

    def test_fetch_from_empty_cache(self):
        """Test if there are not any issues returned when the cache is empty"""

        print("TODO")

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        print("TODO")


class TestGitHubClient(unittest.TestCase):
    """ GitHub API client tests """

    def test_api_url_initialization(self):
        """Test API URL initialization for both basic and enterprise servers"""

        print("TODO")

    @httpretty.activate
    def test_issues(self):
        """ Test issues API call """

        print("TODO")

    @httpretty.activate
    def test_issues_from_date(self):
        """ Test issue from date param API call """

        print("TODO")

    @httpretty.activate
    def test_issues_empty(self):
        """ Test when issue is empty API call """

        print("TODO")

    @httpretty.activate
    def test_issue_notes(self):
        """ Test issue_notes API call """

        print("TODO")

    @httpretty.activate
    def test_issue_emoji(self):
        """ Test issue_emoji API call """

        print("TODO")

    @httpretty.activate
    def test_note_emojis(self):
        """ Test note_emoji API call """

        print("TODO")

    @httpretty.activate
    def test_user(self):
        """Test user API call"""

        print("TODO")

    @httpretty.activate
    def test_http_wrong_status(self):
        """Test if a error is raised when the http status was not 200"""

        print("TODO")

    @httpretty.activate
    def test_sleep_for_rate(self):
        """ Test get_page_issue API call """

        print("TODO")

    @httpretty.activate
    def test_rate_limit_error(self):
        """ Test get_page_issue API call """

        print("TODO")


class TestGitLabCommand(unittest.TestCase):
    """GitLabCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is GitLab"""

        self.assertIs(GitLabCommand.BACKEND, GitLab)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GitLabCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--sleep-for-rate',
                '--min-rate-to-sleep', '1',
                '--tag', 'test', '--no-cache',
                '--api-token', 'abcdefgh',
                '--from-date', '1970-01-01',
                '--enterprise-url', 'https://example.com',
                'zhquan_example', 'repo']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.owner, 'zhquan_example')
        self.assertEqual(parsed_args.repository, 'repo')
        self.assertEqual(parsed_args.base_url, 'https://example.com')
        self.assertEqual(parsed_args.sleep_for_rate, True)
        self.assertEqual(parsed_args.min_rate_to_sleep, 1)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.no_cache, True)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')


if __name__ == "__main__":
    unittest.main(warnings='ignore')
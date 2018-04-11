#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Bitergia
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
#     Assad Montasser <assad.montasser@ow2.org>
#     Valerio Cosentino <valcos@bitergia.com>
#

import datetime
import json
import os
import time
import unittest

import httpretty
import pkg_resources
import requests

pkg_resources.declare_namespace('perceval.backends')

from grimoirelab.toolkit.datetime import datetime_utcnow
from perceval.backend import BackendCommandArgumentParser
from perceval.errors import RateLimitError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.gitlab import (GitLab,
                                           GitLabCommand,
                                           GitLabClient)
from base import TestCaseBackendArchive

GITLAB_URL = "https://gitlab.com"
GITLAB_API_URL = GITLAB_URL + "/api/v4"
GITLAB_URL_PROJECT = GITLAB_API_URL + "/projects/fdroid%2Ffdroiddata"
GITLAB_ISSUES_URL = GITLAB_API_URL + "/projects/fdroid%2Ffdroiddata/issues"

GITLAB_ENTERPRISE_URL = "https://gitlab.ow2.org"
GITLAB_ENTERPRISE_API_URL = GITLAB_ENTERPRISE_URL + "/api/v4"
GITLAB_ENTERPRISE_URL_PROJECT = GITLAB_ENTERPRISE_API_URL + "/projects/am%2Ftest"
GITLAB_ENTERPRISE_ISSUES_URL = GITLAB_ENTERPRISE_API_URL + "/projects/am%2Ftest/issues"


def setup_http_server(url_project, issues_url, rate_limit_headers=None):
    project = read_file('data/gitlab/project')
    page_1 = read_file('data/gitlab/issue_page_1')
    page_2 = read_file('data/gitlab/issue_page_2')

    if not rate_limit_headers:
        rate_limit_headers = {}

    httpretty.register_uri(httpretty.GET,
                           url_project,
                           body=project,
                           status=200,
                           forcing_headers=rate_limit_headers)

    pagination_header = {'Link': '<' + issues_url +
                         '/?&page=2>; rel="next", <' + issues_url +
                         '/?&page=3>; rel="last"'}

    pagination_header.update(rate_limit_headers)
    httpretty.register_uri(httpretty.GET,
                           issues_url,
                           body=page_1,
                           status=200,
                           forcing_headers=pagination_header)

    httpretty.register_uri(httpretty.GET,
                           issues_url + '/?&page=2',
                           body=page_2,
                           status=200,
                           forcing_headers=rate_limit_headers)

    issue_1_notes = read_file('data/gitlab/issue_1_notes')
    issue_2_notes = read_file('data/gitlab/issue_2_notes')
    issue_3_notes = read_file('data/gitlab/issue_3_notes')
    issue_4_notes = read_file('data/gitlab/issue_4_notes')

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/notes",
                           body=issue_1_notes,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/2/notes",
                           body=issue_2_notes,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/3/notes",
                           body=issue_3_notes,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/4/notes",
                           body=issue_4_notes,
                           status=200,
                           forcing_headers=rate_limit_headers)

    emoji = read_file('data/gitlab/emoji')
    empty_emoji = read_file('data/gitlab/empty_emoji')

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/3/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/4/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/notes/1/award_emoji",
                           body=emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/1/notes/2/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/2/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/3/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)

    httpretty.register_uri(httpretty.GET,
                           issues_url + "/4/notes/1/award_emoji",
                           body=empty_emoji,
                           status=200,
                           forcing_headers=rate_limit_headers)


def read_file(filename, mode='r'):
    with open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestGitLabBackend(unittest.TestCase):
    """ GitLab backend tests """

    @httpretty.activate
    def test_initialization(self):
        """Test whether attributes are initializated"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        gitlab = GitLab('fdroid', 'fdroiddata', api_token='aaa', tag='test')

        self.assertEqual(gitlab.owner, 'fdroid')
        self.assertEqual(gitlab.repository, 'fdroiddata')
        self.assertEqual(gitlab.origin, GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(gitlab.tag, 'test')
        self.assertIsNone(gitlab.client)

        # When tag is empty or None it will be set to
        # the value in origin
        gitlab = GitLab('fdroid', 'fdroiddata', api_token='aaa')

        self.assertEqual(gitlab.owner, 'fdroid')
        self.assertEqual(gitlab.repository, 'fdroiddata')
        self.assertEqual(gitlab.origin, GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(gitlab.tag, GITLAB_URL + '/fdroid/fdroiddata')
        self.assertIsNone(gitlab.client)

    @httpretty.activate
    def test_initialization_entreprise(self):
        """Test whether attributes are initialized for the entreprise version"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT, GITLAB_ENTERPRISE_ISSUES_URL)

        gitlab = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, tag='')

        self.assertEqual(gitlab.owner, 'am')
        self.assertEqual(gitlab.repository, 'test')
        self.assertEqual(gitlab.origin, GITLAB_ENTERPRISE_URL + "/am/test")
        self.assertEqual(gitlab.tag, GITLAB_ENTERPRISE_URL + "/am/test")
        self.assertIsNone(gitlab.client)

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(GitLab.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(GitLab.has_resuming(), False)

    @httpretty.activate
    def test_fetch(self):
        """Test whether issues are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token")

        issues = [issues for issues in gitlab.fetch()]

        self.assertEqual(len(issues), 4)

        self.assertEqual(issues[0]['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issues[0]['data']['author']['id'], 1)
        self.assertEqual(issues[0]['data']['author']['username'], 'redfish64')

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether issues from a given date are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL)

        gitlab = GitLab("fdroid", "fdroiddata", "your-token")
        from_date = datetime.datetime(2017, 3, 18)
        issues = [issues for issues in gitlab.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 3)

        self.assertEqual(issues[0]['origin'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], GITLAB_URL + '/fdroid/fdroiddata')
        self.assertEqual(issues[0]['data']['author']['id'], 1)
        self.assertEqual(issues[0]['data']['author']['username'], 'redfish64')

        from_date = datetime.datetime(3019, 3, 18)
        issues = [issues for issues in gitlab.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 0)

    @httpretty.activate
    def test_fetch_enterprise(self):
        """Test whether issues are properly fetched from GitLab Enterprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT, GITLAB_ENTERPRISE_ISSUES_URL)

        gitlab = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL)

        issues = [issues for issues in gitlab.fetch()]

        self.assertEqual(len(issues), 4)

        self.assertEqual(issues[0]['origin'], GITLAB_ENTERPRISE_URL + "/am/test")
        self.assertEqual(issues[0]['category'], 'issue')
        self.assertEqual(issues[0]['tag'], GITLAB_ENTERPRISE_URL + "/am/test")
        self.assertEqual(issues[0]['data']['author']['id'], 1)
        self.assertEqual(issues[0]['data']['author']['username'], 'redfish64')

    @httpretty.activate
    def test_fetch_empty(self):
        """Test when return empty"""

        page_1 = ''

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body=page_1,
                               status=200)

        gitlab = GitLab("fdroid", "fdroiddata", api_token="your-token")

        issues = [issues for issues in gitlab.fetch()]

        self.assertEqual(len(issues), 0)


class TestGitHUbBackendArchive(TestCaseBackendArchive):
    """GitHub backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = GitLab("fdroid", "fdroiddata", api_token="your-token", archive=self.archive)
        self.backend_read_archive = GitLab("fdroid", "fdroiddata", api_token="your-token", archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether issues are properly fetched from the archive"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL)
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether issues from a given date are properly fetched from GitLab"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL)

        from_date = datetime.datetime(2017, 3, 18)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_enterprise(self):
        """Test whether issues are properly fetched from GitLab Enterprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT, GITLAB_ENTERPRISE_ISSUES_URL)

        self.backend_write_archive = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, archive=self.archive)
        self.backend_read_archive = GitLab('am', 'test', base_url=GITLAB_ENTERPRISE_URL, archive=self.archive)
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_empty(self):
        """Test when return empty"""

        page_1 = ''

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body=page_1,
                               status=200)

        self._test_fetch_from_archive()


class TestGitLabClient(unittest.TestCase):
    """GitLab API client tests"""

    @httpretty.activate
    def test_initialization(self):
        """Test initialization for GitLab server"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        self.assertEqual(client.owner, "fdroid")
        self.assertEqual(client.repository, "fdroiddata")
        self.assertEqual(client.token, "your-token")
        self.assertEqual(client.sleep_for_rate, False)
        self.assertEqual(client.base_url, GITLAB_API_URL)
        self.assertEqual(client.min_rate_to_sleep, GitLabClient.MIN_RATE_LIMIT)
        self.assertEqual(client.sleep_time, GitLabClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GitLabClient.MAX_RETRIES)
        self.assertEqual(client.rate_limit, 20)
        self.assertEqual(client.rate_limit_reset_ts, None)

        client = GitLabClient("fdroid", "fdroiddata", "your-token", sleep_for_rate=True,
                              min_rate_to_sleep=100, max_retries=10, sleep_time=100)

        self.assertEqual(client.sleep_for_rate, True)
        self.assertEqual(client.base_url, GITLAB_API_URL)
        self.assertEqual(client.min_rate_to_sleep, 100)
        self.assertEqual(client.sleep_time, 100)
        self.assertEqual(client.max_retries, 10)

    @httpretty.activate
    def test_initialization_entreprise(self):
        """Test initialization for GitLab entreprise server"""

        setup_http_server(GITLAB_ENTERPRISE_URL_PROJECT, GITLAB_ENTERPRISE_ISSUES_URL)

        client = GitLabClient("am", "test", None, base_url=GITLAB_ENTERPRISE_URL)

        self.assertEqual(client.owner, "am")
        self.assertEqual(client.repository, "test")
        self.assertEqual(client.token, None)
        self.assertEqual(client.sleep_for_rate, False)
        self.assertEqual(client.base_url, GITLAB_ENTERPRISE_API_URL)
        self.assertEqual(client.min_rate_to_sleep, GitLabClient.MIN_RATE_LIMIT)
        self.assertEqual(client.sleep_time, GitLabClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, GitLabClient.MAX_RETRIES)
        self.assertEqual(client.rate_limit, None)
        self.assertEqual(client.rate_limit_reset_ts, None)

    @httpretty.activate
    def test_issues(self):
        """Test issues API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        page_1 = read_file('data/gitlab/issue_page_1')
        page_2 = read_file('data/gitlab/issue_page_2')

        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        raw_issues = [issues for issues in client.issues()]

        self.assertEqual(len(raw_issues), 2)
        self.assertEqual(raw_issues[0], page_1)
        self.assertEqual(raw_issues[1], page_2)

        # Check requests
        expected = {
            'state': ['all'],
            'sort': ['asc'],
            'order_by': ['updated_at'],
            'page': ['2']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["PRIVATE-TOKEN"], "your-token")

    @httpretty.activate
    def test_issues_from_date(self):
        """Test issues API call with from date parameter"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        page_1 = read_file('data/gitlab/issue_page_1')
        page_2 = read_file('data/gitlab/issue_page_2')

        from_date = datetime.datetime(2017, 1, 1)
        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        raw_issues = [issues for issues in client.issues(from_date)]

        self.assertEqual(len(raw_issues), 2)
        self.assertNotEqual(raw_issues[0], json.dumps(json.loads(page_1)))
        self.assertEqual(raw_issues[1], json.dumps(json.loads(page_2)))

        # Check requests
        expected = {
            'state': ['all'],
            'sort': ['asc'],
            'order_by': ['updated_at'],
            'page': ['2']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["PRIVATE-TOKEN"], "your-token")

    @httpretty.activate
    def test_issues_empty(self):
        """Test when issue is empty API call"""

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body="[]",
                               status=200
                               )

        client = GitLabClient("fdroid", "fdroiddata", "aaa")

        raw_issues = [issues for issues in client.issues()]

        self.assertEqual(raw_issues[0], "[]")

        self.assertEqual(
            httpretty.last_request().headers["PRIVATE-TOKEN"], "aaa")

    @httpretty.activate
    def test_issue_notes(self):
        """Test issue_notes API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_notes = next(client.issue_notes(1))
        notes = json.loads(raw_notes)

        self.assertEqual(len(notes), 2)

    @httpretty.activate
    def test_issue_emojis(self):
        """Test issue_emojis API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_emojis = next(client.issue_emojis(1))
        emojis = json.loads(raw_emojis)

        self.assertEqual(len(emojis), 2)

    @httpretty.activate
    def test_note_emojis(self):
        """Test note_emojis API call"""

        setup_http_server(GITLAB_URL_PROJECT, GITLAB_ISSUES_URL,
                          rate_limit_headers={'RateLimit-Remaining': '20'})

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        raw_emojis = next(client.note_emojis(1, 2))
        emojis = json.loads(raw_emojis)

        self.assertEqual(len(emojis), 0)

    @httpretty.activate
    def test_http_wrong_status(self):
        """Test if a error is raised when the http status was not 200"""

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '20',
                                   'RateLimit-Reset': '15'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body="",
                               status=500
                               )

        client = GitLabClient("fdroid", "fdroiddata", "your-token", sleep_time=1)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in client.issues()]

    @httpretty.activate
    def test_calculate_time_to_reset(self):
        """Test whether the time to reset is zero if the sleep time is negative"""

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '20',
                                   'RateLimit-Reset': int(datetime_utcnow().replace(microsecond=0).timestamp())
                               })

        client = GitLabClient("fdroid", "fdroiddata", "your-token")
        time_to_reset = client.calculate_time_to_reset()

        self.assertEqual(time_to_reset, 0)

    @httpretty.activate
    def test_sleep_for_rate(self):
        """Test whether a RateLimit error is thrown when the sleep for rate parameter is false"""

        wait = 2
        reset = int(time.time() + wait)

        httpretty.register_uri(httpretty.GET,
                               GITLAB_URL_PROJECT,
                               body='',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '20',
                                   'RateLimit-Reset': reset
                               })

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL,
                               body='[]',
                               status=200,
                               forcing_headers={
                                   'RateLimit-Remaining': '0',
                                   'RateLimit-Reset': reset,
                                   'Link': '<' + GITLAB_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                    GITLAB_ISSUES_URL +
                                    '/?&page=3>; rel="last"'
                               })

        httpretty.register_uri(httpretty.GET,
                               GITLAB_ISSUES_URL + '/?&page=2',
                               body='[]',
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': reset
                               })

        client = GitLabClient("fdroid", "fdroiddata", "your-token", sleep_for_rate=True)

        issues = [issues for issues in client.issues()]
        after = int(time.time())

        self.assertTrue(reset >= after)
        self.assertEqual(len(issues), 2)

        client = GitLabClient("fdroid", "fdroiddata", "your-token")

        with self.assertRaises(RateLimitError):
            _ = [issues for issues in client.issues()]


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
                '--tag', 'test', '--no-archive',
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
        self.assertEqual(parsed_args.no_archive, True)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')


if __name__ == "__main__":
    unittest.main(warnings='ignore')

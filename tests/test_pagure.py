#!/usr/bin/env python3
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
#     Animesh Kumar<animuz111@gmail.com>
#

import datetime
import os
import unittest.mock
import httpretty
import requests
import dateutil.tz
import copy

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import (DEFAULT_DATETIME, DEFAULT_LAST_DATETIME)
from perceval.backends.core.pagure import (logger,
                                           Pagure,
                                           PagureCommand,
                                           PagureClient,
                                           CATEGORY_ISSUE,
                                           MAX_CATEGORY_ITEMS_PER_PAGE)
from base import TestCaseBackendArchive

PAGURE_API_URL = "https://pagure.io/api/0"
PAGURE_REPO_URL = PAGURE_API_URL + "/Project-example"
PAGURE_ISSUES_URL = PAGURE_REPO_URL + "/issues"

# Repository with issue tracker disabled
PAGURE_REPO_URL_DISABLED_URL = PAGURE_API_URL + "/Project-test-example"
PAGURE_ISSUES_DISABLED_URL = PAGURE_REPO_URL_DISABLED_URL + "/issues"

PAGURE_NAMESPACE_REPO_URL = PAGURE_API_URL + "/Test-group/Project-namespace-example"
PAGURE_NAMESPACE_ISSUES_URL = PAGURE_NAMESPACE_REPO_URL + "/issues"


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestPagureBackend(unittest.TestCase):
    """Pagure backend tests"""

    @httpretty.activate
    def test_initialization(self):
        """Test whether attributes are initialized"""

        pagure = Pagure(namespace=None, repository='Project-example', api_token='aaa', tag='test')

        # Testing initialization when repository is not within a namespace
        self.assertEqual(pagure.repository, 'Project-example')
        self.assertIsNone(pagure.namespace)
        self.assertEqual(pagure.origin, 'https://pagure.io/Project-example')
        self.assertEqual(pagure.tag, 'test')
        self.assertEqual(pagure.max_items, MAX_CATEGORY_ITEMS_PER_PAGE)
        self.assertEqual(pagure.categories, [CATEGORY_ISSUE])
        self.assertEqual(pagure.api_token, 'aaa')
        self.assertTrue(pagure.ssl_verify)

        # When tag is empty or None it will be set to the value in origin
        pagure = Pagure(namespace=None, repository='Project-example', api_token='aaa', ssl_verify=False)
        self.assertEqual(pagure.repository, 'Project-example')
        self.assertIsNone(pagure.namespace)
        self.assertEqual(pagure.origin, 'https://pagure.io/Project-example')
        self.assertEqual(pagure.tag, 'https://pagure.io/Project-example')
        self.assertFalse(pagure.ssl_verify)
        self.assertEqual(pagure.api_token, 'aaa')

        pagure = Pagure(namespace=None, repository='Project-example', api_token='aaa', tag='')
        self.assertEqual(pagure.repository, 'Project-example')
        self.assertIsNone(pagure.namespace)
        self.assertEqual(pagure.origin, 'https://pagure.io/Project-example')
        self.assertEqual(pagure.tag, 'https://pagure.io/Project-example')
        self.assertEqual(pagure.api_token, 'aaa')

        # Empty value generates a None API token
        pagure = Pagure(repository='Project-example', tag='test')
        self.assertEqual(pagure.repository, 'Project-example')
        self.assertIsNone(pagure.namespace)
        self.assertEqual(pagure.origin, 'https://pagure.io/Project-example')
        self.assertEqual(pagure.tag, 'test')
        self.assertIsNone(pagure.api_token)

        # Testing initialization when repository is within a namespace
        pagure = Pagure(namespace='Test-group', repository='Project-example-namespace', api_token='aaa', tag='testing')
        self.assertEqual(pagure.repository, 'Project-example-namespace')
        self.assertEqual(pagure.namespace, 'Test-group')
        self.assertEqual(pagure.origin, 'https://pagure.io/Test-group/Project-example-namespace')
        self.assertEqual(pagure.tag, 'testing')
        self.assertEqual(pagure.max_items, MAX_CATEGORY_ITEMS_PER_PAGE)
        self.assertEqual(pagure.categories, [CATEGORY_ISSUE])
        self.assertEqual(pagure.api_token, 'aaa')
        self.assertTrue(pagure.ssl_verify)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Pagure.has_resuming(), True)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Pagure.has_archiving(), True)

    @httpretty.activate
    def test_fetch_issues(self):
        """Test whether a list of issues is returned"""

        body = read_file('data/pagure/pagure_repo_issue_1')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=body,
                               status=200,
                               )
        pagure = Pagure(repository='Project-example', api_token='aaa')
        issues = [issues for issues in pagure.fetch(from_date=None, to_date=None)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['uuid'], '41071b08dd75f34ca92c6d5ecb844e7a3e5939c6')
        self.assertEqual(issue['updated_on'], 1583508642.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://pagure.io/Project-example')
        self.assertEqual(len(issue['data']['comments']), 1)
        self.assertEqual(issue['data']['comments'][0]['user']['name'], 'animeshk08')
        self.assertEqual(len(issue['data']['comments'][0]['reactions']), 0)

    @httpretty.activate
    def test_fetch_issues_disabled(self):
        """Test whether a warning message is logged when the issue tracker is disabled"""

        body = read_file('data/pagure/pagure_empty_request')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_DISABLED_URL,
                               body=body,
                               status=404,
                               )

        pagure = Pagure(repository='Project-test-example')

        with self.assertLogs(logger, level='WARN') as cm:
            issues = [issues for issues in pagure.fetch(from_date=None, to_date=None)]
            self.assertEqual(cm.output[0], 'WARNING:perceval.backends.core.pagure:'
                                           'The issue tracker is disabled please enable'
                                           ' the feature for the repository')

        self.assertListEqual(issues, [])

    @httpretty.activate
    def test_search_fields_issues(self):
        """Test whether the search_fields is properly set"""

        body = read_file('data/pagure/pagure_repo_issue_1')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=body,
                               status=200,
                               )

        pagure = Pagure(repository='Project-example', api_token='aaa')
        issues = [issues for issues in pagure.fetch(from_date=None, to_date=None)]

        issue = issues[0]
        self.assertEqual(pagure.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertIsNone(issue['search_fields']['namespace'])
        self.assertEqual(issue['search_fields']['repo'], 'Project-example')

    @httpretty.activate
    def test_fetch_more_issues(self):
        """Test when return two issues"""

        issue_1 = read_file('data/pagure/pagure_repo_issue_1')
        issue_2 = read_file('data/pagure/pagure_repo_only_issue_2')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'Link': '<' + PAGURE_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           PAGURE_ISSUES_URL + '/?&page=3>; rel="last"'
                               }
                               )

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               )

        pagure = Pagure(repository='Project-example')
        issues = [issues for issues in pagure.fetch()]

        self.assertEqual(len(issues), 2)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['uuid'], '41071b08dd75f34ca92c6d5ecb844e7a3e5939c6')
        self.assertEqual(issue['updated_on'], 1583508642.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://pagure.io/Project-example')
        self.assertEqual(len(issue['data']['comments']), 1)
        self.assertEqual(issue['data']['comments'][0]['user']['name'], 'animeshk08')
        self.assertEqual(issue['data']['assignee']['name'], 'animeshk08')
        self.assertEqual(len(issue['data']['comments'][0]['reactions']), 0)

        issue = issues[1]
        self.assertEqual(issue['origin'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['uuid'], '7dd3642664c8a7e475814b9037277df775657850')
        self.assertEqual(issue['updated_on'], 1583558174.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['data']['assignee']['name'], 'animeshk0806')
        self.assertEqual(len(issue['data']['comments']), 2)
        self.assertEqual(issue['data']['comments'][0]['user']['name'], 'animeshk08')
        self.assertEqual(len(issue['data']['comments'][0]['reactions']), 0)
        self.assertEqual(len(issue['data']['comments'][1]['reactions']), 1)
        self.assertListEqual(issue['data']['comments'][1]['reactions']['Thumbs up'], ['animeshk0806'])

    @httpretty.activate
    def test_fetch_issues_until_date(self):
        """Test when fetching issues till a particular date"""

        issue_1 = read_file('data/pagure/pagure_repo_issue_1')
        issue_2 = read_file('data/pagure/pagure_repo_only_issue_2')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'Link': '<' + PAGURE_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           PAGURE_ISSUES_URL + '/?&page=3>; rel="last"'
                               }
                               )

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               )

        to_date = datetime.datetime(2020, 3, 7)
        pagure = Pagure(repository='Project-example')
        issues = [issues for issues in pagure.fetch(to_date=to_date)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['uuid'], '41071b08dd75f34ca92c6d5ecb844e7a3e5939c6')
        self.assertEqual(issue['updated_on'], 1583508642.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['data']['assignee']['name'], 'animeshk08')
        self.assertEqual(len(issue['data']['comments']), 1)
        self.assertEqual(issue['data']['comments'][0]['user']['name'], 'animeshk08')

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test when fetching issues from a given date"""

        body = read_file('data/pagure/pagure_repo_issue_from_2020_03_07')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=body,
                               status=200,
                               )

        from_date = datetime.datetime(2020, 3, 7)
        pagure = Pagure(repository='Project-example')
        issues = [issues for issues in pagure.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['uuid'], '7dd3642664c8a7e475814b9037277df775657850')
        self.assertEqual(issue['updated_on'], 1583558174.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://pagure.io/Project-example')
        self.assertEqual(issue['data']['assignee']['name'], 'animeshk0806')
        self.assertEqual(len(issue['data']['comments']), 2)
        self.assertEqual(issue['data']['comments'][0]['user']['name'], 'animeshk08')

    @httpretty.activate
    def test_fetch_issues_namespace(self):
        """Test issues fetch from a repository within a namespace"""

        issue_1 = read_file('data/pagure/pagure_namespace_issue_2')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_NAMESPACE_ISSUES_URL,
                               body=issue_1, status=200,
                               )

        pagure = Pagure(namespace='Test-group', repository='Project-namespace-example')
        issues = [issues for issues in pagure.fetch()]

        self.assertEqual(len(issues), 2)

        issue = issues[0]
        self.assertEqual(issue['origin'], 'https://pagure.io/Test-group/Project-namespace-example')
        self.assertEqual(issue['uuid'], 'bdf90e94bf3b17ed2f75f5e5187e21a62512ca5a')
        self.assertEqual(issue['updated_on'], 1583509042.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://pagure.io/Test-group/Project-namespace-example')
        self.assertEqual(issue['data']['assignee']['name'], 'animeshk08')
        self.assertEqual(len(issue['data']['comments']), 1)
        self.assertEqual(issue['data']['comments'][0]['user']['name'], 'animeshk08')
        self.assertEqual(len(issue['data']['comments'][0]['reactions']), 0)

        issue = issues[1]
        self.assertEqual(issue['origin'], 'https://pagure.io/Test-group/Project-namespace-example')
        self.assertEqual(issue['uuid'], 'eec4d7bf5c3ca405e39f39a8c6faf616fd4fa425')
        self.assertEqual(issue['updated_on'], 1583562831.0)
        self.assertEqual(issue['category'], CATEGORY_ISSUE)
        self.assertEqual(issue['tag'], 'https://pagure.io/Test-group/Project-namespace-example')
        self.assertEqual(issue['data']['assignee']['name'], 'animeshk0806')
        self.assertEqual(len(issue['data']['comments']), 2)
        self.assertEqual(issue['data']['comments'][1]['user']['name'], 'animeshk08')
        self.assertEqual(len(issue['data']['comments'][0]['reactions']), 1)
        self.assertListEqual(issue['data']['comments'][0]['reactions']['Heart'], ['animeshk0806'])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test when return empty"""

        body = ""

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=body, status=200,
                               )
        from_date = datetime.datetime(2016, 1, 1)
        pagure = Pagure(repository='Project-example', api_token='aaa')

        issues = [issues for issues in pagure.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 0)


class TestPagureBackendArchive(TestCaseBackendArchive):
    """Pagure backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Pagure(repository='Project-example', api_token='aaa', archive=self.archive)
        self.backend_read_archive = Pagure(repository='Project-example', api_token='aaa', archive=self.archive)

    @httpretty.activate
    def test_fetch_issues_from_archive(self):
        """Test whether a list of issues is returned from archive"""

        issue_2 = read_file('data/pagure/pagure_repo_issue_1')
        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issue_2,
                               status=200,
                               )

        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of issues is returned from archive after a given date"""

        body = read_file('data/pagure/pagure_repo_issue_from_2020_03_07')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=body,
                               status=200,
                               )
        from_date = datetime.datetime(2020, 3, 7)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_from_empty_archive(self):
        """Test whether no issues are returned when the archive is empty"""

        body = ""

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=body, status=200,
                               )

        self._test_fetch_from_archive()


class TestPagureClient(unittest.TestCase):
    """Pagure API client tests"""

    @httpretty.activate
    def test_init(self):
        """Test initialization of client"""

        client = PagureClient(namespace=None, repository="Project-example", token="aaa")

        self.assertIsNone(client.namespace)
        self.assertEqual(client.repository, "Project-example")
        self.assertEqual(client.sleep_time, PagureClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, PagureClient.MAX_RETRIES)
        self.assertEqual(client.base_url, PAGURE_API_URL)
        self.assertTrue(client.ssl_verify)

        client = PagureClient(None, "Project-test-example", token='aaa',
                              sleep_time=20, max_retries=2, max_items=1,
                              archive=None, from_archive=False)
        self.assertIsNone(client.namespace)
        self.assertEqual(client.repository, "Project-test-example")
        self.assertEqual(client.token, 'aaa')
        self.assertEqual(client.sleep_time, 20)
        self.assertEqual(client.max_retries, 2)
        self.assertEqual(client.max_items, 1)
        self.assertIsNone(client.archive)
        self.assertFalse(client.from_archive)

        client = PagureClient(None, repository='Project-test-example', token=None)
        self.assertIsNone(client.token)

        # When the repository is within a namespace
        client = PagureClient(namespace='Test-group', repository="Project-namespace-example", token="aaa")

        self.assertEqual(client.namespace, 'Test-group')
        self.assertEqual(client.repository, "Project-namespace-example")
        self.assertEqual(client.sleep_time, PagureClient.DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, PagureClient.MAX_RETRIES)
        self.assertEqual(client.base_url, PAGURE_API_URL)
        self.assertTrue(client.ssl_verify)

    @httpretty.activate
    def test_issues(self):
        """Test issues API call"""

        issues = read_file('data/pagure/pagure_repo_issue_1')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issues, status=200,
                               )

        client = PagureClient(namespace=None, repository='Project-example', token='aaa')
        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issues)

        # Check requests
        expected = {
            'status': ['all'],
            'per_page': ['100'],
            'order': ['asc']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], 'token aaa')  # check

    @httpretty.activate
    def test_namespace_issues(self):
        """Test fetching issues from a repository within a namespace"""

        issue = read_file('data/pagure/pagure_namespace_issue_2')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_NAMESPACE_ISSUES_URL,
                               body=issue, status=200)

        client = PagureClient(namespace='Test-group', repository='Project-namespace-example', token=None)

        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
            'status': ['all'],
            'per_page': ['100'],
            'order': ['asc']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertIsNone(httpretty.last_request().headers["Authorization"])

    @httpretty.activate
    def test_get_from_date_issues(self):
        """Test issues from date API call"""

        issues = read_file('data/pagure/pagure_repo_issue_from_2020_03_07')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issues,
                               status=200,
                               )

        from_date = datetime.datetime(2020, 3, 7)
        client = PagureClient(namespace=None, repository='Project-example', token='aaa')

        raw_issues = [issues for issues in client.issues(from_date=from_date)]
        self.assertEqual(raw_issues[0], issues)

        # Check requests
        expected = {
            'status': ['all'],
            'per_page': ['100'],
            'order': ['asc'],
            'since': ['2020-03-07 00:00:00']
        }
        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_empty_issues(self):
        """Test when issue is empty API call"""

        issue = read_file('data/pagure/pagure_empty_request')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issue, status=200,
                               )

        client = PagureClient(namespace=None, repository="Project-example", token="aaa")

        raw_issues = [issues for issues in client.issues()]
        self.assertEqual(raw_issues[0], issue)

        # Check requests
        expected = {
            'status': ['all'],
            'per_page': ['100'],
            'order': ['asc']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_http_wrong_status(self):
        """Test if an error is raised when the http status was not 200"""

        issue = ""

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issue,
                               status=501,
                               )

        client = PagureClient(namespace=None, repository="Project-example", token="aaa", sleep_time=1, max_retries=1)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [issues for issues in client.issues()]

        # Check requests
        expected = {
            'status': ['all'],
            'per_page': ['100'],
            'order': ['asc']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    @httpretty.activate
    def test_get_page_issues(self):
        """Test issues pagination API call"""

        issue_1 = read_file('data/pagure/pagure_repo_issue_1')
        issue_2 = read_file('data/pagure/pagure_repo_only_issue_2')

        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL,
                               body=issue_1,
                               status=200,
                               forcing_headers={
                                   'Link': '<' + PAGURE_ISSUES_URL + '/?&page=2>; rel="next", <' +
                                           PAGURE_ISSUES_URL + '/?&page=3>; rel="last"'
                               })
        httpretty.register_uri(httpretty.GET,
                               PAGURE_ISSUES_URL + '/?&page=2',
                               body=issue_2,
                               status=200,
                               )

        client = PagureClient(namespace=None, repository="Project-example", token="aaa")

        issues = [issues for issues in client.issues()]

        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0], issue_1)
        self.assertEqual(issues[1], issue_2)

        # Check requests
        expected = {
            'status': ['all'],
            'page': ['2'],
            'per_page': ['100'],
            'order': ['asc']
        }

        self.assertDictEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], "token aaa")

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = {PagureClient.HAUTHORIZATION: "token aaa"}
        c_headers = copy.deepcopy(headers)
        payload = {}

        san_u, san_h, san_p = PagureClient.sanitize_for_archive(url, c_headers, payload)
        headers.pop(PagureClient.HAUTHORIZATION)

        self.assertEqual(url, san_u)
        self.assertEqual(headers, san_h)
        self.assertEqual(payload, san_p)


class TestPagureCommand(unittest.TestCase):
    """PagureCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Pagure"""

        self.assertIs(PagureCommand.BACKEND, Pagure)

    def test_setup_cmd_parser(self):
        """Test if the parser object is correctly initialized"""

        parser = PagureCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Pagure)

        # Testing initialization when a repository is within a namespace
        args = ['Test-group', 'Project-namespace-example',
                '--max-retries', '5',
                '--max-items', '10',
                '--tag', 'test', '--no-archive',
                '--api-token', 'abcdefgh',
                '--from-date', '1970-01-01',
                '--to-date', '2100-01-01',
                ]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.namespace, 'Test-group')
        self.assertEqual(parsed_args.repository, 'Project-namespace-example')
        self.assertEqual(parsed_args.max_retries, 5)
        self.assertEqual(parsed_args.max_items, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.to_date, DEFAULT_LAST_DATETIME)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')

        # Testing initialization when a repository is not within a namespace
        args = ['Project-example',
                '--max-retries', '4',
                '--max-items', '20',
                '--no-archive',
                '--api-token', 'abcdefgh',
                '--from-date', '2018-03-01',
                '--to-date', '2020-01-20',
                ]

        from_date_datetime = datetime.datetime(2018, 3, 1, 0, 0, tzinfo=dateutil.tz.tzutc())
        to_date_datetime = datetime.datetime(2020, 1, 20, 0, 0, tzinfo=dateutil.tz.tzutc())

        parsed_args = parser.parse(*args)
        self.assertIsNone(parsed_args.namespace)
        self.assertEqual(parsed_args.repository, 'Project-example')
        self.assertEqual(parsed_args.max_retries, 4)
        self.assertEqual(parsed_args.max_items, 20)
        self.assertEqual(parsed_args.from_date, from_date_datetime)
        self.assertEqual(parsed_args.to_date, to_date_datetime)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')

        # Testing initialization without api-token,from_date and to_date
        args = ['Project-example',
                '--max-retries', '4',
                '--max-items', '20',
                '--no-archive',
                ]

        parsed_args = parser.parse(*args)
        self.assertIsNone(parsed_args.namespace)
        self.assertEqual(parsed_args.repository, 'Project-example')
        self.assertEqual(parsed_args.max_retries, 4)
        self.assertEqual(parsed_args.max_items, 20)
        self.assertIsNone(parsed_args.api_token)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertIsNone(parsed_args.to_date)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

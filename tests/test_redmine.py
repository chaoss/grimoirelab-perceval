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
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import copy
import datetime
import httpretty
import os
import unittest

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.redmine import (Redmine,
                                            RedmineCommand,
                                            RedmineClient)
from base import TestCaseBackendArchive


REDMINE_URL = 'http://example.com'
REDMINE_ISSUES_URL = REDMINE_URL + '/issues.json'
REDMINE_ISSUE_2_URL = REDMINE_URL + '/issues/2.json'
REDMINE_ISSUE_5_URL = REDMINE_URL + '/issues/5.json'
REDMINE_ISSUE_9_URL = REDMINE_URL + '/issues/9.json'
REDMINE_ISSUE_7311_URL = REDMINE_URL + '/issues/7311.json'
REDMINE_USER_3_URL = REDMINE_URL + '/users/3.json'
REDMINE_USER_4_URL = REDMINE_URL + '/users/4.json'
REDMINE_USER_24_URL = REDMINE_URL + '/users/24.json'
REDMINE_USER_25_URL = REDMINE_URL + '/users/25.json'
REDMINE_NOT_FOUND_USER_URL = REDMINE_URL + '/users/99.json'

REDMINE_URL_LIST = [
    REDMINE_ISSUES_URL, REDMINE_ISSUE_2_URL, REDMINE_ISSUE_5_URL,
    REDMINE_ISSUE_9_URL, REDMINE_ISSUE_7311_URL, REDMINE_USER_3_URL,
    REDMINE_USER_4_URL, REDMINE_USER_24_URL, REDMINE_USER_25_URL,
    REDMINE_NOT_FOUND_USER_URL
]


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    issues_body = read_file('data/redmine/redmine_issues.json', 'rb')
    issues_next_body = read_file('data/redmine/redmine_issues_next.json', 'rb')
    issues_empty_body = read_file('data/redmine/redmine_issues_empty.json', 'rb')
    issue_2_body = read_file('data/redmine/redmine_issue_2.json', 'rb')
    issue_5_body = read_file('data/redmine/redmine_issue_5.json', 'rb')
    issue_9_body = read_file('data/redmine/redmine_issue_9.json', 'rb')
    issue_7311_body = read_file('data/redmine/redmine_issue_7311.json', 'rb')
    user_3_body = read_file('data/redmine/redmine_user_3.json', 'rb')
    user_4_body = read_file('data/redmine/redmine_user_4.json', 'rb')
    user_24_body = read_file('data/redmine/redmine_user_24.json', 'rb')
    user_25_body = read_file('data/redmine/redmine_user_25.json', 'rb')

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        status = 200

        if uri.startswith(REDMINE_ISSUES_URL):
            if (params['updated_on'][0] == '>=1970-01-01T00:00:00Z' and
                params['offset'][0] == '0'):
                body = issues_body
            elif (params['updated_on'][0] == '>=1970-01-01T00:00:00Z' and
                  params['offset'][0] == '3'):
                body = issues_next_body
            elif (params['updated_on'][0] == '>=2016-07-27T00:00:00Z' and
                  params['offset'][0] == '0'):
                body = issues_next_body
            else:
                body = issues_empty_body
        elif uri.startswith(REDMINE_ISSUE_2_URL):
            body = issue_2_body
        elif uri.startswith(REDMINE_ISSUE_5_URL):
            body = issue_5_body
        elif uri.startswith(REDMINE_ISSUE_9_URL):
            body = issue_9_body
        elif uri.startswith(REDMINE_ISSUE_7311_URL):
            body = issue_7311_body
        elif uri.startswith(REDMINE_USER_3_URL):
            body = user_3_body
        elif uri.startswith(REDMINE_USER_4_URL):
            body = user_4_body
        elif uri.startswith(REDMINE_USER_24_URL):
            body = user_24_body
        elif uri.startswith(REDMINE_USER_25_URL):
            body = user_25_body
        elif uri.startswith(REDMINE_NOT_FOUND_USER_URL):
            body = "Not Found"
            status = 404
        else:
            raise

        http_requests.append(last_request)

        return (status, headers, body)

    for url in REDMINE_URL_LIST:
        httpretty.register_uri(httpretty.GET,
                               url,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
    return http_requests


class TestRedmineBackend(unittest.TestCase):
    """Redmine backend unit tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        redmine = Redmine(REDMINE_URL, api_token='AAAA', max_issues=5,
                          tag='test')

        self.assertEqual(redmine.url, REDMINE_URL)
        self.assertEqual(redmine.max_issues, 5)
        self.assertEqual(redmine.origin, REDMINE_URL)
        self.assertEqual(redmine.tag, 'test')
        self.assertIsNone(redmine.client)
        self.assertTrue(redmine.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        redmine = Redmine(REDMINE_URL)
        self.assertEqual(redmine.url, REDMINE_URL)
        self.assertEqual(redmine.origin, REDMINE_URL)
        self.assertEqual(redmine.tag, REDMINE_URL)

        redmine = Redmine(REDMINE_URL, tag='', ssl_verify=False)
        self.assertEqual(redmine.url, REDMINE_URL)
        self.assertEqual(redmine.origin, REDMINE_URL)
        self.assertEqual(redmine.tag, REDMINE_URL)
        self.assertFalse(redmine.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Redmine.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Redmine.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of issues"""

        http_requests = setup_http_server()

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch()]

        expected = [(9, '91a8349c2f6ebffcccc49409529c61cfd3825563', 1323367020.0, 3, 3),
                    (5, 'c4aeb9e77fec8e4679caa23d4012e7cc36ae8b98', 1323367075.0, 3, 3),
                    (2, '3c3d67925b108a37f88cc6663f7f7dd493fa818c', 1323367117.0, 3, 3),
                    (7311, '4ab289ab60aee93a66e5490529799cf4a2b4d94c', 1469607427.0, 24, 4)]

        self.assertEqual(len(issues), len(expected))

        for x in range(len(issues)):
            issue = issues[x]
            expc = expected[x]
            self.assertEqual(issue['data']['id'], expc[0])
            self.assertEqual(issue['uuid'], expc[1])
            self.assertEqual(issue['origin'], REDMINE_URL)
            self.assertEqual(issue['updated_on'], expc[2])
            self.assertEqual(issue['category'], 'issue')
            self.assertEqual(issue['tag'], REDMINE_URL)
            self.assertEqual(issue['data']['author_data']['id'], expc[3])
            self.assertEqual(issue['data']['journals'][0]['user_data']['id'], expc[4])

        # Check requests
        expected = [
            {
                'key': ['AAAA'],
                'status_id': ['*'],
                'sort': ['updated_on'],
                'updated_on': ['>=1970-01-01T00:00:00Z'],
                'offset': ['0'],
                'limit': ['3']
            },
            {
                'key': ['AAAA'],
                'include': ['attachments,changesets,children,journals,relations,watchers']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA'],
                'include': ['attachments,changesets,children,journals,relations,watchers']
            },
            {
                'key': ['AAAA'],
                'include': ['attachments,changesets,children,journals,relations,watchers']
            },
            {
                'key': ['AAAA'],
                'status_id': ['*'],
                'sort': ['updated_on'],
                'updated_on': ['>=1970-01-01T00:00:00Z'],
                'offset': ['3'],
                'limit': ['3']
            },
            {
                'key': ['AAAA'],
                'include': ['attachments,changesets,children,journals,relations,watchers']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA'],
                'status_id': ['*'],
                'sort': ['updated_on'],
                'updated_on': ['>=1970-01-01T00:00:00Z'],
                'offset': ['6'],
                'limit': ['3']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch()]

        issue = issues[0]
        self.assertEqual(redmine.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['data']['project']['name'], 'Global')
        self.assertEqual(issue['data']['project']['name'], issue['search_fields']['project_name'])
        self.assertEqual(issue['data']['project']['id'], 1)
        self.assertEqual(issue['data']['project']['id'], issue['search_fields']['project_id'])

        issue = issues[1]
        self.assertEqual(redmine.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['data']['project']['name'], 'Global')
        self.assertEqual(issue['data']['project']['name'], issue['search_fields']['project_name'])
        self.assertEqual(issue['data']['project']['id'], 1)
        self.assertEqual(issue['data']['project']['id'], issue['search_fields']['project_id'])

        issue = issues[2]
        self.assertEqual(redmine.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['data']['project']['name'], 'Global')
        self.assertEqual(issue['data']['project']['name'], issue['search_fields']['project_name'])
        self.assertEqual(issue['data']['project']['id'], 1)
        self.assertEqual(issue['data']['project']['id'], issue['search_fields']['project_id'])

        issue = issues[3]
        self.assertEqual(redmine.metadata_id(issue['data']), issue['search_fields']['item_id'])
        self.assertEqual(issue['data']['project']['name'], 'MAD')
        self.assertEqual(issue['data']['project']['name'], issue['search_fields']['project_name'])
        self.assertEqual(issue['data']['project']['id'], 91)
        self.assertEqual(issue['data']['project']['id'], issue['search_fields']['project_id'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test wether if fetches a set of issues from the given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 7, 27)

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 1)

        issue = issues[0]
        self.assertEqual(issue['data']['id'], 7311)
        self.assertEqual(issue['uuid'], '4ab289ab60aee93a66e5490529799cf4a2b4d94c')
        self.assertEqual(issue['origin'], REDMINE_URL)
        self.assertEqual(issue['updated_on'], 1469607427.0)
        self.assertEqual(issue['category'], 'issue')
        self.assertEqual(issue['tag'], REDMINE_URL)
        self.assertEqual(issue['data']['author_data']['id'], 24)
        self.assertEqual(issue['data']['journals'][0]['user_data']['id'], 4)

        expected = [
            {
                'key': ['AAAA'],
                'status_id': ['*'],
                'sort': ['updated_on'],
                'updated_on': ['>=2016-07-27T00:00:00Z'],
                'offset': ['0'],
                'limit': ['3']
            },
            {
                'key': ['AAAA'],
                'include': ['attachments,changesets,children,journals,relations,watchers']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA']
            },
            {
                'key': ['AAAA'],
                'status_id': ['*'],
                'sort': ['updated_on'],
                'updated_on': ['>=2016-07-27T00:00:00Z'],
                'offset': ['3'],
                'limit': ['3']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_not_found_user(self):
        """Test if it works when a user is not found"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 7, 27)

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 1)

        # The user 99 does not have information
        self.assertEqual(issues[0]['data']['journals'][1]['user']['id'], 99)
        self.assertDictEqual(issues[0]['data']['journals'][1]['user_data'], {})

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returnerd when there are no issues"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2017, 1, 1)

        redmine = Redmine(REDMINE_URL, api_token='AAAA',
                          max_issues=3)
        issues = [issue for issue in redmine.fetch(from_date=from_date)]

        self.assertEqual(len(issues), 0)

        expected = {
            'key': ['AAAA'],
            'status_id': ['*'],
            'sort': ['updated_on'],
            'updated_on': ['>=2017-01-01T00:00:00Z'],
            'offset': ['0'],
            'limit': ['3']
        }

        self.assertEqual(len(http_requests), 1)
        self.assertDictEqual(http_requests[0].querystring, expected)

    def test_parse_issues(self):
        """Test if it parses a issues stream"""

        raw_json = read_file('data/redmine/redmine_issues.json')

        issues = Redmine.parse_issues(raw_json)
        results = [issue for issue in issues]

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['id'], 9)
        self.assertEqual(results[1]['id'], 5)
        self.assertEqual(results[2]['id'], 2)

        # Parse a file without results
        raw_json = read_file('data/redmine/redmine_issues_empty.json')

        issues = Redmine.parse_issues(raw_json)
        results = [issue for issue in issues]

        self.assertEqual(len(results), 0)

    def test_parse_issue_data(self):
        """Test if it parses a issue stream"""

        raw_json = read_file('data/redmine/redmine_issue_7311.json')

        issue = Redmine.parse_issue_data(raw_json)

        self.assertEqual(issue['id'], 7311)
        self.assertEqual(len(issue['journals']), 22)
        self.assertEqual(len(issue['changesets']), 0)

    def test_parse_user_data(self):
        """"Test if it parses a user stream"""

        raw_json = read_file('data/redmine/redmine_user_3.json')

        user = Redmine.parse_user_data(raw_json)

        self.assertEqual(user['id'], 3)
        self.assertEqual(user['lastname'], 'User')
        self.assertEqual(user['login'], 'generic')


class TestRedmineBackendArchive(TestCaseBackendArchive):
    """Redmine backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Redmine(REDMINE_URL, api_token='AAAA', max_issues=3, archive=self.archive)
        self.backend_read_archive = Redmine(REDMINE_URL, api_token='BBBB', max_issues=3, archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether it fetches a set of issues from archive"""

        setup_http_server()
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test wether if fetches a set of issues from the given date from archive"""

        setup_http_server()

        from_date = datetime.datetime(2016, 7, 27)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test if nothing is returnerd when there are no issues from archive"""

        setup_http_server()

        from_date = datetime.datetime(2017, 1, 1)
        self._test_fetch_from_archive(from_date=from_date)


class TestRedmineCommand(unittest.TestCase):
    """Tests for RedmineCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Redmine"""

        self.assertIs(RedmineCommand.BACKEND, Redmine)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = RedmineCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Redmine)

        args = ['http://example.com',
                '--api-token', '12345678',
                '--max-issues', '5',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com')
        self.assertEqual(parsed_args.api_token, '12345678')
        self.assertEqual(parsed_args.max_issues, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)

        args = ['http://example.com',
                '--api-token', '12345678',
                '--max-issues', '5',
                '--tag', 'test',
                '--no-ssl-verify',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com')
        self.assertEqual(parsed_args.api_token, '12345678')
        self.assertEqual(parsed_args.max_issues, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


class TestRedmineClient(unittest.TestCase):
    """Redmine client unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization parameters"""

        client = RedmineClient(REDMINE_URL, 'aaaa')
        self.assertEqual(client.base_url, REDMINE_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertTrue(client.ssl_verify)

        client = RedmineClient(REDMINE_URL, 'aaaa', ssl_verify=False)
        self.assertEqual(client.base_url, REDMINE_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_issues(self):
        """Test if issues call works"""

        body = read_file('data/redmine/redmine_issues_next.json')

        httpretty.register_uri(httpretty.GET,
                               REDMINE_ISSUES_URL,
                               body=body, status=200)

        client = RedmineClient(REDMINE_URL, 'aaaa')
        dt = datetime.datetime(2016, 7, 1, 0, 0, 0)

        result = client.issues(from_date=dt, offset=10, max_issues=200)

        self.assertEqual(result, body)

        expected = {
            'key': ['aaaa'],
            'status_id': ['*'],
            'sort': ['updated_on'],
            'updated_on': ['>=2016-07-01T00:00:00Z'],
            'offset': ['10'],
            'limit': ['200']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/issues.json')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_issue(self):
        """Test if issue call works"""

        body = read_file('data/redmine/redmine_issue_7311.json')

        httpretty.register_uri(httpretty.GET,
                               REDMINE_ISSUE_7311_URL,
                               body=body, status=200)

        client = RedmineClient(REDMINE_URL, 'aaaa')

        result = client.issue(7311)

        self.assertEqual(result, body)

        expected = {
            'key': ['aaaa'],
            'include': ['attachments,changesets,children,journals,relations,watchers']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/issues/7311.json')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_user(self):
        """Test if user call works"""

        body = read_file('data/redmine/redmine_user_3.json')

        httpretty.register_uri(httpretty.GET,
                               REDMINE_USER_3_URL,
                               body=body, status=200)

        client = RedmineClient(REDMINE_URL, 'aaaa')

        result = client.user(3)

        self.assertEqual(result, body)

        expected = {
            'key': ['aaaa']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/users/3.json')
        self.assertDictEqual(req.querystring, expected)

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = "headers-information"
        payload = {'key': 'aaaa'}

        s_url, s_headers, s_payload = RedmineClient.sanitize_for_archive(url, headers, copy.deepcopy(payload))
        payload.pop("key")

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

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
#     Quan Zhou <quan@bitergia.com>
#


import datetime
import dateutil
import httpretty
import json
import os
import pkg_resources
import unittest
import warnings

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.weblate import (Weblate,
                                            WeblateClient,
                                            WeblateCommand)


WEBLATE_API_URL = 'https://my.weblate.org/api/'
WEBLATE_CHANGES_API_URL = WEBLATE_API_URL + 'changes'
WEBLATE_CHANGES_PAGE_2_API_URL = WEBLATE_CHANGES_API_URL + '/?page=2'
WEBLATE_USERS_API_URL = WEBLATE_API_URL + 'users'
WEBLATE_USER_1_API_URL = WEBLATE_USERS_API_URL + '/1'
WEBLATE_USER_2_API_URL = WEBLATE_USERS_API_URL + '/2'
WEBLATE_USER_NO_PERMISSION_API_URL = WEBLATE_USERS_API_URL + '/NoPermission'

NO_CHECK_FIELDS = ['timestamp', 'backend_version', 'perceval_version']


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server(archived_changes=False):
    """Setup a mock HTTP server"""

    http_requests = []

    if archived_changes:
        changes = read_file('data/weblate/weblate_changes_archived.json', 'rb')
    else:
        changes = read_file('data/weblate/weblate_changes.json', 'rb')
    changes_page_2 = read_file('data/weblate/weblate_changes_page_2.json', 'rb')

    user_1 = read_file('data/weblate/weblate_user_1.json', 'rb')
    user_2 = read_file('data/weblate/weblate_user_2.json', 'rb')
    user_no_permission = read_file('data/weblate/weblate_user_no_permission.json', 'rb')

    def request_callback(_, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        status = 200

        if uri.startswith(WEBLATE_CHANGES_API_URL):
            if 'timestamp_after' in params and '2020-01-01T00:00:00 00:00' in params['timestamp_after']:
                body = changes_page_2
            elif 'page' not in params:
                body = changes
            else:
                body = changes_page_2
        elif uri.startswith(WEBLATE_USER_1_API_URL):
            body = user_1
        elif uri.startswith(WEBLATE_USER_2_API_URL):
            body = user_2
        elif uri.startswith(WEBLATE_USER_NO_PERMISSION_API_URL):
            body = user_no_permission
        else:
            raise

        http_requests.append(last_request)

        return status, headers, body

    httpretty.register_uri(httpretty.GET,
                           WEBLATE_CHANGES_API_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    httpretty.register_uri(httpretty.GET,
                           WEBLATE_CHANGES_PAGE_2_API_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    httpretty.register_uri(httpretty.GET,
                           WEBLATE_USER_1_API_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    httpretty.register_uri(httpretty.GET,
                           WEBLATE_USER_2_API_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    httpretty.register_uri(httpretty.GET,
                           WEBLATE_USER_NO_PERMISSION_API_URL,
                           status=404,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestWeblateBackend(unittest.TestCase):
    """Weblate backend tests"""

    def test_initialization(self):
        """Test whether attributes are initialized"""

        weblate = Weblate('https://my.weblate.org', api_token='xxyyzz')

        self.assertEqual(weblate.origin, 'https://my.weblate.org')
        self.assertListEqual(weblate.categories, ['changes'])
        self.assertEqual(weblate.api_token, 'xxyyzz')

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Weblate.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Weblate.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test if it fetches a list of changes"""

        warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

        http_requests = setup_http_server()

        weblate = Weblate('https://my.weblate.org')
        changes = [change for change in weblate.fetch(from_date=None)]

        changes_expected = json.loads(read_file('data/weblate/weblate_changes_expected.json', 'r'))
        self.assertEqual(len(changes), len(changes_expected))

        # remove timestamp due to this value change for each execution
        changes_no_timestamp = [{k: v for k, v in change.items() if k not in NO_CHECK_FIELDS} for change in changes]
        changes_expected_no_timestamp = [{k: v for k, v in change.items() if k not in NO_CHECK_FIELDS}
                                         for change in changes_expected]
        self.assertListEqual(changes_no_timestamp, changes_expected_no_timestamp)

        requests_path_expected = [
            '/api/changes?timestamp_after=1970-01-01T00%3A00%3A00%2B00%3A00',
            '/api/users/1',
            '/api/users/1',
            '/api/users/2',
            '/api/users/2',
            '/api/changes/?page=2',
            '/api/users/2',
            '/api/users/2'
        ]
        self.assertEqual(len(http_requests), len(requests_path_expected))
        for i in range(len(http_requests)):
            self.assertEqual(http_requests[i].path, requests_path_expected[i])

    @httpretty.activate
    def test_fetch_archived(self):
        """Test if it fetches a list of changes from an archived file"""

        http_requests = setup_http_server(archived_changes=True)

        weblate = Weblate('https://my.weblate.org')
        changes = [change for change in weblate.fetch(from_date=None)]

        changes_expected = json.loads(read_file('data/weblate/weblate_changes_expected.json', 'r'))
        self.assertEqual(len(changes), len(changes_expected))

        # remove timestamp due to this value change for each execution
        changes_no_timestamp = [{k: v for k, v in change.items() if k not in NO_CHECK_FIELDS} for change in changes]
        changes_expected_no_timestamp = [{k: v for k, v in change.items() if k not in NO_CHECK_FIELDS} for change in
                                         changes_expected]
        self.assertListEqual(changes_no_timestamp, changes_expected_no_timestamp)

        requests_path_expected = [
            '/api/changes?timestamp_after=1970-01-01T00%3A00%3A00%2B00%3A00',
            '/api/users/1',
            '/api/users/1',
            '/api/users/2',
            '/api/users/2',
            '/api/users/2',
            '/api/users/2'
        ]
        self.assertEqual(len(http_requests), len(requests_path_expected))
        for i in range(len(http_requests)):
            self.assertEqual(http_requests[i].path, requests_path_expected[i])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test if it fetches a list of changes since a given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2020, 1, 1, 00, 00, 00, 00,
                                      tzinfo=dateutil.tz.tzutc())

        weblate = Weblate('https://my.weblate.org')
        changes = [change for change in weblate.fetch(from_date=from_date)]

        changes_expected_all = json.loads(read_file('data/weblate/weblate_changes_expected.json', 'r'))
        changes_expected = changes_expected_all[2:]
        self.assertEqual(len(changes), len(changes_expected))

        # remove timestamp due to this value change for each execution
        changes_no_timestamp = [{k: v for k, v in change.items() if k not in NO_CHECK_FIELDS} for change in changes]
        changes_expected_no_timestamp = [{k: v for k, v in change.items() if k not in NO_CHECK_FIELDS} for change in
                                         changes_expected]
        self.assertListEqual(changes_no_timestamp, changes_expected_no_timestamp)

        requests_path_expected = [
            '/api/changes?timestamp_after=2020-01-01T00%3A00%3A00%2B00%3A00',
            '/api/users/2',
            '/api/users/2'
        ]
        self.assertEqual(len(http_requests), len(requests_path_expected))
        for i in range(len(http_requests)):
            self.assertEqual(http_requests[i].path, requests_path_expected[i])

    def test_metadata_updated_on(self):
        """Test if metadata_updated_on converts date correctly"""

        weblate = Weblate('https://my.weblate.org')
        metadata_updated_on = weblate.metadata_updated_on({'timestamp': '2020-01-01'})
        self.assertEqual(metadata_updated_on, 1577836800.0)


class TestWeblateClient(unittest.TestCase):
    """Weblate API client tests."""

    def test_init(self):
        """Test initialization"""

        client = WeblateClient('https://my.weblate.org', api_token="xxyyzz")
        self.assertEqual(client.api_token, 'xxyyzz')
        self.assertTrue(client.ssl_verify)

        client = WeblateClient('https://my.weblate.org', api_token="xxyyzz",
                               project="test", ssl_verify=False)
        self.assertEqual(client.api_token, 'xxyyzz')
        self.assertEqual(client.project, "test")
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_user(self):
        """Test user API call"""

        http_requests = setup_http_server()

        client = WeblateClient('https://my.weblate.org', api_token="xxyyzz")

        user_1 = client.user(WEBLATE_USER_1_API_URL)

        user_1_expected = json.loads(read_file('data/weblate/weblate_user_1.json', 'r'))
        self.assertDictEqual(user_1, user_1_expected)

        requests_path_expected = [
            '/api/users/1'
        ]
        self.assertEqual(len(http_requests), len(requests_path_expected))
        for i in range(len(http_requests)):
            self.assertEqual(http_requests[i].path, requests_path_expected[i])

    @httpretty.activate
    def test_user_no_permission(self):
        """Test user API call when we don't have manager permission"""

        http_requests = setup_http_server()

        client = WeblateClient('https://my.weblate.org', api_token="xxyyzz")

        user = client.user(WEBLATE_USER_NO_PERMISSION_API_URL)

        user_expected = json.loads(read_file('data/weblate/weblate_user_no_permission.json', 'r'))
        self.assertDictEqual(user, user_expected)

        requests_path_expected = [
            '/api/users/NoPermission'
        ]
        self.assertEqual(len(http_requests), len(requests_path_expected))
        for i in range(len(http_requests)):
            self.assertEqual(http_requests[i].path, requests_path_expected[i])

    @httpretty.activate
    def test_changes(self):
        """Test changes API call"""

        http_requests = setup_http_server()

        client = WeblateClient('https://my.weblate.org', api_token="xxyyzz")

        changes = [change for change in client.changes()]

        changes_raw = json.loads(read_file('data/weblate/weblate_changes.json', 'r'))
        changes_raw_page_2 = json.loads(read_file('data/weblate/weblate_changes_page_2.json', 'r'))
        changes_expected_page_1 = changes_raw['results']
        changes_expected_page_2 = changes_raw_page_2['results']
        self.assertEqual(len(changes[0]), len(changes_expected_page_1))
        self.assertEqual(len(changes[1]), len(changes_expected_page_2))
        self.assertListEqual(changes[0], changes_expected_page_1)
        self.assertListEqual(changes[1], changes_expected_page_2)

        requests_path_expected = [
            '/api/changes',
            '/api/changes/?page=2'
        ]
        self.assertEqual(len(http_requests), len(requests_path_expected))
        for i in range(len(http_requests)):
            self.assertEqual(http_requests[i].path, requests_path_expected[i])

    @httpretty.activate
    def test_fetch(self):
        """Test if it fetches a list of changes"""

        http_requests = setup_http_server()

        client = WeblateClient('https://my.weblate.org', api_token="xxyyzz")

        changes_response = client.fetch(WEBLATE_CHANGES_API_URL)
        changes_raw = changes_response.json()

        changes_raw_expected = json.loads(read_file('data/weblate/weblate_changes.json', 'r'))
        self.assertDictEqual(changes_raw, changes_raw_expected)

        requests_path_expected = [
            '/api/changes'
        ]
        self.assertEqual(len(http_requests), len(requests_path_expected))
        for i in range(len(http_requests)):
            self.assertEqual(http_requests[i].path, requests_path_expected[i])


class TestWeblateCommand(unittest.TestCase):
    """WeblateCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Weblate"""

        self.assertIs(WeblateCommand.BACKEND, Weblate)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = WeblateCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Weblate)
        from_date = datetime.datetime(2020, 1, 1, 00, 00, 00, 00,
                                      tzinfo=dateutil.tz.tzutc())

        args = ['https://my.weblate.org', '--no-archive',
                '-t', 'xxyyzz',
                '--from-date', '2020-01-01',
                '--sleep-for-rate',
                '--min-rate-to-sleep', '10',
                '--project', 'test',
                '--max-retries', '5',
                '--sleep-time', '1']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'https://my.weblate.org')
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.api_token, 'xxyyzz')
        self.assertEqual(parsed_args.from_date, from_date)
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.min_rate_to_sleep, 10)
        self.assertEqual(parsed_args.project, 'test')
        self.assertEqual(parsed_args.max_retries, 5)
        self.assertEqual(parsed_args.sleep_time, 1)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

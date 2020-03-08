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
import os
import shutil
import unittest

import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import BackendError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.bugzillarest import (BugzillaREST,
                                                 BugzillaRESTCommand,
                                                 BugzillaRESTClient,
                                                 BugzillaRESTError)
from base import TestCaseBackendArchive


BUGZILLA_SERVER_URL = 'http://example.com'
BUGZILLA_LOGIN_URL = BUGZILLA_SERVER_URL + '/rest/login'
BUGZILLA_BUGS_URL = BUGZILLA_SERVER_URL + '/rest/bug'
BUGZILLA_BUGS_COMMENTS_1273442_URL = BUGZILLA_SERVER_URL + '/rest/bug/1273442/comment'
BUGZILLA_BUGS_HISTORY_1273442_URL = BUGZILLA_SERVER_URL + '/rest/bug/1273442/history'
BUGZILLA_BUGS_ATTACHMENTS_1273442_URL = BUGZILLA_SERVER_URL + '/rest/bug/1273442/attachment'
BUGZILLA_BUG_947945_URL = BUGZILLA_SERVER_URL + '/rest/bug/947945/'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server():
    http_requests = []

    bodies_bugs = [read_file('data/bugzilla/bugzilla_rest_bugs.json', mode='rb'),
                   read_file('data/bugzilla/bugzilla_rest_bugs_next.json', mode='rb'),
                   read_file('data/bugzilla/bugzilla_rest_bugs_empty.json', mode='rb')]
    body_comments = [read_file('data/bugzilla/bugzilla_rest_bugs_comments.json', mode='rb'),
                     read_file('data/bugzilla/bugzilla_rest_bugs_comments_empty.json', mode='rb')]
    body_history = [read_file('data/bugzilla/bugzilla_rest_bugs_history.json', mode='rb'),
                    read_file('data/bugzilla/bugzilla_rest_bugs_history_empty.json', mode='rb')]
    body_attachments = [read_file('data/bugzilla/bugzilla_rest_bugs_attachments.json', mode='rb'),
                        read_file('data/bugzilla/bugzilla_rest_bugs_attachments_empty.json', mode='rb')]

    def request_callback(method, uri, headers):
        if uri.startswith(BUGZILLA_BUGS_COMMENTS_1273442_URL):
            body = body_comments[0]
        elif uri.startswith(BUGZILLA_BUGS_HISTORY_1273442_URL):
            body = body_history[0]
        elif uri.startswith(BUGZILLA_BUGS_ATTACHMENTS_1273442_URL):
            body = body_attachments[0]
        elif uri.startswith(BUGZILLA_BUG_947945_URL):
            if uri.find('comment') > 0:
                body = body_comments[1]
            elif uri.find('history') > 0:
                body = body_history[1]
            else:
                body = body_attachments[1]
        else:
            body = bodies_bugs.pop(0)

        http_requests.append(httpretty.last_request())

        return (200, headers, body)

    httpretty.register_uri(httpretty.GET,
                           BUGZILLA_BUGS_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(3)
                           ])

    http_urls = [BUGZILLA_BUGS_COMMENTS_1273442_URL,
                 BUGZILLA_BUGS_HISTORY_1273442_URL,
                 BUGZILLA_BUGS_ATTACHMENTS_1273442_URL]

    suffixes = ['comment', 'history', 'attachment']

    for http_url in [BUGZILLA_BUG_947945_URL]:
        for suffix in suffixes:
            http_urls.append(http_url + suffix)

    for req_url in http_urls:
        httpretty.register_uri(httpretty.GET,
                               req_url,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

    return http_requests


class TestBugzillaRESTBackend(unittest.TestCase):
    """Bugzilla REST backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        bg = BugzillaREST(BUGZILLA_SERVER_URL, tag='test',
                          max_bugs=5)

        self.assertEqual(bg.url, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.origin, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.tag, 'test')
        self.assertEqual(bg.max_bugs, 5)
        self.assertIsNone(bg.client)
        self.assertTrue(bg.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in URL
        bg = BugzillaREST(BUGZILLA_SERVER_URL)
        self.assertEqual(bg.url, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.origin, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.tag, BUGZILLA_SERVER_URL)

        bg = BugzillaREST(BUGZILLA_SERVER_URL, tag='', ssl_verify=False)
        self.assertEqual(bg.url, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.origin, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.tag, BUGZILLA_SERVER_URL)
        self.assertFalse(bg.ssl_verify)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(BugzillaREST.has_resuming(), True)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(BugzillaREST.has_archiving(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of bugs is returned"""

        http_requests = setup_http_server()

        bg = BugzillaREST(BUGZILLA_SERVER_URL, max_bugs=2)
        bugs = [bug for bug in bg.fetch(from_date=None)]

        self.assertEqual(len(bugs), 3)

        self.assertEqual(bugs[0]['data']['id'], 1273442)
        self.assertEqual(len(bugs[0]['data']['comments']), 7)
        self.assertEqual(len(bugs[0]['data']['history']), 6)
        self.assertEqual(len(bugs[0]['data']['attachments']), 1)
        self.assertEqual(bugs[0]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[0]['uuid'], '68494ad0072ed9e09cecb8235649a38c443326db')
        self.assertEqual(bugs[0]['updated_on'], 1465257689.0)
        self.assertEqual(bugs[0]['category'], 'bug')
        self.assertEqual(bugs[0]['tag'], BUGZILLA_SERVER_URL)

        self.assertEqual(bugs[1]['data']['id'], 1273439)
        self.assertEqual(len(bugs[1]['data']['comments']), 0)
        self.assertEqual(len(bugs[1]['data']['history']), 0)
        self.assertEqual(len(bugs[1]['data']['attachments']), 0)
        self.assertEqual(bugs[1]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[1]['uuid'], 'd306162de06bc759f9bd9227fe3fd5f08aeb0dde')
        self.assertEqual(bugs[1]['updated_on'], 1465257715.0)
        self.assertEqual(bugs[1]['category'], 'bug')
        self.assertEqual(bugs[1]['tag'], BUGZILLA_SERVER_URL)

        self.assertEqual(bugs[2]['data']['id'], 947945)
        self.assertEqual(len(bugs[2]['data']['comments']), 0)
        self.assertEqual(len(bugs[2]['data']['history']), 0)
        self.assertEqual(len(bugs[2]['data']['attachments']), 0)
        self.assertEqual(bugs[2]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[2]['uuid'], '33edda925351c3310fc3e12d7f18a365c365f6bd')
        self.assertEqual(bugs[2]['updated_on'], 1465257743.0)
        self.assertEqual(bugs[2]['category'], 'bug')
        self.assertEqual(bugs[2]['tag'], BUGZILLA_SERVER_URL)

        # Check requests
        expected = [
            {
                'last_change_time': ['1970-01-01T00:00:00Z'],
                'limit': ['2'],
                'order': ['changeddate'],
                'include_fields': ['_all']
            },
            {
                'ids': ['1273442', '1273439']
            },
            {
                'ids': ['1273442', '1273439']
            },
            {
                'ids': ['1273442', '1273439'],
                'exclude_fields': ['data']
            },
            {
                'last_change_time': ['1970-01-01T00:00:00Z'],
                'offset': ['2'],
                'limit': ['2'],
                'order': ['changeddate'],
                'include_fields': ['_all']
            },
            {
                'ids': ['947945']
            },
            {
                'ids': ['947945']
            },
            {
                'ids': ['947945'],
                'exclude_fields': ['data']
            },
            {
                'last_change_time': ['1970-01-01T00:00:00Z'],
                'offset': ['4'],
                'limit': ['2'],
                'order': ['changeddate'],
                'include_fields': ['_all']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        bg = BugzillaREST(BUGZILLA_SERVER_URL, max_bugs=2)
        bugs = [bug for bug in bg.fetch(from_date=None)]

        self.assertEqual(len(bugs), 3)

        bug = bugs[0]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'], 'Connected Devices')
        self.assertEqual(bug['data']['product'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'], 'Project Sensor Web')
        self.assertEqual(bug['data']['component'], bug['search_fields']['component'])

        bug = bugs[1]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'], 'Connected Devices')
        self.assertEqual(bug['data']['product'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'], 'Project Sensor Web')
        self.assertEqual(bug['data']['component'], bug['search_fields']['component'])

        bug = bugs[2]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'], 'MailNews Core')
        self.assertEqual(bug['data']['product'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'], 'Backend')
        self.assertEqual(bug['data']['component'], bug['search_fields']['component'])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no bugs are fetched"""

        body = read_file('data/bugzilla/bugzilla_rest_bugs_empty.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_URL,
                               body=body, status=200)

        bg = BugzillaREST(BUGZILLA_SERVER_URL)
        bugs = [bug for bug in bg.fetch()]

        self.assertEqual(len(bugs), 0)


class TestBugzillaRESTBackendArchive(TestCaseBackendArchive):
    """Bugzilla REST backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = BugzillaREST(BUGZILLA_SERVER_URL,
                                                  user='jsmith@example.com', password='1234',
                                                  max_bugs=2, archive=self.archive)
        self.backend_read_archive = BugzillaREST(BUGZILLA_SERVER_URL,
                                                 user='jreno@example.com', password='5678',
                                                 max_bugs=2, archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of bugs is returned from the archive"""

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_LOGIN_URL,
                               body='{"token": "786-OLaWfBisMY", "id": "786"}',
                               status=200)
        setup_http_server()
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether it works when no bugs are fetched from the archive"""

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_LOGIN_URL,
                               body='{"token": "786-OLaWfBisMY", "id": "786"}',
                               status=200)
        body = read_file('data/bugzilla/bugzilla_rest_bugs_empty.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_URL,
                               body=body, status=200)

        self._test_fetch_from_archive(from_date=None)


class TestBugzillaRESTClient(unittest.TestCase):
    """Bugzilla REST API client tests

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""

        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        self.assertEqual(client.base_url, BUGZILLA_SERVER_URL)
        self.assertEqual(client.api_token, None)
        self.assertTrue(client.ssl_verify)

        client = BugzillaRESTClient(BUGZILLA_SERVER_URL, ssl_verify=False)
        self.assertEqual(client.base_url, BUGZILLA_SERVER_URL)
        self.assertEqual(client.api_token, None)
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_init_auth(self):
        """Test initialization with authentication"""

        # Set up a mock HTTP server
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_LOGIN_URL,
                               body='{"token": "786-OLaWfBisMY", "id": "786"}',
                               status=200)

        client = BugzillaRESTClient(BUGZILLA_SERVER_URL,
                                    user='jsmith@example.com',
                                    password='1234')

        self.assertEqual(client.api_token, '786-OLaWfBisMY')

        # Check request params
        expected = {
            'login': ['jsmith@example.com'],
            'password': ['1234'],
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/login')
        self.assertEqual(req.querystring, expected)

    @httpretty.activate
    def test_invalid_auth(self):
        """Test whether it fails when the authentication goes wrong"""

        # Set up a mock HTTP server
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_LOGIN_URL,
                               body="401 Client Error: Authorization Required",
                               status=401)

        with self.assertRaises(BackendError):
            _ = BugzillaRESTClient(BUGZILLA_SERVER_URL,
                                   user='jsmith@example.com',
                                   password='1234')

    @httpretty.activate
    def test_auth_token_call(self):
        """Test whether the API token is included on the calls when it was set"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_rest_bugs.json')

        # Set up a mock HTTP server
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_LOGIN_URL,
                               body='{"token": "786-OLaWfBisMY", "id": "786"}',
                               status=200)

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_URL,
                               body=body, status=200)

        # Test API token login
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL,
                                    user='jsmith@example.com',
                                    password='1234')

        self.assertEqual(client.api_token, '786-OLaWfBisMY')

        # Check whether it is included on the calls
        _ = client.bugs()

        # Check request params
        expected = {
            'last_change_time': ['1970-01-01T00:00:00Z'],
            'limit': ['500'],
            'order': ['changeddate'],
            'include_fields': ['_all'],
            'token': ['786-OLaWfBisMY']
        }

        req = httpretty.last_request()
        self.assertDictEqual(req.querystring, expected)

        # Test API token initialization
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL,
                                    api_token='ABCD')
        _ = client.bugs()

        expected = {
            'last_change_time': ['1970-01-01T00:00:00Z'],
            'limit': ['500'],
            'order': ['changeddate'],
            'include_fields': ['_all'],
            'token': ['ABCD']
        }

        req = httpretty.last_request()
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_bugs(self):
        """Test bugs API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_rest_bugs.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.bugs()

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'last_change_time': ['1970-01-01T00:00:00Z'],
            'limit': ['500'],
            'order': ['changeddate'],
            'include_fields': ['_all']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug')
        self.assertDictEqual(req.querystring, expected)

        # Call API with parameters
        from_date = datetime.datetime(2016, 6, 7, 0, 0, 0)

        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.bugs(from_date=from_date, offset=100, max_bugs=5)

        self.assertEqual(response, body)

        expected = {
            'last_change_time': ['2016-06-07T00:00:00Z'],
            'offset': ['100'],
            'limit': ['5'],
            'order': ['changeddate'],
            'include_fields': ['_all']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_comments(self):
        """Test comments API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_rest_bugs_comments.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_COMMENTS_1273442_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.comments('1273442', '1273439')

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'ids': ['1273442', '1273439']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug/1273442/comment')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_history(self):
        """Test history API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_rest_bugs_history.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_HISTORY_1273442_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.history('1273442', '1273439')

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'ids': ['1273442', '1273439']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug/1273442/history')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_attachments(self):
        """Test attachments API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_rest_bugs_attachments.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_ATTACHMENTS_1273442_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.attachments('1273442', '1273439')

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'ids': ['1273442', '1273439'],
            'exclude_fields': ['data']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug/1273442/attachment')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_user_agent_header(self):
        """Test if the User-Agent header is included on every API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_rest_bugs_history.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_HISTORY_1273442_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.history('1273442', '1273439')

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'ids': ['1273442', '1273439']
        }

        req = httpretty.last_request()
        user_agent = req.headers['User-Agent']
        self.assertEqual(user_agent.startswith('Perceval/'), True)

    @httpretty.activate
    def test_rest_error(self):
        """Test if an exception is raised when the server returns an error"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_rest_error.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_URL,
                               body=body, status=200)

        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)

        with self.assertRaises(BugzillaRESTError) as e:
            _ = client.call('bug', {})
            self.assertEqual(e.exception.code, 32000)
            self.assertEqual(e.exception.error,
                             "API key authentication is required.")

    def test_sanitize_for_archive_login(self):
        """Test whether the sanitize method works properly when login"""

        url = "http://example.com"
        headers = "headers-information"
        payload = {'login': 'jsmith@example.com', 'password': '1234'}

        s_url, s_headers, s_payload = BugzillaRESTClient.sanitize_for_archive(url, headers, copy.deepcopy(payload))
        payload.pop('login')
        payload.pop('password')

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)

    def test_sanitize_for_archive_token(self):
        """Test whether the sanitize method works properly for token-signed requests"""

        payload = {'limit': 2,
                   'order': 'changeddate',
                   'token': '786-OLaWfBisMY',
                   'include_fields': '_all',
                   'last_change_time': '1970-01-01T00:00:00Z'}

        url, headers, payload = BugzillaRESTClient.sanitize_for_archive(None, None, payload)
        with self.assertRaises(KeyError):
            payload.pop('token')


class TestBugzillaRESTCommand(unittest.TestCase):
    """BugzillaRESTCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Bugzilla"""

        self.assertIs(BugzillaRESTCommand.BACKEND, BugzillaREST)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = BugzillaRESTCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, BugzillaREST)

        args = ['--backend-user', 'jsmith@example.com',
                '--backend-password', '1234',
                '--api-token', 'abcdefg',
                '--max-bugs', '10', '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-archive',
                BUGZILLA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith@example.com')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.api_token, 'abcdefg')
        self.assertEqual(parsed_args.max_bugs, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.url, BUGZILLA_SERVER_URL)

        args = ['--backend-user', 'jsmith@example.com',
                '--backend-password', '1234',
                '--api-token', 'abcdefg',
                '--max-bugs', '10', '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-ssl-verify',
                BUGZILLA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith@example.com')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.api_token, 'abcdefg')
        self.assertEqual(parsed_args.max_bugs, 10)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.url, BUGZILLA_SERVER_URL)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

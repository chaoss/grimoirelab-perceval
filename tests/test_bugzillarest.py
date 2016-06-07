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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import datetime
import sys
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.errors import BackendError
from perceval.backends.bugzillarest import BugzillaRESTClient


BUGZILLA_SERVER_URL = 'http://example.com'
BUGZILLA_LOGIN_URL = BUGZILLA_SERVER_URL + '/rest/login'
BUGZILLA_BUGS_URL = BUGZILLA_SERVER_URL + '/rest/bug'
BUGZILLA_BUGS_COMMENTS_1273442_URL =  BUGZILLA_SERVER_URL + '/rest/bug/1273442/comment'
BUGZILLA_BUGS_HISTORY_1273442_URL =  BUGZILLA_SERVER_URL + '/rest/bug/1273442/history'
BUGZILLA_BUGS_ATTACHMENTS_1273442_URL =  BUGZILLA_SERVER_URL + '/rest/bug/1273442/attachment'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


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
                    'login' : ['jsmith@example.com'],
                    'password' : ['1234'],
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
        body = read_file('data/bugzilla_rest_bugs.json')

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
                     'last_change_time' : ['1970-01-01T00:00:00Z'],
                     'limit' : ['500'],
                     'order' : ['changeddate'],
                     'include_fields' : ['_all'],
                     'token' :  ['786-OLaWfBisMY']
                   }

        req = httpretty.last_request()
        self.assertDictEqual(req.querystring, expected)

        # Test API token initialization
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL,
                                    api_token='ABCD')
        _ = client.bugs()

        expected = {
                    'last_change_time' : ['1970-01-01T00:00:00Z'],
                    'limit' : ['500'],
                    'order' : ['changeddate'],
                    'include_fields' : ['_all'],
                    'token' :  ['ABCD']
                   }

        req = httpretty.last_request()
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_bugs(self):
        """Test bugs API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_rest_bugs.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_URL,
                               body=body, status=200)


        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.bugs()

        self.assertEqual(response, body)

        # Check request params
        expected = {
                     'last_change_time' : ['1970-01-01T00:00:00Z'],
                     'limit' : ['500'],
                     'order' : ['changeddate'],
                     'include_fields' : ['_all']
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
                    'last_change_time' : ['2016-06-07T00:00:00Z'],
                    'offset' : ['100'],
                    'limit' : ['5'],
                    'order' : ['changeddate'],
                    'include_fields' : ['_all']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_comments(self):
        """Test comments API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_rest_bug_comments.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_COMMENTS_1273442_URL,
                               body=body, status=200)


        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.comments('1273442')

        self.assertEqual(response, body)

        # Check request params
        expected = {}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug/1273442/comment')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_history(self):
        """Test history API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_rest_bug_history.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_HISTORY_1273442_URL,
                               body=body, status=200)


        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.history('1273442')

        self.assertEqual(response, body)

        # Check request params
        expected = {}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug/1273442/history')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_attachments(self):
        """Test attachments API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_rest_bug_attachments.json')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGS_ATTACHMENTS_1273442_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaRESTClient(BUGZILLA_SERVER_URL)
        response = client.attachments('1273442')

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'exclude_fields' : ['data']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/rest/bug/1273442/attachment')
        self.assertDictEqual(req.querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

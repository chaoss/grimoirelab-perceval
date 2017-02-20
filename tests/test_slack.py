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
#     Santiago Dueñas <sduenas@bitergia.com>
#

import sys
import unittest

import httpretty
import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backends.core.slack import SlackClient, SlackClientError


SLACK_API_URL = 'https://slack.com/api'
SLACK_CHANNEL_HISTORY_URL = SLACK_API_URL + '/channels.history'
SLACK_USER_INFO_URL = SLACK_API_URL + '/users.info'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    channel_error = read_file('data/slack/slack_error.json', 'rb')
    channel_history = read_file('data/slack/slack_history.json', 'rb')
    channel_history_next = read_file('data/slack/slack_history_next.json', 'rb')
    user_U0001 = read_file('data/slack/slack_user_U0001.json', 'rb')

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        status = 200

        if uri.startswith(SLACK_CHANNEL_HISTORY_URL):
            if params['channel'][0] != 'C011DUKE8':
                body = channel_error
            elif 'latest' not in params:
                body = channel_history
            elif params['oldest'][0] == '1' and \
                params['latest'][0] == '1427135733.000068':
                body = channel_history_next
        elif uri.startswith(SLACK_USER_INFO_URL):
            body = user_U0001
        else:
            raise

        http_requests.append(last_request)

        return (status, headers, body)

    httpretty.register_uri(httpretty.GET,
                           SLACK_CHANNEL_HISTORY_URL,
                           responses=[
                                httpretty.Response(body=request_callback) \
                                    for _ in range(1)
                           ])

    httpretty.register_uri(httpretty.GET,
                           SLACK_USER_INFO_URL,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestSlackClient(unittest.TestCase):
    """Slack API client tests.

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    def test_init(self):
        """Test initialization"""

        client = SlackClient('aaaa', max_items=5)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_items, 5)

    @httpretty.activate
    def test_history(self):
        """Test channel history API call"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        # Call API
        _ = client.history('C011DUKE8',
                           oldest=1, latest=1427135733.000068)

        expected = {
            'channel' : ['C011DUKE8'],
            'oldest' : ['1'],
            'latest' : ['1427135733.000068'],
            'token' : ['aaaa'],
            'count' : ['5']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/channels.history')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_user(self):
        """Test user info API call"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        # Call API
        _ = client.user('U0001')

        expected = {
            'user' : ['U0001'],
            'token' : ['aaaa']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/users.info')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_slack_error(self):
        """Test if an exception is raised when an error is returned by the server"""

        setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        with self.assertRaises(SlackClientError):
            _ = client.history('CH0')


if __name__ == "__main__":
    unittest.main(warnings='ignore')

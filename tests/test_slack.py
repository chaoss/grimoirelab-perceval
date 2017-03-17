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

import datetime
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import dateutil
import httpretty
import pkg_resources

# Hack to make sure that tests import the right packages
# due to setuptools behaviour
sys.path.insert(0, '..')
pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.slack import (Slack,
                                          SlackClient,
                                          SlackClientError,
                                          SlackCommand)


SLACK_API_URL = 'https://slack.com/api'
SLACK_CHANNEL_INFO_URL = SLACK_API_URL + '/channels.info'
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
    channel_empty = read_file('data/slack/slack_history_empty.json', 'rb')
    channel_info = read_file('data/slack/slack_info.json', 'rb')
    channel_history = read_file('data/slack/slack_history.json', 'rb')
    channel_history_next = read_file('data/slack/slack_history_next.json', 'rb')
    channel_history_date = read_file('data/slack/slack_history_20150323.json', 'rb')
    user_U0001 = read_file('data/slack/slack_user_U0001.json', 'rb')
    user_U0002 = read_file('data/slack/slack_user_U0002.json', 'rb')
    user_U0003 = read_file('data/slack/slack_user_U0003.json', 'rb')

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        status = 200

        if uri.startswith(SLACK_CHANNEL_INFO_URL):
            body = channel_info
        elif uri.startswith(SLACK_CHANNEL_HISTORY_URL):
            if params['channel'][0] != 'C011DUKE8':
                body = channel_error
            elif 'latest' not in params:
                body = channel_history
            elif (params['oldest'][0] == '1' and
                  params['latest'][0] == '1427135733.000068'):
                body = channel_history_next
            elif (params['oldest'][0] == '0' and
                  params['latest'][0] == '1483228800.0'):
                body = channel_history
            elif (params['oldest'][0] == '0' and
                  params['latest'][0] == '1427135733.000068'):
                body = channel_history_next
            elif (params['oldest'][0] == '1427135740.000068' and
                  params['latest'][0] == '1483228800.0'):
                body = channel_history_date
            elif (params['oldest'][0] == '1451606399.999999' and
                  params['latest'][0] == '1483228800.0'):
                body = channel_empty
        elif uri.startswith(SLACK_USER_INFO_URL):
            if params['user'][0] == 'U0001':
                body = user_U0001
            elif params['user'][0] == 'U0002':
                body = user_U0002
            else:
                body = user_U0003
        else:
            raise

        http_requests.append(last_request)

        return (status, headers, body)

    httpretty.register_uri(httpretty.GET,
                           SLACK_CHANNEL_INFO_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    httpretty.register_uri(httpretty.GET,
                           SLACK_CHANNEL_HISTORY_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(1)
                           ])

    httpretty.register_uri(httpretty.GET,
                           SLACK_USER_INFO_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestSlackBackend(unittest.TestCase):
    """Slack backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        slack = Slack('C011DUKE8', 'aaaa', max_items=5, tag='test')

        self.assertEqual(slack.origin, 'https://slack.com/C011DUKE8')
        self.assertEqual(slack.tag, 'test')
        self.assertEqual(slack.channel, 'C011DUKE8')
        self.assertEqual(slack.max_items, 5)
        self.assertIsInstance(slack.client, SlackClient)
        self.assertEqual(slack.client.api_token, 'aaaa')

        # When tag is empty or None it will be set to
        # the value in URL
        slack = Slack('C011DUKE8', 'aaaa')
        self.assertEqual(slack.origin, 'https://slack.com/C011DUKE8')
        self.assertEqual(slack.tag, 'https://slack.com/C011DUKE8')

        slack = Slack('C011DUKE8', 'aaaa', tag='')
        self.assertEqual(slack.origin, 'https://slack.com/C011DUKE8')
        self.assertEqual(slack.tag, 'https://slack.com/C011DUKE8')

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Slack.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(Slack.has_resuming(), False)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch(self, mock_utcnow):
        """Test if it fetches a list of messages"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        http_requests = setup_http_server()

        slack = Slack('C011DUKE8', 'aaaa', max_items=5)
        messages = [msg for msg in slack.fetch()]

        expected = [
            ("There are no events this week.",
             'b48fd01f4e010597091b7e44cecfb6074f56a1a6',
             1486969200.000136, 'B0001', 'test channel'),
            ("<@U0003|dizquierdo> has joined the channel",
             'bb95a1facf7d61baaf57322f3d6b6d2d45af8aeb',
             1427799888.0, 'dizquierdo@example.com', 'test channel'),
            ("tengo el m\u00f3vil",
             'f8668de6fadeb5730e0a80d4c8e5d3f8d175f4d5',
             1427135890.000071, 'jsmanrique@example.com', 'test channel'),
            ("hey acs",
             '29c2942a704c4e0b067daeb76edb2f826376cecf',
             1427135835.000070, 'jsmanrique@example.com', 'test channel'),
            ("¿vale?",
             '757e88ea008db0fff739dd261179219aedb84a95',
             1427135740.000069, 'acs@example.com', 'test channel'),
            ("jsmanrique: tenemos que dar m\u00e9tricas super chulas",
             'e92555381bc431a53c0b594fc118850eafd6e212',
             1427135733.000068, 'acs@example.com', 'test channel'),
            ("hi!",
             'b92892e7b65add0e83d0839de20b2375a42014e8',
             1427135689.000067, 'jsmanrique@example.com', 'test channel'),
            ("hi!",
             'e59d9ca0d9a2ba1c747dc60a0904edd22d69e20e',
             1427135634.000066, 'acs@example.com', 'test channel')
        ]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            expc = expected[x]
            self.assertEqual(message['data']['text'], expc[0])
            self.assertEqual(message['uuid'], expc[1])
            self.assertEqual(message['origin'], 'https://slack.com/C011DUKE8')
            self.assertEqual(message['updated_on'], expc[2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://slack.com/C011DUKE8')

            # The first message was sent by a bot
            if x == 0:
                self.assertEqual(message['data']['bot_id'], expc[3])
            else:
                self.assertEqual(message['data']['user_data']['profile']['email'], expc[3])

            self.assertEqual(message['data']['channel_info']['name'], expc[4])

        # Check requests
        expected = [
            {
                'channel': ['C011DUKE8'],
                'token': ['aaaa']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1483228800.0'],
                'token': ['aaaa'],
                'count': ['5']
            },
            {
                'user': ['U0003'],
                'token': ['aaaa']
            },
            {
                'user': ['U0002'],
                'token': ['aaaa']
            },
            {
                'user': ['U0001'],
                'token': ['aaaa']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1427135733.000068'],
                'token': ['aaaa'],
                'count': ['5']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch_from_date(self, mock_utcnow):
        """Test if it fetches a list of messages since a given date"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        http_requests = setup_http_server()

        from_date = datetime.datetime(2015, 3, 23, 18, 35, 40, 69,
                                      tzinfo=dateutil.tz.tzutc())

        slack = Slack('C011DUKE8', 'aaaa', max_items=5)
        messages = [msg for msg in slack.fetch(from_date=from_date)]

        expected = [
            ("There are no events this week.",
             'b48fd01f4e010597091b7e44cecfb6074f56a1a6',
             1486969200.000136, 'B0001', 'test channel'),
            ("<@U0003|dizquierdo> has joined the channel",
             'bb95a1facf7d61baaf57322f3d6b6d2d45af8aeb',
             1427799888.0, 'dizquierdo@example.com', 'test channel'),
            ("tengo el m\u00f3vil",
             'f8668de6fadeb5730e0a80d4c8e5d3f8d175f4d5',
             1427135890.000071, 'jsmanrique@example.com', 'test channel'),
            ("hey acs",
             '29c2942a704c4e0b067daeb76edb2f826376cecf',
             1427135835.000070, 'jsmanrique@example.com', 'test channel')
        ]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            expc = expected[x]
            self.assertEqual(message['data']['text'], expc[0])
            self.assertEqual(message['uuid'], expc[1])
            self.assertEqual(message['origin'], 'https://slack.com/C011DUKE8')
            self.assertEqual(message['updated_on'], expc[2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://slack.com/C011DUKE8')

            # The first message was sent by a bot
            if x == 0:
                self.assertEqual(message['data']['bot_id'], expc[3])
            else:
                self.assertEqual(message['data']['user_data']['profile']['email'], expc[3])

            self.assertEqual(message['data']['channel_info']['name'], expc[4])

        # Check requests
        expected = [
            {
                'channel': ['C011DUKE8'],
                'token': ['aaaa']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['1427135740.000068'],
                'latest': ['1483228800.0'],
                'token': ['aaaa'],
                'count': ['5']
            },
            {
                'user': ['U0003'],
                'token': ['aaaa']
            },
            {
                'user': ['U0002'],
                'token': ['aaaa']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch_empty(self, mock_utcnow):
        """Test if nothing is returned when there are no messages"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 1, 1,
                                      tzinfo=dateutil.tz.tzutc())

        slack = Slack('C011DUKE8', 'aaaa', max_items=5)
        messages = [msg for msg in slack.fetch(from_date=from_date)]

        self.assertEqual(len(messages), 0)

        # Check requests
        expected = [
            {
                'channel': ['C011DUKE8'],
                'token': ['aaaa']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['1451606399.999999'],
                'latest': ['1483228800.0'],
                'token': ['aaaa'],
                'count': ['5']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    def test_parse_channel_info(self):
        """Test if it parses a channel info JSON stream"""

        raw_json = read_file('data/slack/slack_info.json')

        user = Slack.parse_channel_info(raw_json)

        self.assertEqual(user['id'], 'C011DUKE8')
        self.assertEqual(user['name'], 'test channel')

    def test_parse_history(self):
        """Test if it parses a channel history JSON stream"""

        raw_json = read_file('data/slack/slack_history.json')

        items, has_more = Slack.parse_history(raw_json)
        results = [item for item in items]

        self.assertEqual(len(results), 6)
        self.assertEqual(results[0]['ts'], '1486969200.000136')
        self.assertEqual(results[1]['ts'], '1427799888.000000')
        self.assertEqual(results[2]['ts'], '1427135890.000071')
        self.assertEqual(results[3]['ts'], '1427135835.000070')
        self.assertEqual(results[4]['ts'], '1427135740.000069')
        self.assertEqual(results[5]['ts'], '1427135733.000068')
        self.assertEqual(has_more, True)

        # Parse a file without results
        raw_json = read_file('data/slack/slack_history_empty.json')

        items, has_more = Slack.parse_history(raw_json)
        results = [item for item in items]

        self.assertEqual(len(results), 0)
        self.assertEqual(has_more, False)

    def test_parse_user(self):
        """Test if it parses a user info JSON stream"""

        raw_json = read_file('data/slack/slack_user_U0001.json')

        user = Slack.parse_user(raw_json)

        self.assertEqual(user['id'], 'U0001')
        self.assertEqual(user['name'], 'acs')
        self.assertEqual(user['profile']['email'], 'acs@example.com')


class TestSlackBackendCache(unittest.TestCase):
    """Slack backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch_from_cache(self, mock_utcnow):
        """Test whether the cache works"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        http_requests = setup_http_server()

        # First, we fetch the events from the server,
        # storing them in a cache
        cache = Cache(self.tmp_path)
        slack = Slack('C011DUKE8', 'aaaa', max_items=5, cache=cache)
        messages = [msg for msg in slack.fetch()]

        self.assertEqual(len(http_requests), 6)

        # Now, we get the messages from the cache.
        # The events should be the same and there won't be
        # any new request to the server
        cached_messages = [msg for msg in slack.fetch_from_cache()]
        self.assertEqual(len(cached_messages), len(messages))

        expected = [
            ("There are no events this week.",
             'b48fd01f4e010597091b7e44cecfb6074f56a1a6',
             1486969200.000136, 'B0001', 'test channel'),
            ("<@U0003|dizquierdo> has joined the channel",
             'bb95a1facf7d61baaf57322f3d6b6d2d45af8aeb',
             1427799888.0, 'dizquierdo@example.com', 'test channel'),
            ("tengo el m\u00f3vil",
             'f8668de6fadeb5730e0a80d4c8e5d3f8d175f4d5',
             1427135890.000071, 'jsmanrique@example.com', 'test channel'),
            ("hey acs",
             '29c2942a704c4e0b067daeb76edb2f826376cecf',
             1427135835.000070, 'jsmanrique@example.com', 'test channel'),
            ("¿vale?",
             '757e88ea008db0fff739dd261179219aedb84a95',
             1427135740.000069, 'acs@example.com', 'test channel'),
            ("jsmanrique: tenemos que dar m\u00e9tricas super chulas",
             'e92555381bc431a53c0b594fc118850eafd6e212',
             1427135733.000068, 'acs@example.com', 'test channel'),
            ("hi!",
             'b92892e7b65add0e83d0839de20b2375a42014e8',
             1427135689.000067, 'jsmanrique@example.com', 'test channel'),
            ("hi!",
             'e59d9ca0d9a2ba1c747dc60a0904edd22d69e20e',
             1427135634.000066, 'acs@example.com', 'test channel')
        ]

        self.assertEqual(len(cached_messages), len(expected))

        for x in range(len(cached_messages)):
            cmessage = cached_messages[x]
            expc = expected[x]
            self.assertEqual(cmessage['data']['text'], expc[0])
            self.assertEqual(cmessage['uuid'], expc[1])
            self.assertEqual(cmessage['origin'], 'https://slack.com/C011DUKE8')
            self.assertEqual(cmessage['updated_on'], expc[2])
            self.assertEqual(cmessage['category'], 'message')
            self.assertEqual(cmessage['tag'], 'https://slack.com/C011DUKE8')

            # The first message was sent by a bot
            if x == 0:
                self.assertEqual(cmessage['data']['bot_id'], expc[3])
            else:
                self.assertEqual(cmessage['data']['user_data']['profile']['email'], expc[3])

            self.assertEqual(cmessage['data']['channel_info']['name'], expc[4])

            # Compare chached and fetched message
            self.assertDictEqual(cmessage['data'], messages[x]['data'])

        # No more requests were sent
        self.assertEqual(len(http_requests), 6)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any message returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        slack = Slack('C011DUKE8', 'aaaa', max_items=5, cache=cache)
        cached_messages = [msg for msg in slack.fetch_from_cache()]
        self.assertEqual(len(cached_messages), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        slack = Slack('C011DUKE8', 'aaaa', max_items=5)

        with self.assertRaises(CacheError):
            _ = [msg for msg in slack.fetch_from_cache()]


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
    def test_channel_info(self):
        """Test channel info API call"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        _ = client.channel_info('C011DUKE8')

        expected = {
            'channel': ['C011DUKE8'],
            'token': ['aaaa'],
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/channels.info')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_history(self):
        """Test channel history API call"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        # Call API
        _ = client.history('C011DUKE8',
                           oldest=1, latest=1427135733.000068)

        expected = {
            'channel': ['C011DUKE8'],
            'oldest': ['1'],
            'latest': ['1427135733.000068'],
            'token': ['aaaa'],
            'count': ['5']
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
            'user': ['U0001'],
            'token': ['aaaa']
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


class TestSlackCommand(unittest.TestCase):
    """SlackCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Slack"""

        self.assertIs(SlackCommand.BACKEND, Slack)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = SlackCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--tag', 'test', '--no-cache',
                '--api-token', 'abcdefgh',
                '--from-date', '1970-01-01',
                '--max-items', '10',
                'C001']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.channel, 'C001')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.no_cache, True)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')
        self.assertEqual(parsed_args.max_items, 10)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

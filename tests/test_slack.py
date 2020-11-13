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
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import copy
import datetime
import dateutil
import httpretty
import os
import pkg_resources
import unittest
import unittest.mock

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.slack import (logger,
                                          Slack,
                                          SlackClient,
                                          SlackClientError,
                                          SlackCommand)
from base import TestCaseBackendArchive


SLACK_API_URL = 'https://slack.com/api/'
SLACK_CHANNEL_INFO_URL = SLACK_API_URL + SlackClient.RCONVERSATION_INFO
SLACK_CHANNEL_HISTORY_URL = SLACK_API_URL + SlackClient.RCHANNEL_HISTORY
SLACK_CONVERSATION_MEMBERS = SLACK_API_URL + SlackClient.RCONVERSATION_MEMBERS
SLACK_USER_INFO_URL = SLACK_API_URL + SlackClient.RUSER_INFO


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server(archived_channel=False):
    """Setup a mock HTTP server"""

    http_requests = []

    channel_error = read_file('data/slack/slack_error.json', 'rb')
    channel_empty = read_file('data/slack/slack_history_empty.json', 'rb')

    if archived_channel:
        channel_info = read_file('data/slack/slack_info_archived.json', 'rb')
    else:
        channel_info = read_file('data/slack/slack_info.json', 'rb')

    conversation_members_1 = read_file('data/slack/slack_members1.json', 'rb')
    conversation_members_2 = read_file('data/slack/slack_members2.json', 'rb')
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
            elif (params['oldest'][0] == '0.999990' and
                  params['latest'][0] == '1427135733.000068'):
                body = channel_history_next
            elif (params['oldest'][0] == '0' and
                  params['latest'][0] == '1483228800.000000'):
                body = channel_history
            elif (params['oldest'][0] == '0' and
                  params['latest'][0] == '1427135733.000068'):
                body = channel_history_next
            elif (params['oldest'][0] == '1427135740.000059' and
                  params['latest'][0] == '1483228800.000000'):
                body = channel_history_date
            elif (params['oldest'][0] == '1451606399.999990' and
                  params['latest'][0] == '1483228800.000000'):
                body = channel_empty
            else:
                raise Exception
        elif uri.startswith(SLACK_USER_INFO_URL):
            if params['user'][0] == 'U0001':
                body = user_U0001
            elif params['user'][0] == 'U0002':
                body = user_U0002
            else:
                body = user_U0003
        elif uri.startswith(SLACK_CONVERSATION_MEMBERS):
            if 'cursor' not in params:
                body = conversation_members_1
            else:
                body = conversation_members_2
        else:
            raise

        http_requests.append(last_request)

        return status, headers, body

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

    httpretty.register_uri(httpretty.GET,
                           SLACK_CONVERSATION_MEMBERS,
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
        self.assertIsNone(slack.client)
        self.assertTrue(slack.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in URL
        slack = Slack('C011DUKE8', 'aaaa', ssl_verify=False)
        self.assertEqual(slack.origin, 'https://slack.com/C011DUKE8')
        self.assertEqual(slack.tag, 'https://slack.com/C011DUKE8')
        self.assertFalse(slack.ssl_verify)

        slack = Slack('C011DUKE8', 'aaaa', tag='')
        self.assertEqual(slack.origin, 'https://slack.com/C011DUKE8')
        self.assertEqual(slack.tag, 'https://slack.com/C011DUKE8')

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Slack.has_archiving(), True)

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
        messages = [msg for msg in slack.fetch(from_date=None)]

        expected = [
            ("<@U0003|dizquierdo> commented on <@U0002|acs> file>: Thanks.",
             'cc2338c23bf5293308d596629c598cd5ec37d14b',
             1486999900.000000, 'dizquierdo@example.com', 'test channel'),
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

            # The second message was sent by a bot
            if x == 1:
                self.assertEqual(message['data']['bot_id'], expc[3])
            else:
                self.assertEqual(message['data']['user_data']['profile']['email'], expc[3])

            self.assertEqual(message['data']['channel_info']['name'], expc[4])
            self.assertEqual(message['data']['channel_info']['num_members'], 164)

        # Check requests
        expected = [
            {
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8'],
                'cursor': ['dXNlcl9pZDpVNEMwUTZGQTc=']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1483228800.000000'],
                'count': ['5']
            },
            {
                'user': ['U0003']
            },
            {
                'user': ['U0002']
            },
            {
                'user': ['U0001']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1427135733.000068'],
                'count': ['5']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), http_requests[i].headers._headers)
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_search_fields(self, mock_utcnow):
        """Test whether the search_fields is properly set"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()

        slack = Slack('C011DUKE8', 'aaaa', max_items=5)
        messages = [msg for msg in slack.fetch(from_date=None)]

        message = messages[0]
        self.assertEqual(slack.metadata_id(message['data']), message['search_fields']['item_id'])
        self.assertEqual(message['data']['channel_info']['name'], 'test channel')
        self.assertEqual(message['data']['channel_info']['name'], message['search_fields']['channel_name'])
        self.assertEqual(message['data']['channel_info']['id'], 'C011DUKE8')
        self.assertEqual(message['data']['channel_info']['id'], message['search_fields']['channel_id'])

        message = messages[1]
        self.assertEqual(slack.metadata_id(message['data']), message['search_fields']['item_id'])
        self.assertEqual(message['data']['channel_info']['name'], 'test channel')
        self.assertEqual(message['data']['channel_info']['name'], message['search_fields']['channel_name'])
        self.assertEqual(message['data']['channel_info']['id'], 'C011DUKE8')
        self.assertEqual(message['data']['channel_info']['id'], message['search_fields']['channel_id'])

        message = messages[2]
        self.assertEqual(slack.metadata_id(message['data']), message['search_fields']['item_id'])
        self.assertEqual(message['data']['channel_info']['name'], 'test channel')
        self.assertEqual(message['data']['channel_info']['name'], message['search_fields']['channel_name'])
        self.assertEqual(message['data']['channel_info']['id'], 'C011DUKE8')
        self.assertEqual(message['data']['channel_info']['id'], message['search_fields']['channel_id'])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch_archived_channel(self, mock_utcnow):
        """Test if it fetches a list of messages from an archived channel"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        http_requests = setup_http_server(archived_channel=True)

        slack = Slack('C011DUKE8', 'aaaa', max_items=5)

        with self.assertLogs(logger, level='WARNING') as cm:
            messages = [msg for msg in slack.fetch(from_date=None)]
            self.assertEqual(cm.output[0], 'WARNING:perceval.backends.core.slack:'
                                           'channel_info.num_members is None for archived channels C011DUKE8')

        expected = [
            ("<@U0003|dizquierdo> commented on <@U0002|acs> file>: Thanks.",
             'cc2338c23bf5293308d596629c598cd5ec37d14b',
             1486999900.000000, 'dizquierdo@example.com', 'test channel'),
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

            # The second message was sent by a bot
            if x == 1:
                self.assertEqual(message['data']['bot_id'], expc[3])
            else:
                self.assertEqual(message['data']['user_data']['profile']['email'], expc[3])

            self.assertEqual(message['data']['channel_info']['name'], expc[4])
            self.assertIsNone(message['data']['channel_info']['num_members'])

        # Check requests
        expected = [
            {
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1483228800.000000'],
                'count': ['5']
            },
            {
                'user': ['U0003']
            },
            {
                'user': ['U0002']
            },
            {
                'user': ['U0001']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['0'],
                'latest': ['1427135733.000068'],
                'count': ['5']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), http_requests[i].headers._headers)
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
            ("hey hey!",
             '141392fe7515c0710bc4b3d1da82f1d4bec311f4',
             1486949200.000069, None, 'test channel'),
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
            elif x == 1:
                self.assertNotIn('bot_id', message['data'])
                self.assertNotIn('user_data', message['data'])
            else:
                self.assertEqual(message['data']['user_data']['profile']['email'], expc[3])

            self.assertEqual(message['data']['channel_info']['name'], expc[4])
            self.assertEqual(message['data']['channel_info']['num_members'], 164)

        # Check requests
        expected = [
            {
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8'],
                'cursor': ['dXNlcl9pZDpVNEMwUTZGQTc=']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['1427135740.000059'],
                'latest': ['1483228800.000000'],
                'count': ['5']
            },
            {
                'user': ['U0003']
            },
            {
                'user': ['U0002']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), http_requests[i].headers._headers)
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
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8'],
                'cursor': ['dXNlcl9pZDpVNEMwUTZGQTc=']
            },
            {
                'channel': ['C011DUKE8'],
                'oldest': ['1451606399.999990'],
                'latest': ['1483228800.000000'],
                'count': ['5']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), http_requests[i].headers._headers)
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

        self.assertEqual(len(results), 7)
        self.assertEqual(results[0]['ts'], '1486999900.000000')
        self.assertEqual(results[1]['ts'], '1486969200.000136')
        self.assertEqual(results[2]['ts'], '1427799888.000000')
        self.assertEqual(results[3]['ts'], '1427135890.000071')
        self.assertEqual(results[4]['ts'], '1427135835.000070')
        self.assertEqual(results[5]['ts'], '1427135740.000069')
        self.assertEqual(results[6]['ts'], '1427135733.000068')
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


class TestSlackBackendArchive(TestCaseBackendArchive):
    """Slack backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Slack('C011DUKE8', 'aaaa', max_items=5, archive=self.archive)
        self.backend_read_archive = Slack('C011DUKE8', 'bbbb', max_items=5, archive=self.archive)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch_from_archive(self, mock_utcnow):
        """Test if it fetches a list of messages from archive"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch_from_date_from_archive(self, mock_utcnow):
        """Test if it fetches a list of messages since a given date from archive"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()

        from_date = datetime.datetime(2015, 3, 23, 18, 35, 40, 69,
                                      tzinfo=dateutil.tz.tzutc())
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.slack.datetime_utcnow')
    def test_fetch_empty_from_archive(self, mock_utcnow):
        """Test if nothing is returned when there are no messages from archive"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()

        from_date = datetime.datetime(2016, 1, 1,
                                      tzinfo=dateutil.tz.tzutc())
        self._test_fetch_from_archive(from_date=from_date)


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
        self.assertTrue(client.ssl_verify)

        client = SlackClient('aaaa', max_items=5, ssl_verify=False)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_items, 5)
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_conversation_members(self):
        """Test conversation members API call"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        num_members = client.conversation_members('C011DUKE8')
        self.assertEqual(num_members, 164)

        expected = [
            {
                'channel': ['C011DUKE8']
            },
            {
                'channel': ['C011DUKE8'],
                'cursor': ['dXNlcl9pZDpVNEMwUTZGQTc=']
            }]

        self.assertEqual(len(http_requests), 2)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, SlackClient.RCONVERSATION_MEMBERS)

        for i in range(len(expected)):
            self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), http_requests[i].headers._headers)
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_channel_info(self):
        """Test channel info API call"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        _ = client.channel_info('C011DUKE8')

        expected = {
            'channel': ['C011DUKE8']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, SlackClient.RCONVERSATION_INFO)
        self.assertDictEqual(req.querystring, expected)
        self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), req.headers._headers)

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
            'oldest': ['0.999990'],
            'latest': ['1427135733.000068'],
            'count': ['5']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, SlackClient.RCHANNEL_HISTORY)
        self.assertDictEqual(req.querystring, expected)
        self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), req.headers._headers)

    @httpretty.activate
    def test_history_format_latest(self):
        """Test channel history API call with latest timestamp longer than 6 decimals"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        # Call API
        _ = client.history('C011DUKE8',
                           oldest=1, latest=1427135733.00006771)

        expected = {
            'channel': ['C011DUKE8'],
            'oldest': ['0.999990'],
            'latest': ['1427135733.000068'],
            'count': ['5']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, SlackClient.RCHANNEL_HISTORY)
        self.assertDictEqual(req.querystring, expected)
        self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), req.headers._headers)

    @httpretty.activate
    def test_user(self):
        """Test user info API call"""

        http_requests = setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        # Call API
        _ = client.user('U0001')

        expected = {
            'user': ['U0001']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, SlackClient.RUSER_INFO)
        self.assertDictEqual(req.querystring, expected)
        self.assertIn((SlackClient.AUTHORIZATION_HEADER, 'Bearer aaaa'), req.headers._headers)

    @httpretty.activate
    def test_slack_error(self):
        """Test if an exception is raised when an error is returned by the server"""

        setup_http_server()

        client = SlackClient('aaaa', max_items=5)

        with self.assertRaises(SlackClientError):
            _ = client.history('CH0')

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = {
            SlackClient.AUTHORIZATION_HEADER: 'Bear aaaa'
        }
        payload = {
            'channel': 'C011DUKE8'
        }

        s_url, s_headers, s_payload = SlackClient.sanitize_for_archive(url, copy.deepcopy(headers), payload)
        headers.pop(SlackClient.AUTHORIZATION_HEADER)

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)

    @httpretty.activate
    def test_private_user(self):

        user_U0004 = read_file('data/slack/slack_user_U0004_private.json', 'rb')
        httpretty.register_uri(httpretty.GET,
                               SLACK_USER_INFO_URL + "?user=U0004",
                               body=user_U0004)

        client = SlackClient('aaaa', max_items=5)

        # Call API
        user = client.user('U0004')

        self.assertEqual(user, '{"ok":false,"user":null}')


class TestSlackCommand(unittest.TestCase):
    """SlackCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Slack"""

        self.assertIs(SlackCommand.BACKEND, Slack)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = SlackCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Slack)

        args = ['--tag', 'test', '--no-archive',
                '--api-token', 'abcdefgh',
                '--from-date', '1970-01-01',
                '--max-items', '10',
                'C001']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.channel, 'C001')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')
        self.assertEqual(parsed_args.max_items, 10)

        args = ['--tag', 'test', '--no-ssl-verify',
                '--api-token', 'abcdefgh',
                '--from-date', '1970-01-01',
                '--max-items', '10',
                'C001']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.channel, 'C001')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, 'abcdefgh')
        self.assertEqual(parsed_args.max_items, 10)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

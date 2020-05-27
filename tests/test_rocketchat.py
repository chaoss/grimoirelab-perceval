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
#     Aditya Prajapati <aditya10699@gmail.com>
#     Animesh Kumar <animuz111@gmail.com>
#

import copy
import datetime
import httpretty
import os
import pkg_resources
import unittest
import unittest.mock
import dateutil.tz
import time
import json

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import RateLimitError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.rocketchat import (RocketChat,
                                               RocketChatClient,
                                               RocketChatCommand,
                                               MIN_RATE_LIMIT,
                                               MAX_ITEMS)

from base import TestCaseBackendArchive

ROCKETCHAT_SERVER_URL = 'https://open.rocket.chat'
ROCKETCHAT_CHANNEL_NAME = 'testapichannel'
ROCKETCHAT_API_EXTENSION = "/api/v1/"
ROCKETCHAT_API_BASE_URL = ROCKETCHAT_SERVER_URL + ROCKETCHAT_API_EXTENSION
ROCKETCHAT_MESSAGE_URL = ROCKETCHAT_API_BASE_URL + RocketChatClient.RCHANNEL_MESSAGES
ROCKETCHAT_CHANNEL_URL = ROCKETCHAT_API_BASE_URL + RocketChatClient.RCHANNEL_INFO


def setup_http_server(no_message=False, rate_limit_headers=None, from_date=False):
    """Setup a mock HTTP server"""

    message_page_1 = read_file('data/rocketchat/message_page_1.json')
    message_page_2 = read_file('data/rocketchat/message_page_2.json')
    channel_info = read_file('data/rocketchat/channel_info.json')
    message_empty_2020_5_10 = read_file('data/rocketchat/message_empty_2020_05_10.json')
    message_page_2020_05_03 = read_file('data/rocketchat/message_page_2020_05_03.json')

    if not rate_limit_headers:
        rate_limit_headers = {}

    httpretty.register_uri(httpretty.GET,
                           ROCKETCHAT_CHANNEL_URL + '?roomName=testapichannel',
                           body=channel_info,
                           status=200,
                           forcing_headers=rate_limit_headers)

    roomName = '?roomName=testapichannel'
    sort = '&sort={"_updatedAt": 1}'
    count = '&count=2'
    params = roomName + sort + count

    if no_message:
        query = '&q={"_updatedAt": {"$gte": {"$date": "2020-05-10T00:00:00+00:00"}}}'
        httpretty.register_uri(httpretty.GET,
                               ROCKETCHAT_MESSAGE_URL + params + query + '&offset=0',
                               body=message_empty_2020_5_10,
                               status=200,
                               forcing_headers=rate_limit_headers)
    elif from_date:
        query = '&q={"_updatedAt": {"$gte": {"$date": "2020-05-03T00:00:00+00:00"}}}'
        httpretty.register_uri(httpretty.GET,
                               ROCKETCHAT_MESSAGE_URL + params + query + '&offset=0',
                               body=message_page_2020_05_03,
                               status=200,
                               forcing_headers=rate_limit_headers)
    else:
        query = '&q={"_updatedAt": {"$gte": {"$date": "2020-05-02T00:00:00+00:00"}}}'
        httpretty.register_uri(httpretty.GET,
                               ROCKETCHAT_MESSAGE_URL + params + query + '&offset=2',
                               body=message_page_2,
                               status=200,
                               forcing_headers=rate_limit_headers)

        httpretty.register_uri(httpretty.GET,
                               ROCKETCHAT_MESSAGE_URL + params + query + '&offset=0',
                               body=message_page_1,
                               status=200,
                               forcing_headers=rate_limit_headers)


class MockedRocketChatClient(RocketChatClient):
    """Mocked Rocket.Chat client for testing"""

    def __init__(self, url, user_id, api_token, max_items=MAX_ITEMS, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 from_archive=False, ssl_verify=True):
        super().__init__(url, user_id, api_token, max_items=max_items,
                         min_rate_to_sleep=min_rate_to_sleep,
                         sleep_for_rate=sleep_for_rate,
                         archive=archive,
                         from_archive=from_archive,
                         ssl_verify=ssl_verify
                         )
        self.rate_limit_reset_ts = -1


def read_file(filename):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), 'rb') as f:
        content = f.read()
    return content


class TestRocketChatBackend(unittest.TestCase):
    """Tests for Rocket.Chat backend class"""

    def test_initialization(self):
        """Test whether attributes are initialized"""

        backend = RocketChat(url='https://chat.example.com', user_id='123user', api_token='aaa',
                             channel='testapichannel', tag='test')

        self.assertEqual(backend.url, 'https://chat.example.com')
        self.assertEqual(backend.user_id, '123user')
        self.assertEqual(backend.api_token, "aaa")
        self.assertEqual(backend.channel, "testapichannel")
        self.assertEqual(backend.min_rate_to_sleep, MIN_RATE_LIMIT)
        self.assertIsNone(backend.client)
        self.assertFalse(backend.sleep_for_rate)
        self.assertTrue(backend.ssl_verify)
        self.assertEqual(backend.origin, 'https://chat.example.com/testapichannel')
        self.assertEqual(backend.tag, 'test')
        self.assertEqual(backend.max_items, MAX_ITEMS)

        # When tag is empty or None it will be set to
        # the value in URL
        backend = RocketChat(url="https://chat.example.com", user_id="123user", api_token='aaa',
                             channel='testapichannel', tag=None)
        self.assertEqual(backend.origin, 'https://chat.example.com/testapichannel')
        self.assertEqual(backend.tag, 'https://chat.example.com/testapichannel')

        backend = RocketChat(url="https://chat.example.com", user_id="123user", api_token='aaa',
                             channel='testapichannel', tag='')
        self.assertEqual(backend.origin, 'https://chat.example.com/testapichannel')
        self.assertEqual(backend.tag, 'https://chat.example.com/testapichannel')

        backend = RocketChat(url='https://chat.example.com', user_id='123user', api_token='aaa',
                             channel='testapichannel', tag='', sleep_for_rate=True,
                             ssl_verify=False, max_items=20, min_rate_to_sleep=1)
        self.assertEqual(backend.origin, 'https://chat.example.com/testapichannel')
        self.assertEqual(backend.tag, 'https://chat.example.com/testapichannel')
        self.assertFalse(backend.ssl_verify)
        self.assertTrue(backend.sleep_for_rate)
        self.assertEqual(backend.max_items, 20)
        self.assertEqual(backend.min_rate_to_sleep, 1)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(RocketChat.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(RocketChat.has_resuming(), True)

    @httpretty.activate
    def test_fetch_messages(self):
        """Test whether a list of messages is returned"""

        setup_http_server()

        backend = RocketChat(url='https://open.rocket.chat', user_id='123user',
                             api_token='aaa', channel='testapichannel')
        messages = [m for m in backend.fetch()]

        self.assertEqual(len(messages), 4)

        message = messages[0]
        self.assertEqual(message['data']['_id'], '4AwA2eJQ7xBgPZ4mv')
        self.assertEqual(message['origin'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['uuid'], '888b6c9a728c267435cee1d5fe8f5dbe446614a2')
        self.assertEqual(message['updated_on'], 1588404686.164)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['data']['msg'], 'Test message 1')
        self.assertEqual(message['data']['u']['username'], 'animesh_username1')
        self.assertEqual(message['data']['u']['name'], 'Animesh Kumar')
        self.assertListEqual(message['data']['replies'], ["567user"])
        self.assertEqual(message['data']['channel_info']['_id'], 'wyJHNAtuPGnQCT5xP')
        self.assertEqual(message['data']['channel_info']['lastMessage']['msg'], 'Test message 2')
        self.assertEqual(message['data']['channel_info']['usersCount'], 2)

        message = messages[1]
        self.assertEqual(message['data']['_id'], 'zofFonHMq5M3tdGyu')
        self.assertEqual(message['origin'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['uuid'], '6fa3f6a18491b9bcb3309f12e3a2b1cd654980c3')
        self.assertEqual(message['updated_on'], 1588404716.711)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['data']['msg'], 'Test reply 1')
        self.assertEqual(message['data']['u']['username'], 'animesh_username2')
        self.assertEqual(message['data']['u']['name'], 'Animesh Kumar Singh')
        self.assertEqual(message['data']['channel_info']['_id'], 'wyJHNAtuPGnQCT5xP')
        self.assertEqual(message['data']['channel_info']['lastMessage']['msg'], 'Test message 2')
        self.assertEqual(message['data']['channel_info']['usersCount'], 2)

        message = messages[2]
        self.assertEqual(message['data']['_id'], 'WnWSwiD877xRpqcMb')
        self.assertEqual(message['origin'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['uuid'], '3b3afa62a63766ebeb70e3c8951c2c4b42f34767')
        self.assertEqual(message['updated_on'], 1588404716.714)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['data']['msg'], 'Test reply 1 edited')
        self.assertEqual(message['data']['u']['username'], 'animesh_username2')
        self.assertEqual(message['data']['u']['name'], 'Animesh Kumar Singh')
        self.assertEqual(message['data']['editedBy']['username'], 'animesh_username1')
        self.assertEqual(message['data']['channel_info']['_id'], 'wyJHNAtuPGnQCT5xP')
        self.assertEqual(message['data']['channel_info']['usersCount'], 2)

        message = messages[3]
        self.assertEqual(message['data']['_id'], 'p5dQSb48W25EimhJK')
        self.assertEqual(message['origin'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['uuid'], 'a3b2a4c195e8b6a155cf5eddb2b8f79a13f836dd')
        self.assertEqual(message['updated_on'], 1588491123.587)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['data']['msg'], 'Test message 2')
        self.assertEqual(message['data']['u']['username'], 'animesh_username1')
        self.assertEqual(message['data']['u']['name'], 'Animesh Kumar')
        self.assertEqual(message['data']['channel_info']['_id'], 'wyJHNAtuPGnQCT5xP')
        self.assertEqual(message['data']['channel_info']['usersCount'], 2)

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test when fetching messages from a given date"""

        setup_http_server(from_date=True)
        from_date = datetime.datetime(2020, 5, 3, 0, 0, tzinfo=dateutil.tz.tzutc())

        backend = RocketChat(url='https://open.rocket.chat', user_id='123user',
                             api_token='aaa', channel='testapichannel')

        messages = [m for m in backend.fetch(from_date=from_date)]
        self.assertEqual(len(messages), 1)

        message = messages[0]
        self.assertEqual(message['data']['_id'], 'p5dQSb48W25EimhJK')
        self.assertEqual(message['origin'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['uuid'], 'a3b2a4c195e8b6a155cf5eddb2b8f79a13f836dd')
        self.assertEqual(message['updated_on'], 1588491123.587)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://open.rocket.chat/testapichannel')
        self.assertEqual(message['data']['msg'], 'Test message 2')
        self.assertEqual(message['data']['u']['username'], 'animesh_username1')
        self.assertEqual(message['data']['u']['name'], 'Animesh Kumar')
        self.assertEqual(message['data']['channel_info']['_id'], 'wyJHNAtuPGnQCT5xP')
        self.assertEqual(message['data']['channel_info']['usersCount'], 2)

    @httpretty.activate
    def test_search_fields_messages(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        backend = RocketChat(url='https://open.rocket.chat', user_id='123user',
                             api_token='aaa', channel='testapichannel')
        messages = [m for m in backend.fetch()]

        message = messages[0]
        self.assertEqual(message['search_fields']['item_id'], backend.metadata_id(message['data']))
        self.assertEqual(message['search_fields']['channel_id'], 'wyJHNAtuPGnQCT5xP')
        self.assertEqual(message['search_fields']['channel_name'], 'testapichannel')

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether an empty list is returned when there are no messages"""

        setup_http_server(no_message=True)

        backend = RocketChat(url='https://open.rocket.chat', user_id='123user',
                             api_token='aaa', channel='testapichannel')
        messages = [m for m in backend.fetch()]
        self.assertListEqual(messages, [])


class TestRocketChatBackendArchive(TestCaseBackendArchive):
    """Rocket.Chat backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = RocketChat(url='https://open.rocket.chat', user_id='123user',
                                                api_token='aaa', channel='testapichannel',
                                                max_items=5, archive=self.archive)
        self.backend_read_archive = RocketChat(url='https://open.rocket.chat', user_id='123user',
                                               api_token='aaa', channel='testapichannel',
                                               max_items=5, archive=self.archive)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.rocketchat.datetime_utcnow')
    def test_fetch_from_archive(self, mock_utcnow):
        """Test if a list of messages is returned from archive"""

        mock_utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.rocketchat.datetime_utcnow')
    def test_fetch_from_date_from_archive(self, mock_utcnow):
        """Test whether a list of messages is returned from archive after a given date"""

        mock_utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()

        from_date = datetime.datetime(2020, 5, 3, 18, 35, 40, 69,
                                      tzinfo=dateutil.tz.tzutc())
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.rocketchat.datetime_utcnow')
    def test_fetch_empty_from_archive(self, mock_utcnow):
        """Test whether no messages are returned when the archive is empty"""

        mock_utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()

        from_date = datetime.datetime(2020, 5, 3,
                                      tzinfo=dateutil.tz.tzutc())
        self._test_fetch_from_archive(from_date=from_date)


class TestRocketChatClient(unittest.TestCase):
    """Tests for RocketChatClient class"""

    def test_init(self):
        """Check attributes initialization"""

        client = RocketChatClient(url='https://open.rocket.chat', user_id='123user',
                                  api_token='aaa', ssl_verify=True)
        self.assertIsInstance(client, RocketChatClient)
        self.assertEqual(client.base_url, 'https://open.rocket.chat/api/v1')
        self.assertEqual(client.user_id, '123user')
        self.assertEqual(client.api_token, 'aaa')
        self.assertTrue(client.ssl_verify)
        self.assertFalse(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, MIN_RATE_LIMIT)

        client = RocketChatClient(url='https://open.rocket.chat', user_id='123user', api_token='aaa',
                                  sleep_for_rate=True, min_rate_to_sleep=1, ssl_verify=False)
        self.assertIsInstance(client, RocketChatClient)
        self.assertEqual(client.base_url, 'https://open.rocket.chat/api/v1')
        self.assertEqual(client.user_id, '123user')
        self.assertEqual(client.api_token, 'aaa')
        self.assertFalse(client.ssl_verify)
        self.assertTrue(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, 1)

    @httpretty.activate
    def test_messages(self):
        """Test whether messages are fetched"""

        setup_http_server()

        client = RocketChatClient(url='https://open.rocket.chat', user_id='123user',
                                  api_token='aaa', ssl_verify=True)

        messages = client.messages('testapichannel', from_date=DEFAULT_DATETIME, offset=0)
        messages = json.loads(messages)

        self.assertEqual(len(messages['messages']), 2)

        # Check requests
        expected = {
            'count': ['100'],
            'offset': ['0'],
            'query': ['{"_updatedAt": {"$gte": {"$date": "1970-01-01T00:00:00 00:00"}}}'],
            'roomName': ['testapichannel'],
            'sort': ['{"_updatedAt": 1}']
        }

        self.assertEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers[RocketChatClient.HAUTH_TOKEN], 'aaa')

    @httpretty.activate
    def test_channel_info(self):
        """Test whether channel information is fetched"""

        setup_http_server()

        client = RocketChatClient(url='https://open.rocket.chat', user_id='123user',
                                  api_token='aaa', ssl_verify=True)
        channel = client.channel_info('testapichannel')
        channel = json.loads(channel)

        self.assertEqual(channel['channel']['_id'], 'wyJHNAtuPGnQCT5xP')
        self.assertEqual(channel['channel']['name'], 'testapichannel')
        self.assertEqual(channel['channel']['usersCount'], 2)
        self.assertEqual(channel['channel']['msgs'], 3)
        self.assertEqual(channel['channel']['lastMessage']['msg'], 'Test message 2')

        # Check requests
        expected = {
            'roomName': ['testapichannel'],
        }

        self.assertEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers[RocketChatClient.HAUTH_TOKEN], 'aaa')

    def test_calculate_time_to_reset(self):
        """Test whether the time to reset is zero if the sleep time is negative"""

        client = MockedRocketChatClient(url='https://open.rocket.chat', user_id='123user',
                                        api_token='aaa', max_items=10, archive=None, from_archive=False,
                                        min_rate_to_sleep=2, sleep_for_rate=True, ssl_verify=False)
        time_to_reset = client.calculate_time_to_reset()
        self.assertEqual(time_to_reset, 0)

    @httpretty.activate
    def test_sleep_for_rate(self):
        """Test if the clients sleeps when the rate limit is reached"""

        wait = 10000
        reset = int(time.time() * 1000 + wait)
        rate_limit_headers = {'X-RateLimit-Remaining': '0',
                              'X-RateLimit-Reset': reset}

        setup_http_server(rate_limit_headers=rate_limit_headers)

        client = RocketChatClient(url='https://open.rocket.chat', user_id='123user',
                                  api_token='aaa', min_rate_to_sleep=5,
                                  sleep_for_rate=True)

        _ = client.channel_info('testapichannel')
        after = float(time.time() * 1000)

        self.assertTrue(reset >= after)

    @httpretty.activate
    def test_rate_limit_error(self):
        """Test if a rate limit error is raised when rate is exhausted"""

        wait = 2000
        reset = int(time.time() * 1000 + wait)
        rate_limit_headers = {'X-RateLimit-Remaining': '0',
                              'X-RateLimit-Reset': reset}

        setup_http_server(rate_limit_headers=rate_limit_headers)

        client = RocketChatClient(url='https://open.rocket.chat', user_id='123user',
                                  api_token='aaa', sleep_for_rate=False)

        _ = client.channel_info('testapichannel')
        with self.assertRaises(RateLimitError):
            _ = client.messages('testapichannel', from_date=DEFAULT_DATETIME, offset=0)

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "https://open.rocket.chat/testapichannel"
        headers = {
            RocketChatClient.HAUTH_TOKEN: 'aaaa',
            RocketChatClient.HUSER_ID: '123user'
        }

        payload = {
            'count': 100,
            'offset': 0,
            'query': '{"_updatedAt": {"$gte": {"$date": "1970-01-01T00:00:00 00:00"}}}',
            'roomName': 'testapichannel',
            'sort': '{"_updatedAt": 1}'
        }

        s_url, s_headers, s_payload = RocketChatClient.sanitize_for_archive(url, copy.deepcopy(headers), payload)
        headers.pop(RocketChatClient.HAUTH_TOKEN)
        headers.pop(RocketChatClient.HUSER_ID)

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)


class TestRocketChatCommand(unittest.TestCase):
    """Tests for RocketChatCommand class"""

    def test_backend_class(self):
        """Test if the backend class is RocketChat"""

        self.assertIs(RocketChatCommand.BACKEND, RocketChat)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = RocketChatCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, RocketChat)

        args = ['-t', 'aaa',
                '-u', '123user',
                '--tag', 'test',
                '--sleep-for-rate',
                '--from-date', '1970-01-01',
                'https://open.rocket.chat',
                'testapichannel']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.api_token, 'aaa')
        self.assertEqual(parsed_args.user_id, '123user')
        self.assertEqual(parsed_args.url, 'https://open.rocket.chat')
        self.assertEqual(parsed_args.channel, 'testapichannel')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertTrue(parsed_args.sleep_for_rate)

        from_date = datetime.datetime(2020, 3, 1, 0, 0, tzinfo=dateutil.tz.tzutc())

        args = ['-t', 'aaa',
                '-u', '123user',
                '--tag', 'test',
                '--max-items', '10',
                '--no-ssl-verify',
                '--min-rate-to-sleep', '1',
                '--from-date', '2020-03-01',
                'https://open.rocket.chat',
                'testapichannel']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.api_token, 'aaa')
        self.assertEqual(parsed_args.user_id, '123user')
        self.assertEqual(parsed_args.url, 'https://open.rocket.chat')
        self.assertEqual(parsed_args.channel, 'testapichannel')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, from_date)
        self.assertEqual(parsed_args.min_rate_to_sleep, 1)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertFalse(parsed_args.sleep_for_rate)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

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

import httpretty
import os
import unittest
import urllib

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.telegram import (Telegram,
                                             TelegramCommand,
                                             TelegramBotClient)
from base import TestCaseBackendArchive

TELEGRAM_BOT = 'mybot'
TELEGRAM_TOKEN = '12345678'
TELEGRAM_UPDATES_URL = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/getUpdates'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    body_msgs = read_file('data/telegram/telegram_messages.json')
    body_msgs_next = read_file('data/telegram/telegram_messages_next.json')
    body_msgs_empty = read_file('data/telegram/telegram_messages_empty.json')

    def request_callback(method, uri, headers):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)

        if 'offset' in params and params['offset'] == ['319280321']:
            body = body_msgs_next
        elif 'offset' in params and params['offset'] == ['319280324']:
            body = body_msgs_empty
        else:
            body = body_msgs

        http_requests.append(httpretty.last_request())

        return 200, headers, body

    httpretty.register_uri(httpretty.GET,
                           TELEGRAM_UPDATES_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestTelegramBackend(unittest.TestCase):
    """Telegram backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        origin = 'https://telegram.org/' + TELEGRAM_BOT

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN,
                       tag='test')

        self.assertEqual(tlg.bot, 'mybot')
        self.assertEqual(tlg.origin, origin)
        self.assertEqual(tlg.tag, 'test')
        self.assertIsNone(tlg.client)
        self.assertTrue(tlg.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN, ssl_verify=False)
        self.assertEqual(tlg.bot, TELEGRAM_BOT)
        self.assertEqual(tlg.origin, origin)
        self.assertEqual(tlg.tag, origin)
        self.assertFalse(tlg.ssl_verify)

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN, tag='')
        self.assertEqual(tlg.bot, TELEGRAM_BOT)
        self.assertEqual(tlg.origin, origin)
        self.assertEqual(tlg.tag, origin)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Telegram.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Telegram.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of messages is returned"""

        http_requests = setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        messages = [msg for msg in tlg.fetch(offset=None)]

        expected = [
            (31, '5a5457aec04237ac3fab30031e84c745a3bdd157', 1467289325.0, 319280318),
            (32, '16a59e93e919174fcd4e70e5b3289201c1016c72', 1467289329.0, 319280319),
            (33, '9d03eeea7e3186ca8e5c150b4cbf18c8283cca9d', 1467289371.0, 319280320),
            (34, '2e61e72b64c9084f3c5a36671c3119641c3ae42f', 1467370372.0, 319280321),
            (35, '563e8e9d3f477cbfd04eef0af3a72af51ab6d72b', 1467370373.0, 319280322),
            (35, '563e8e9d3f477cbfd04eef0af3a72af51ab6d72b', 1467370374.0, 319280323)
        ]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['message']['message_id'], expected[x][0])
            self.assertEqual(message['origin'], 'https://telegram.org/' + TELEGRAM_BOT)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://telegram.org/' + TELEGRAM_BOT)

        # check that the only the message is marked as edited
        message = messages[0]
        self.assertNotIn('edited', message['data']['message'])

        message = messages[1]
        self.assertNotIn('edited', message['data']['message'])

        message = messages[2]
        self.assertNotIn('edited', message['data']['message'])

        message = messages[3]
        self.assertNotIn('edited', message['data']['message'])

        message = messages[4]
        self.assertNotIn('edited', message['data']['message'])

        message = messages[5]
        self.assertTrue(message['data']['message']['edited'])

        # Check requests
        expected = [
            {'offset': ['1']},
            {'offset': ['319280321']},
            {'offset': ['319280324']}
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        messages = [msg for msg in tlg.fetch(offset=None)]

        message = messages[0]
        self.assertEqual(tlg.metadata_id(message['data']), message['search_fields']['item_id'])
        self.assertEqual(message['data']['message']['chat']['title'], 'Testing Telegram Bots')
        self.assertEqual(message['data']['message']['chat']['title'], message['search_fields']['chat_name'])
        self.assertEqual(message['data']['message']['chat']['id'], -1)
        self.assertEqual(message['data']['message']['chat']['id'], message['search_fields']['chat_id'])

        message = messages[1]
        self.assertEqual(tlg.metadata_id(message['data']), message['search_fields']['item_id'])
        self.assertEqual(message['data']['message']['chat']['title'], 'A new group')
        self.assertEqual(message['data']['message']['chat']['title'], message['search_fields']['chat_name'])
        self.assertEqual(message['data']['message']['chat']['id'], -2)
        self.assertEqual(message['data']['message']['chat']['id'], message['search_fields']['chat_id'])

        message = messages[2]
        self.assertEqual(tlg.metadata_id(message['data']), message['search_fields']['item_id'])
        self.assertEqual(message['data']['message']['chat']['title'], 'Testing Telegram Bots')
        self.assertEqual(message['data']['message']['chat']['title'], message['search_fields']['chat_name'])
        self.assertEqual(message['data']['message']['chat']['id'], -1)
        self.assertEqual(message['data']['message']['chat']['id'], message['search_fields']['chat_id'])

        message = messages[3]
        self.assertEqual(tlg.metadata_id(message['data']), message['search_fields']['item_id'])
        self.assertNotIn('title', message['data']['message']['chat'])
        self.assertEqual(message['data']['message']['chat']['id'], 8)
        self.assertEqual(message['data']['message']['chat']['id'], message['search_fields']['chat_id'])

    @httpretty.activate
    def test_fetch_from_offset(self):
        """Test whether it fetches and parses messages from the given offset"""

        http_requests = setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        messages = [msg for msg in tlg.fetch(offset=319280321)]

        expected = [
            (34, '2e61e72b64c9084f3c5a36671c3119641c3ae42f', 1467370372.0, 319280321),
            (35, '563e8e9d3f477cbfd04eef0af3a72af51ab6d72b', 1467370373.0, 319280322),
            (35, '563e8e9d3f477cbfd04eef0af3a72af51ab6d72b', 1467370374.0, 319280323)
        ]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['message']['message_id'], expected[x][0])
            self.assertEqual(message['origin'], 'https://telegram.org/' + TELEGRAM_BOT)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://telegram.org/' + TELEGRAM_BOT)

        # Check requests
        expected = [
            {'offset': ['319280321']},
            {'offset': ['319280324']}
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_by_chats(self):
        """Test if it returns only those messages that belong to the given chats"""

        _ = setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)

        chats = [8, -1]
        messages = [msg for msg in tlg.fetch(chats=chats)]

        self.assertEqual(len(messages), 3)

        expected = [(31, '5a5457aec04237ac3fab30031e84c745a3bdd157', 1467289325.0, 319280318),
                    (33, '9d03eeea7e3186ca8e5c150b4cbf18c8283cca9d', 1467289371.0, 319280320),
                    (34, '2e61e72b64c9084f3c5a36671c3119641c3ae42f', 1467370372.0, 319280321)]

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['message']['message_id'], expected[x][0])
            self.assertEqual(message['origin'], 'https://telegram.org/' + TELEGRAM_BOT)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://telegram.org/' + TELEGRAM_BOT)

        # Empty list of chats will return no messages
        chats = []
        messages = [msg for msg in tlg.fetch(chats=chats)]

        self.assertEqual(len(messages), 0)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when there are no messages to fetch"""

        http_requests = setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        messages = [msg for msg in tlg.fetch(offset=319280324)]

        self.assertEqual(len(messages), 0)

        # Check requests
        self.assertEqual(len(http_requests), 1)

        self.assertDictEqual(http_requests[0].querystring,
                             {'offset': ['319280324']})

    def test_parse_messages(self):
        """Test whether the method parses a raw file"""

        body_msgs = read_file('data/telegram/telegram_messages.json')
        body_msgs_empty = read_file('data/telegram/telegram_messages_empty.json')

        messages = Telegram.parse_messages(body_msgs)
        result = [msg for msg in messages]

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['message']['message_id'], 31)
        self.assertEqual(result[1]['message']['message_id'], 32)
        self.assertEqual(result[2]['message']['message_id'], 33)

        messages = Telegram.parse_messages(body_msgs_empty)
        result = [msg for msg in messages]

        self.assertEqual(len(result), 0)


class TestTelegramBackendArchive(TestCaseBackendArchive):
    """Telegram backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN, archive=self.archive)
        self.backend_read_archive = Telegram(TELEGRAM_BOT, "another-token", archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of messages is returned from archive"""

        setup_http_server()
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_from_offset_from_archive(self):
        """Test whether it fetches and parses messages from the given offset from archive"""

        setup_http_server()
        self._test_fetch_from_archive(offset=319280321)

    @httpretty.activate
    def test_fetch_by_chats_from_archive(self):
        """Test if the fetch from archive returns only those messages that belong to the given chats"""

        setup_http_server()

        chats = [8, -1]
        self._test_fetch_from_archive(chats=chats)

    @httpretty.activate
    def test_fetch_empty_by_chats_from_archive(self):
        """Test whether no chat messages are returned from an empty archive"""

        setup_http_server()

        chats = []
        self._test_fetch_from_archive(chats=chats)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether no messages are returned from an empty archive"""

        setup_http_server()
        self._test_fetch_from_archive(offset=319280322)


class TestTelegramCommand(unittest.TestCase):
    """Tests for TelegramCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Telegram"""

        self.assertIs(TelegramCommand.BACKEND, Telegram)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = TelegramCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Telegram)

        args = ['mybot',
                '--api-token', '12345678',
                '--offset', '10',
                '--chats', '-10000',
                '--tag', 'test',
                '--no-archive']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.bot, 'mybot')
        self.assertEqual(parsed_args.bot_token, '12345678')
        self.assertEqual(parsed_args.offset, 10)
        self.assertEqual(parsed_args.chats, [-10000])
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['mybot',
                '--api-token', '12345678',
                '--offset', '10',
                '--chats', '-10000',
                '--tag', 'test',
                '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.bot, 'mybot')
        self.assertEqual(parsed_args.bot_token, '12345678')
        self.assertEqual(parsed_args.offset, 10)
        self.assertEqual(parsed_args.chats, [-10000])
        self.assertEqual(parsed_args.tag, 'test')
        self.assertFalse(parsed_args.ssl_verify)


class TestTelegramBotClient(unittest.TestCase):
    """TelegramBotClient unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization parameters"""

        client = TelegramBotClient(TELEGRAM_TOKEN)
        self.assertEqual(client.bot_token, TELEGRAM_TOKEN)
        self.assertTrue(client.ssl_verify)

        client = TelegramBotClient(TELEGRAM_TOKEN, ssl_verify=False)
        self.assertEqual(client.bot_token, TELEGRAM_TOKEN)
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_updates(self):
        """Test updates API call"""

        setup_http_server()

        client = TelegramBotClient(TELEGRAM_TOKEN)

        # Check empty params
        client.updates()

        expected = {}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/bot12345678/getUpdates')
        self.assertDictEqual(req.querystring, expected)

        # Check request with offset
        client.updates(offset=319280321)

        expected = {
            'offset': ['319280321']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/bot12345678/getUpdates')
        self.assertDictEqual(req.querystring, expected)

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "https://api.telegram.org/bot12345678/getUpdates"
        headers = "headers-information"
        payload = "payload-information"

        s_url, s_headers, s_payload = TelegramBotClient.sanitize_for_archive(url, headers, payload)

        self.assertEqual(s_url, "https://api.telegram.org/botXXXXX/getUpdates")
        self.assertEqual(s_headers, headers)
        self.assertEqual(s_payload, payload)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

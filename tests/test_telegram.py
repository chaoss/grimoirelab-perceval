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

import argparse
import shutil
import sys
import tempfile
import unittest
import urllib

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.telegram import (Telegram,
                                        TelegramCommand,
                                        TelegramBotClient)


TELEGRAM_BOT = 'mybot'
TELEGRAM_TOKEN = '12345678'
TELEGRAM_UPDATES_URL = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/getUpdates'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    body_msgs = read_file('data/telegram_messages.json')
    body_msgs_next = read_file('data/telegram_messages_next.json')
    body_msgs_empty = read_file('data/telegram_messages_empty.json')

    def request_callback(method, uri, headers):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)

        if 'offset' in params and params['offset'] == ['319280321']:
            body = body_msgs_next
        elif 'offset' in params and params['offset'] == ['319280322']:
            body = body_msgs_empty
        else:
            body = body_msgs

        http_requests.append(httpretty.last_request())

        return (200, headers, body)

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
        self.assertIsInstance(tlg.client, TelegramBotClient)

        # When tag is empty or None it will be set to
        # the value in url
        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        self.assertEqual(tlg.bot, TELEGRAM_BOT)
        self.assertEqual(tlg.origin, origin)
        self.assertEqual(tlg.tag, origin)

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN, tag='')
        self.assertEqual(tlg.bot, TELEGRAM_BOT)
        self.assertEqual(tlg.origin, origin)
        self.assertEqual(tlg.tag, origin)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Telegram.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Telegram.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of messages is returned"""

        http_requests = setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        messages = [msg for msg in tlg.fetch()]

        expected = [(31, '5a5457aec04237ac3fab30031e84c745a3bdd157', 1467289325.0, 319280318),
                    (32, '16a59e93e919174fcd4e70e5b3289201c1016c72', 1467289329.0, 319280319),
                    (33, '9d03eeea7e3186ca8e5c150b4cbf18c8283cca9d', 1467289371.0, 319280320),
                    (34, '2e61e72b64c9084f3c5a36671c3119641c3ae42f', 1467370372.0, 319280321)]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message['data']['message']['message_id'], expected[x][0])
            self.assertEqual(message['origin'], 'https://telegram.org/' +  TELEGRAM_BOT)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://telegram.org/' +  TELEGRAM_BOT)

        # Check requests
        expected = [
                    {'offset' : ['1']},
                    {'offset' : ['319280321']},
                    {'offset' : ['319280322']}
                   ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_from_offset(self):
        """Test whether it fetches and parses messages from the given offset"""

        http_requests = setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        messages = [msg for msg in tlg.fetch(offset=319280321)]

        self.assertEqual(len(messages), 1)

        msg = messages[0]
        self.assertEqual(msg['data']['message']['message_id'], 34)
        self.assertEqual(msg['origin'], 'https://telegram.org/' +  TELEGRAM_BOT)
        self.assertEqual(msg['uuid'], '2e61e72b64c9084f3c5a36671c3119641c3ae42f')
        self.assertEqual(msg['updated_on'], 1467370372.0)
        self.assertEqual(msg['offset'], 319280321)
        self.assertEqual(msg['category'], 'message')
        self.assertEqual(msg['tag'], 'https://telegram.org/' +  TELEGRAM_BOT)

        # Check requests
        expected = [
                    {'offset' : ['319280321']},
                    {'offset' : ['319280322']}
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
            self.assertEqual(message['origin'], 'https://telegram.org/' +  TELEGRAM_BOT)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://telegram.org/' +  TELEGRAM_BOT)

        # Empty list of chats will return no messages
        chats = []
        messages = [msg for msg in tlg.fetch(chats=chats)]

        self.assertEqual(len(messages), 0)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when there are no messages to fetch"""

        http_requests = setup_http_server()

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)
        messages = [msg for msg in tlg.fetch(offset=319280322)]

        self.assertEqual(len(messages), 0)

        # Check requests
        self.assertEqual(len(http_requests), 1)

        self.assertDictEqual(http_requests[0].querystring,
                             {'offset' : ['319280322']})

    def test_parse_messages(self):
        """Test whether the method parses a raw file"""

        body_msgs = read_file('data/telegram_messages.json')
        body_msgs_empty = read_file('data/telegram_messages_empty.json')

        messages = Telegram.parse_messages(body_msgs)
        result = [msg for msg in messages]

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['message']['message_id'], 31)
        self.assertEqual(result[1]['message']['message_id'], 32)
        self.assertEqual(result[2]['message']['message_id'], 33)

        messages = Telegram.parse_messages(body_msgs_empty)
        result = [msg for msg in messages]

        self.assertEqual(len(result), 0)


class TestTelegramBackendCache(unittest.TestCase):
    """Telegram backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        http_requests = setup_http_server()

        # First, we fetch the messages from the server,
        # storing them in a cache
        cache = Cache(self.tmp_path)
        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN, cache=cache)

        messages = [msg for msg in tlg.fetch()]
        self.assertEqual(len(http_requests), 3)

        # Now, we get the messages from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_messages = [msg for msg in tlg.fetch_from_cache()]
        self.assertEqual(len(cached_messages), len(messages))

        expected = [(31, '5a5457aec04237ac3fab30031e84c745a3bdd157', 1467289325.0, 319280318),
                    (32, '16a59e93e919174fcd4e70e5b3289201c1016c72', 1467289329.0, 319280319),
                    (33, '9d03eeea7e3186ca8e5c150b4cbf18c8283cca9d', 1467289371.0, 319280320),
                    (34, '2e61e72b64c9084f3c5a36671c3119641c3ae42f', 1467370372.0, 319280321)]

        self.assertEqual(len(cached_messages), len(expected))

        for x in range(len(cached_messages)):
            message = cached_messages[x]
            self.assertEqual(message['data']['message']['message_id'], expected[x][0])
            self.assertEqual(message['origin'], 'https://telegram.org/' +  TELEGRAM_BOT)
            self.assertEqual(message['uuid'], expected[x][1])
            self.assertEqual(message['updated_on'], expected[x][2])
            self.assertEqual(message['offset'], expected[x][3])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'https://telegram.org/' +  TELEGRAM_BOT)

        # No more requests were sent
        self.assertEqual(len(http_requests), 3)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any message returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN, cache=cache)
        cached_messages = [msg for msg in tlg.fetch_from_cache()]
        self.assertEqual(len(cached_messages), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        tlg = Telegram(TELEGRAM_BOT, TELEGRAM_TOKEN)

        with self.assertRaises(CacheError):
            _ = [msg for msg in tlg.fetch_from_cache()]


class TestTelegramCommand(unittest.TestCase):
    """Tests for TelegramCommand class"""

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['mybot',
                '--backend-token', '12345678',
                '--offset', '10',
                '--chats', '-10000',
                '--tag', 'test']

        cmd = TelegramCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.bot, 'mybot')
        self.assertEqual(cmd.parsed_args.backend_token, '12345678')
        self.assertEqual(cmd.parsed_args.offset, 10)
        self.assertEqual(cmd.parsed_args.chats, [-10000])
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, Telegram)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = TelegramCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestTelegramBotClient(unittest.TestCase):
    """TelegramBotClient unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization parameters"""

        client = TelegramBotClient(TELEGRAM_TOKEN)
        self.assertEqual(client.bot_token, TELEGRAM_TOKEN)

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
                    'offset' : ['319280321']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/bot12345678/getUpdates')
        self.assertDictEqual(req.querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

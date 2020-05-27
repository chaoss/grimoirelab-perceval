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
#     Venu Vardhan Reddy Tekula <venuvardhanreddytekula8@gmail.com>
#


import unittest
import os

import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.zulip import (Zulip,
                                          ZulipClient,
                                          ZulipCommand)

ZULIP_CHAT_URL = 'https://example.zulipchat.com'
ZULIP_CHAT_API_URL = '/api/v1/messages'
ZULIP_MESSAGE_URL = ZULIP_CHAT_URL + ZULIP_CHAT_API_URL

email = 'bot@zulipchat.com'
api_token = 'aaaa'
AUTH = (email, api_token)


def read_file(filename):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), 'rb') as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []
    message_page_1 = read_file('data/zulip/message_page_1')
    message_page_2 = read_file('data/zulip/message_page_2')

    httpretty.register_uri(httpretty.GET,
                           ZULIP_MESSAGE_URL,
                           body=message_page_1,
                           status=200)

    httpretty.register_uri(httpretty.GET,
                           ZULIP_MESSAGE_URL,
                           body=message_page_2,
                           status=200)


class MockedZulipClient(ZulipClient):
    """Mocked Zulip client for testing"""

    def __init__(self, url, stream, email, api_token, archive=None,
                 from_archive=False, ssl_verify=True):
        super().__init__(url, stream, email, api_token,
                         archive=archive,
                         from_archive=from_archive,
                         ssl_verify=ssl_verify
                         )


class TestZulipBackend(unittest.TestCase):
    """Zulip backend tests"""

    def test_inialization(self):
        """Test whether attributes are initializated"""

        backend = Zulip(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                        email='bot@zulipchat.com', api_token='aaaa', tag='test')
        self.assertEqual(backend.origin, 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(backend.url, 'https://example.zulipchat.com/')
        self.assertEqual(backend.stream, 'abcdefghijkl')
        self.assertEqual(backend.email, 'bot@zulipchat.com')
        self.assertEqual(backend.api_token, 'aaaa')
        self.assertEqual(backend.tag, 'test')
        self.assertTrue(backend.ssl_verify)
        self.assertIsNone(backend.client)

        backend = Zulip(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                        email='bot@zulipchat.com', api_token='aaaa', tag=None)
        self.assertEqual(backend.origin, 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(backend.tag, 'https://example.zulipchat.com/abcdefghijkl')

        backend = Zulip(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                        email='bot@zulipchat.com', api_token='aaaa', tag='')
        self.assertEqual(backend.origin, 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(backend.tag, 'https://example.zulipchat.com/abcdefghijkl')

        backend = Zulip(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                        email='bot@zulipchat.com', api_token='aaaa', tag='', ssl_verify=False)
        self.assertEqual(backend.origin, 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(backend.tag, 'https://example.zulipchat.com/abcdefghijkl')
        self.assertFalse(backend.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertTrue(Zulip.has_archiving())

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertTrue(Zulip.has_resuming())

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of messages is returned"""

        setup_http_server()

        backend = Zulip(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                        email='bot@zulipchat.com', api_token='aaaa')
        messages = [m for m in backend.fetch()]

        self.assertEqual(len(messages), 2)

        message = messages[0]
        self.assertEqual(message['data']['id'], 159310770)
        self.assertEqual(message['origin'], 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(message['uuid'], '20d0159b91d0b912886264f2f1dad39689282559')
        self.assertEqual(message['updated_on'], 1551066955.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(message['data']['content'], 'This is test messgae 1')
        self.assertEqual(message['data']['sender_id'], 113001)
        self.assertEqual(message['data']['sender_full_name'], 'Bot')

        message = messages[1]
        self.assertEqual(message['data']['id'], 159310824)
        self.assertEqual(message['origin'], 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(message['uuid'], '330afca6d053fb05579e3763c7a553c1ee663cb6')
        self.assertEqual(message['updated_on'], 1551067006.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://example.zulipchat.com/abcdefghijkl')
        self.assertEqual(message['data']['content'], 'This is test messgae 2')
        self.assertEqual(message['data']['sender_id'], 113001)
        self.assertEqual(message['data']['sender_full_name'], 'Bot')

    @httpretty.activate
    def test_search_fields_messages(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        backend = Zulip(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                        email='bot@zulipchat.com', api_token='aaaa')

        messages = [m for m in backend.fetch()]
        message = messages[0]
        self.assertEqual(message['search_fields']['item_id'], backend.metadata_id(message['data']))
        self.assertEqual(message['search_fields']['stream'], 'abcdefghijkl')


class TestZulipClient(unittest.TestCase):
    """Tests for ZulipClient class"""

    def test_init(self):
        """Check attributes initialization"""

        client = ZulipClient(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                             email='bot@zulipchat.com', api_token='aaaa', ssl_verify=True)
        self.assertIsInstance(client, ZulipClient)
        self.assertEqual(client.email, 'bot@zulipchat.com')
        self.assertEqual(client.api_token, 'aaaa')
        self.assertTrue(client.ssl_verify)

        client = ZulipClient(url='https://example.zulipchat.com/', stream='abcdefghijkl',
                             email='bot@zulipchat.com', api_token='aaaa', ssl_verify=False)
        self.assertIsInstance(client, ZulipClient)
        self.assertEqual(client.email, 'bot@zulipchat.com')
        self.assertEqual(client.api_token, 'aaaa')
        self.assertFalse(client.ssl_verify)


class TestZulipCommand(unittest.TestCase):
    """Tests for ZulipCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Zulip"""

        self.assertIs(ZulipCommand.BACKEND, Zulip)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = ZulipCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Zulip)

        args = ['-t', 'aaaa',
                '-e', 'bot@zulipchat.com',
                '--tag', 'test',
                'https://example.zulipchat.com/', 'abcdefghijkl']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'https://example.zulipchat.com/')
        self.assertEqual(parsed_args.stream, 'abcdefghijkl')
        self.assertEqual(parsed_args.email, 'bot@zulipchat.com')
        self.assertEqual(parsed_args.api_token, 'aaaa')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.ssl_verify)

        args = ['-t', 'aaaa',
                '-e', 'bot@zulipchat.com',
                '--tag', 'test',
                '--no-ssl-verify',
                'https://example.zulipchat.com/', 'abcdefghijkl']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'https://example.zulipchat.com/')
        self.assertEqual(parsed_args.stream, 'abcdefghijkl')
        self.assertEqual(parsed_args.email, 'bot@zulipchat.com')
        self.assertEqual(parsed_args.api_token, 'aaaa')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertFalse(parsed_args.ssl_verify)


if __name__ == '__main__':
    unittest.main(warnings='ignore')

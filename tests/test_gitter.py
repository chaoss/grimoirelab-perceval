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
#     Animesh Kumar <animuz111@gmail.com>
#

import copy
import datetime
import httpretty
import os
import unittest
import unittest.mock
import dateutil.tz
import time

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import (BackendError,
                             RateLimitError)
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.gitter import (Gitter,
                                           GitterClient,
                                           GitterCommand,
                                           logger,
                                           MIN_RATE_LIMIT,
                                           MAX_ITEMS)

from base import TestCaseBackendArchive

GITTER_API_URL = 'https://api.gitter.im/v1/'
GITTER_URL = 'https://gitter.im/'
GITTER_ROOM_ID = '5e78b6b9d73408ce4fddb4e5'
GITTER_MESSAGE_URL = GITTER_API_URL + 'rooms/' + GITTER_ROOM_ID + '/chatMessages'
GITTER_ROOM_URL = GITTER_API_URL + 'rooms'


def setup_http_server(no_message=False, rate_limit_headers=None):
    """Setup a mock HTTP server"""

    message_page_1 = read_file('data/gitter/message_page_1')
    message_page_2 = read_file('data/gitter/message_page_2')
    rooms = read_file('data/gitter/rooms')
    message_empty = read_file('data/gitter/message_empty')

    if not rate_limit_headers:
        rate_limit_headers = {}

    httpretty.register_uri(httpretty.GET,
                           GITTER_ROOM_URL,
                           body=rooms,
                           status=200,
                           forcing_headers=rate_limit_headers)
    if not no_message:
        httpretty.register_uri(httpretty.GET,
                               GITTER_MESSAGE_URL + '?limit=1&beforeId=5e78b710c2676245a82ab85a',
                               body=message_empty,
                               status=200,
                               forcing_headers=rate_limit_headers)

        httpretty.register_uri(httpretty.GET,
                               GITTER_MESSAGE_URL + '?limit=1',
                               body=message_page_1,
                               status=200,
                               forcing_headers=rate_limit_headers)

        httpretty.register_uri(httpretty.GET,
                               GITTER_MESSAGE_URL + '?limit=1',
                               body=message_page_2,
                               status=200,
                               forcing_headers=rate_limit_headers)

    else:
        httpretty.register_uri(httpretty.GET,
                               GITTER_MESSAGE_URL,
                               body=message_empty,
                               status=200,
                               forcing_headers=rate_limit_headers)


class MockedGitterClient(GitterClient):
    """Mocked Gitter client for testing"""

    def __init__(self, api_token, max_items=MAX_ITEMS, archive=None,
                 sleep_for_rate=False, min_rate_to_sleep=MIN_RATE_LIMIT,
                 from_archive=False, ssl_verify=True):
        super().__init__(api_token, max_items=max_items,
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


class TestGitterBackend(unittest.TestCase):
    """Tests for Gitter backend class"""

    def test_initialization(self):
        """Test whether attributes are initialized"""

        backend = Gitter(group='testapicomm', room='community', api_token='aaa', tag='test')

        self.assertEqual(backend.group, 'testapicomm')
        self.assertEqual(backend.room, 'community')
        self.assertEqual(backend.api_token, "aaa")
        self.assertEqual(backend.min_rate_to_sleep, MIN_RATE_LIMIT)
        self.assertIsNone(backend.room_id)
        self.assertIsNone(backend.client)
        self.assertFalse(backend.sleep_for_rate)
        self.assertTrue(backend.ssl_verify)
        self.assertEqual(backend.origin, 'https://gitter.im/testapicomm/community')
        self.assertEqual(backend.tag, 'test')
        self.assertEqual(backend.max_items, MAX_ITEMS)

        # When tag is empty or None it will be set to
        # the value in uri
        backend = Gitter(group='testapicomm', room='community', api_token='aaa', tag=None)
        self.assertEqual(backend.origin, 'https://gitter.im/testapicomm/community')
        self.assertEqual(backend.tag, 'https://gitter.im/testapicomm/community')

        backend = Gitter(group='testapicomm', room='community', api_token='aaa', tag='')
        self.assertEqual(backend.origin, 'https://gitter.im/testapicomm/community')
        self.assertEqual(backend.tag, 'https://gitter.im/testapicomm/community')

        backend = Gitter(group='testapicomm', room='community', api_token='aaa', tag='', ssl_verify=False,
                         sleep_for_rate=True, max_items=20, min_rate_to_sleep=1)
        self.assertEqual(backend.origin, 'https://gitter.im/testapicomm/community')
        self.assertEqual(backend.tag, 'https://gitter.im/testapicomm/community')
        self.assertFalse(backend.ssl_verify)
        self.assertTrue(backend.sleep_for_rate)
        self.assertEqual(backend.max_items, 20)
        self.assertEqual(backend.min_rate_to_sleep, 1)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Gitter.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Gitter.has_resuming(), False)

    @httpretty.activate
    def test_fetch_messages(self):
        """Test whether a list of messages is returned"""

        setup_http_server()

        backend = Gitter(group='testapicomm', room='community', api_token='aaa', max_items=1)
        messages = [m for m in backend.fetch()]

        self.assertEqual(len(messages), 2)

        message = messages[0]
        self.assertEqual(message['data']['id'], '5e7990ecada8262f814a8056')
        self.assertEqual(message['origin'], 'https://gitter.im/testapicomm/community')
        self.assertEqual(message['uuid'], '8053a8916819636b24e795c594cd24310835477f')
        self.assertEqual(message['updated_on'], 1585025260.777)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://gitter.im/testapicomm/community')
        self.assertEqual(message['data']['text'], 'This is test message 2')
        self.assertEqual(message['data']['fromUser']['id'], '5e2f7e72d73408ce4fd7f187')
        self.assertEqual(message['data']['fromUser']['displayName'], 'Animesh Kumar')

        message = messages[1]
        self.assertEqual(message['data']['id'], '5e78b710c2676245a82ab85a')
        self.assertEqual(message['origin'], 'https://gitter.im/testapicomm/community')
        self.assertEqual(message['uuid'], 'f44b4cdbec932bb1dded7749941b3973853a6bae')
        self.assertEqual(message['updated_on'], 1584969488.8)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://gitter.im/testapicomm/community')
        self.assertEqual(message['data']['text'], 'This is test message 1')
        self.assertEqual(message['data']['fromUser']['id'], '5e2f7e72d73408ce4fd7f187')
        self.assertEqual(message['data']['fromUser']['displayName'], 'Animesh Kumar')

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test when fetching messages from a given date"""

        setup_http_server()
        from_date = datetime.datetime(2020, 3, 24, 0, 0, tzinfo=dateutil.tz.tzutc())
        backend = Gitter(group='testapicomm', room='community', api_token='aaa', max_items=1)
        messages = [m for m in backend.fetch(from_date=from_date)]
        self.assertEqual(len(messages), 1)

        message = messages[0]
        self.assertEqual(message['data']['id'], '5e7990ecada8262f814a8056')
        self.assertEqual(message['origin'], 'https://gitter.im/testapicomm/community')
        self.assertEqual(message['uuid'], '8053a8916819636b24e795c594cd24310835477f')
        self.assertEqual(message['updated_on'], 1585025260.777)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'https://gitter.im/testapicomm/community')
        self.assertEqual(message['data']['text'], 'This is test message 2')
        self.assertEqual(message['data']['fromUser']['id'], '5e2f7e72d73408ce4fd7f187')
        self.assertEqual(message['data']['fromUser']['displayName'], 'Animesh Kumar')

    @httpretty.activate
    def test_search_fields_messages(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        backend = Gitter(group='testapicomm', room='community', api_token='aaa')
        messages = [m for m in backend.fetch()]

        message = messages[0]
        self.assertEqual(message['search_fields']['item_id'], backend.metadata_id(message['data']))
        self.assertEqual(message['search_fields']['group'], 'testapicomm')
        self.assertEqual(message['search_fields']['room'], 'community')
        self.assertEqual(message['search_fields']['room_id'], GITTER_ROOM_ID)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether an empty list is returned
         when there are no messages
         """
        setup_http_server(no_message=True)

        backend = Gitter(group='testapicomm', room='community', api_token='aaa')
        messages = [m for m in backend.fetch()]
        self.assertListEqual(messages, [])

    @httpretty.activate
    def test_room_id_not_found(self):
        """Test whether an error is raised if room id is not found"""

        setup_http_server()

        backend = Gitter(group='testapicomm', room='community_not', api_token='aaa')
        with self.assertLogs(logger, level='ERROR') as cm:
            with self.assertRaises(BackendError):
                _ = [m for m in backend.fetch()]
            self.assertEqual(cm.output[0], 'ERROR:perceval.backends.core.gitter:'
                                           'Room id not found for room testapicomm/community_not')


class TestGitterBackendArchive(TestCaseBackendArchive):
    """Gitter backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Gitter(group='testapicomm', room='community', api_token='aaa',
                                            max_items=5, archive=self.archive)
        self.backend_read_archive = Gitter(group='testapicomm', room='community', api_token='aaa',
                                           max_items=5, archive=self.archive)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.gitter.datetime_utcnow')
    def test_fetch_from_archive(self, mock_utcnow):
        """Test if a list of messages is returned from archive"""

        mock_utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.gitter.datetime_utcnow')
    def test_fetch_from_date_from_archive(self, mock_utcnow):
        """Test whether a list of messages is returned from archive after a given date"""

        mock_utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()

        from_date = datetime.datetime(2020, 3, 24, 18, 35, 40, 69,
                                      tzinfo=dateutil.tz.tzutc())
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.gitter.datetime_utcnow')
    def test_fetch_empty_from_archive(self, mock_utcnow):
        """Test whether no messages are returned when the archive is empty"""

        mock_utcnow.return_value = datetime.datetime(2020, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        setup_http_server()

        from_date = datetime.datetime(2020, 3, 24,
                                      tzinfo=dateutil.tz.tzutc())
        self._test_fetch_from_archive(from_date=from_date)


class TestGitterClient(unittest.TestCase):
    """Tests for GitterClient class"""

    def test_init(self):
        """Check attributes initialization"""

        client = GitterClient(api_token='aaa', ssl_verify=True)
        self.assertIsInstance(client, GitterClient)
        self.assertEqual(client.api_token, 'aaa')
        self.assertTrue(client.ssl_verify)
        self.assertFalse(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, MIN_RATE_LIMIT)

        client = GitterClient(api_token='aaa', sleep_for_rate=True, min_rate_to_sleep=1, ssl_verify=False)
        self.assertIsInstance(client, GitterClient)
        self.assertEqual(client.api_token, 'aaa')
        self.assertFalse(client.ssl_verify)
        self.assertTrue(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, 1)

    @httpretty.activate
    def test_message(self):
        """Test whether messages are fetched"""

        setup_http_server()

        client = GitterClient(api_token='aaa', ssl_verify=True)

        messages = [m for m in client.message_page(GITTER_ROOM_ID, before_id=None)]

        self.assertEqual(len(messages), 6)

        # Check requests
        expected = {
            'limit': ['100'],
        }

        self.assertEqual(httpretty.last_request().querystring, expected)
        self.assertEqual(httpretty.last_request().headers["Authorization"], 'Bearer aaa')

    @httpretty.activate
    def test_get_room_id(self):
        """Test whether room id is returned"""

        setup_http_server()

        client = GitterClient(api_token='aaa', ssl_verify=True)
        room_id = client.get_room_id('testapicomm/community')
        self.assertEqual(room_id, GITTER_ROOM_ID)

    @httpretty.activate
    def test_room_id_not_found(self):
        """Test whether room id returned is
        None when room id is not found
        """
        setup_http_server()

        client = GitterClient(api_token='aaa', ssl_verify=True)

        self.assertIsNone(client.get_room_id('testapicomm/community_not'))

    def test_calculate_time_to_reset(self):
        """Test whether the time to reset is zero if the sleep time is negative"""

        client = MockedGitterClient('aaa', max_items=10, archive=None,
                                    from_archive=False, min_rate_to_sleep=2,
                                    sleep_for_rate=True, ssl_verify=False)
        time_to_reset = client.calculate_time_to_reset()
        self.assertEqual(time_to_reset, 0)

    @httpretty.activate
    def test_sleep_for_rate(self):
        """Test if the clients sleeps when the rate limit is reached"""

        wait = 10
        reset = int(time.time() + wait)
        rate_limit_headers = {'X-RateLimit-Remaining': '0',
                              'X-RateLimit-Reset': reset}

        setup_http_server(rate_limit_headers=rate_limit_headers)

        client = GitterClient('aaaa', max_items=2,
                              min_rate_to_sleep=5,
                              sleep_for_rate=True)

        room_id = client.get_room_id('testapicomm/community')
        _ = [m for m in client.message_page(room_id, before_id=None)]
        after = float(time.time())

        self.assertTrue(reset >= after)

    @httpretty.activate
    def test_rate_limit_error(self):
        """Test if a rate limit error is raised when rate is exhausted"""

        wait = 2
        reset = int(time.time() + wait)
        rate_limit_headers = {'X-RateLimit-Remaining': '0',
                              'X-RateLimit-Reset': reset}

        setup_http_server(rate_limit_headers=rate_limit_headers)

        client = GitterClient('aaaa', max_items=1, sleep_for_rate=False)

        room_id = client.get_room_id('testapicomm/community')
        with self.assertRaises(RateLimitError):
            _ = [m for m in client.message_page(room_id, before_id=None)]

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "https://api.gitter.im/v1/testapicomm/community"
        headers = {
            GitterClient.HAUTHORIZATION: 'Bearer aaaa'
        }

        payload = {
            'limit': 10,
            'beforeId': '123',
        }

        s_url, s_headers, s_payload = GitterClient.sanitize_for_archive(url, copy.deepcopy(headers), payload)
        headers.pop(GitterClient.HAUTHORIZATION)

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)


class TestGitterCommand(unittest.TestCase):
    """Tests for GitterCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Gitter"""

        self.assertIs(GitterCommand.BACKEND, Gitter)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GitterCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Gitter)

        args = ['-t', 'aaa',
                '--tag', 'test',
                '--sleep-for-rate',
                '--from-date', '1970-01-01',
                'testapicomm', 'community']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.api_token, 'aaa')
        self.assertEqual(parsed_args.group, 'testapicomm')
        self.assertEqual(parsed_args.room, 'community')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertTrue(parsed_args.sleep_for_rate)

        from_date = datetime.datetime(2020, 3, 1, 0, 0, tzinfo=dateutil.tz.tzutc())

        args = ['-t', 'aaa',
                '--tag', 'test',
                '--max-items', '10',
                '--no-ssl-verify',
                '--min-rate-to-sleep', '1',
                '--from-date', '2020-03-01',
                'testapicomm', 'community']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.api_token, 'aaa')
        self.assertEqual(parsed_args.group, 'testapicomm')
        self.assertEqual(parsed_args.room, 'community')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, from_date)
        self.assertEqual(parsed_args.min_rate_to_sleep, 1)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertFalse(parsed_args.sleep_for_rate)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

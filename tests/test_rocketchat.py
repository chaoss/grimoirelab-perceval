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
#

import pkg_resources
import datetime
import dateutil
import unittest
import unittest.mock
import os
import httpretty
import json

pkg_resources.declare_namespace('perceval.backends')


from grimoirelab_toolkit.datetime import str_to_datetime

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.rocketchat import (RocketChat,
                                               RocketChatCommand,
                                               RocketChatClient,
                                               MIN_RATE_LIMIT)

ROCKETCHAT_URL = 'http://example.com/'
ROCKETCHAT_MESSAGES_URL = ROCKETCHAT_URL + 'api/v1/channels.messages?roomName=general'
ROCKETCHAT_CHANNEL_INFO_URL = ROCKETCHAT_URL + 'api/v1/channels.info?roomName=general'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server(archived_channel=False):
    """Setup a mock HTTP server"""

    http_requests = []

    channel_history = read_file('data/rocketchat/rocketchat_channel_messages.json', 'r')
    channel_info = read_file('data/rocketchat/rocketchat_channel_info.json', 'r')
    empty_message = read_file('data/rocketchat/rocketchat_empty_message.json', 'r')
    channel_history_date = read_file('data/rocketchat/rocketchat_messages_20191119.json', 'r')

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        status = 200
        if uri.startswith(ROCKETCHAT_MESSAGES_URL):
            if "offset" in params and int(params["offset"][0]) < 100:
                query = json.loads(params["query"][0])
                from_date = str_to_datetime(query["_updatedAt"]["$gte"]["$date"])
                if from_date == DEFAULT_DATETIME:
                    body = channel_history
                else:
                    body = channel_history_date
            else:
                body = empty_message
        elif uri.startswith(ROCKETCHAT_CHANNEL_INFO_URL):
            body = channel_info
        else:
            raise

        http_requests.append(last_request)

        return status, headers, body

    httpretty.register_uri(httpretty.GET,
                           ROCKETCHAT_MESSAGES_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    httpretty.register_uri(httpretty.GET,
                           ROCKETCHAT_CHANNEL_INFO_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestRocketchatBackend(unittest.TestCase):
    """Rocketchat backend tests"""

    def test_initialization(self):
        """Test whether attributes are initialized"""

        rocketchat = RocketChat(user_id='aaa', url=ROCKETCHAT_URL, channel_name='test', api_token='aaaa',
                                max_items=5, tag="test")

        self.assertEqual(rocketchat.url, ROCKETCHAT_URL)
        self.assertEqual(rocketchat.tag, 'test')
        self.assertEqual(rocketchat.user_id, "aaa")
        self.assertEqual(rocketchat.api_token, "aaaa")
        self.assertEqual(rocketchat.channel_name, 'test')
        self.assertEqual(rocketchat.max_items, 5)
        self.assertEqual(rocketchat.min_rate_to_sleep, MIN_RATE_LIMIT)
        self.assertFalse(rocketchat.sleep_for_rate)
        self.assertIsNone(rocketchat.client)
        self.assertTrue(rocketchat.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        rocketchat = RocketChat(ROCKETCHAT_URL, user_id='aaa', api_token='aaaa', channel_name='test', ssl_verify=False)
        self.assertEqual(rocketchat.url, ROCKETCHAT_URL)
        self.assertEqual(rocketchat.user_id, "aaa")
        self.assertEqual(rocketchat.api_token, "aaaa")
        self.assertEqual(rocketchat.tag, ROCKETCHAT_URL)
        self.assertFalse(rocketchat.ssl_verify)

        rocketchat = RocketChat(ROCKETCHAT_URL, user_id='aaa', api_token='aaaa', channel_name='general', tag='')
        self.assertEqual(rocketchat.url, ROCKETCHAT_URL)
        self.assertEqual(rocketchat.user_id, "aaa")
        self.assertEqual(rocketchat.api_token, "aaaa")
        self.assertEqual(rocketchat.tag, ROCKETCHAT_URL)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of messages"""

        http_requests = setup_http_server()

        rocketchat = RocketChat(ROCKETCHAT_URL, user_id='aaa', api_token='aaaa', channel_name='general')
        messages = [msg for msg in rocketchat.fetch()]
        expected = [{"_id": "RMnDyzfePfhCpwq5K",
                     "_updatedAt": "2020-04-06T16:51:23.226Z",
                     "channels": [],
                     "mentions": [],
                     "msg": "Message",
                     "rid": "GENERAL",
                     "ts": "2020-04-06T16:51:21.311Z",
                     "u": {"_id": "mYYjeTe6BSuApydQu",
                           "name": "Umit Altun",
                           "username": "ualtun"}
                     },
                    {"_id": "JXtqPMtFPFNuu44XA",
                     "_updatedAt": "2020-04-06T16:55:02.354Z",
                     "groupable": "False",
                     "msg": "hmarcuse",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2020-04-06T16:55:02.354Z",
                     "u": {"_id": "MtXvMtT4JRYwBEdGA", "username": "hmarcuse"}},
                    {"_id": "gYP2RcZpXLgB8AGo6",
                     "_updatedAt": "2020-04-06T16:55:17.221Z",
                     "attachments": [],
                     "groupable": "False",
                     "msg": "Plappointments ",
                     "rid": "GENERAL",
                     "t": "discussion-created",
                     "ts": "2020-02-06T16:49:12.662Z",
                     "u": {"_id": "Kce278HSvWbYLQzSk", "username": "Matt_Pulliam"}},
                    {"_id": "qi27AXKX7gzDQYjnn",
                     "_updatedAt": "2020-04-06T16:55:29.586Z",
                     "groupable": "False",
                     "msg": "Oric",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2020-04-06T16:55:29.586Z",
                     "u": {"_id": "pPE8Y7xAxJcDQn56Z", "username": "Oric"}}]

        self.assertEqual(len(messages), len(expected))

        for x in range(len(messages)):
            message = messages[x]
            expected_message = expected[x]
            self.assertEqual(message["data"]["_id"], expected_message["_id"])
            self.assertEqual(message["origin"], ROCKETCHAT_URL)
            self.assertEqual(message["data"]["_updatedAt"], expected_message["_updatedAt"])
            self.assertDictEqual(message["data"]["u"], expected_message["u"])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.rocketchat.datetime_utcnow')
    def test_fetch_from_date(self, mock_utcnow):
        """Test if it fetches a list of messages since a given date"""

        http_requests = setup_http_server()

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())

        from_date = datetime.datetime(2019, 11, 19,
                                      tzinfo=dateutil.tz.tzutc())

        rocketchat = RocketChat(ROCKETCHAT_URL, user_id='aaa', api_token='aaaa', channel_name='general')

        messages = [msg for msg in rocketchat.fetch(from_date=from_date)]

        expected = [{"_id": "76ZzGoMA3kJNeRaaE",
                     "_updatedAt": "2019-11-19T01:12:52.778Z",
                     "groupable": "False",
                     "msg": "jjbiggins",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2019-11-19T01:12:52.778Z",
                     "u": {"_id": "DqTgEXnfcrp4LrroR", "username": "jjbiggins"}},
                    {"_id": "fX3WNEPWWFyZGfk3E",
                     "_updatedAt": "2019-11-19T01:30:36.779Z",
                     "groupable": "False",
                     "msg": "alison.schwartz",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2019-11-19T01:30:36.779Z",
                     "u": {"_id": "fzrk5x54PoZMS9k9D",
                           "username": "alison.schwartz"}},
                    {"_id": "awtcArQ7SXQDmKqvv",
                     "_updatedAt": "2019-11-19T01:51:26.531Z",
                     "groupable": "False",
                     "msg": "anderson.calefi",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2019-11-19T01:51:26.531Z",
                     "u": {"_id": "S3uEYgbMCjcfncAu9",
                           "username": "anderson.calefi"}},
                    {"_id": "4dZQWh2Jt5AFrBQDv",
                     "_updatedAt": "2019-11-19T01:55:01.865Z",
                     "groupable": "False",
                     "msg": "danielle.mcgary",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2019-11-19T01:55:01.865Z",
                     "u": {"_id": "vJDQ9WYswYcqFw9zY",
                           "username": "danielle.mcgary"}},
                    {"_id": "epefzvY2WKuGY9bgu",
                     "_updatedAt": "2019-11-19T02:01:23.496Z",
                     "groupable": "False",
                     "msg": "singh0802",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2019-11-19T02:01:23.496Z",
                     "u": {"_id": "m6Q5XEangryF4Ffid", "username": "singh0802"}},
                    {"_id": "WiAzQiCtA7wdTMf5R",
                     "_updatedAt": "2019-11-19T02:40:30.163Z",
                     "groupable": "False",
                     "msg": "sergei.finogenov",
                     "rid": "GENERAL",
                     "t": "uj",
                     "ts": "2019-11-19T02:40:30.163Z",
                     "u": {"_id": "b59GbWj3XvmWdLbd4",
                           "username": "sergei.finogenov"}}]

        for x in range(len(messages)):
            message = messages[x]
            expected_message = expected[x]
            self.assertEqual(message["data"]["ts"], expected_message["ts"])
            self.assertEqual(message["data"]["_updatedAt"], expected_message["_updatedAt"])
            self.assertDictEqual(message["data"]["u"], expected_message["u"])
            self.assertEqual(str_to_datetime(message["data"]["_updatedAt"]).date(), str_to_datetime("2019-11-19").date())

    def test_parse_data_messages(self):
        """Test if it parses a channel info JSON stream"""

        raw_messages = read_file('data/rocketchat/rocketchat_channel_messages.json', 'r')
        rocketchat = RocketChat(ROCKETCHAT_URL, user_id='aaa', api_token='aaaa', channel_name='general')

        messages = rocketchat.parse_data(raw_messages,"messages")

        expected_ids = ["RMnDyzfePfhCpwq5K", "JXtqPMtFPFNuu44XA", "gYP2RcZpXLgB8AGo6", "qi27AXKX7gzDQYjnn"]
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 4)

        for x in range(len(messages)):
            message = messages[x]
            self.assertEqual(message["_id"], expected_ids[x])


class TestRocketchatClient(unittest.TestCase):
    """Rocketchat client unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """

    def test_init(self):
        """Test initialization parameters"""

        client = RocketChatClient(ROCKETCHAT_URL, 'aaa', 'aaaa')
        self.assertEqual(client.api_token, 'aaaa')
        self.assertTrue(client.ssl_verify)

        client = RocketChatClient(ROCKETCHAT_URL, 'aaa', 'aaaa', ssl_verify=False)
        self.assertEqual(client.base_url, ROCKETCHAT_URL)
        self.assertEqual(client.api_token, 'aaaa')
        self.assertFalse(client.ssl_verify)


class TestRocketchatCommand(unittest.TestCase):
    """RocketchatCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Rocketchat"""

        self.assertIs(RocketChatCommand.BACKEND, RocketChat)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = RocketChatCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, RocketChat)

        args = ['--tag', 'test', '--no-ssl-verify',
                '--api-token', 'aaaa',
                '--from-date', '1970-01-01',
                '--max-items', '10',
                '1234', ROCKETCHAT_URL, 'general']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.channel_name, 'general')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.api_token, 'aaaa')
        self.assertEqual(parsed_args.max_items, 10)
        self.assertEqual(parsed_args.user_id, '1234')
        self.assertEqual(parsed_args.url, ROCKETCHAT_URL)

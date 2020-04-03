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
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import unittest
import copy

import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.mattermost import (Mattermost,
                                               MattermostClient,
                                               MattermostCommand)
from grimoirelab_toolkit.datetime import datetime_utcnow

from base import TestCaseBackendArchive


MATTERMOST_API_URL = 'https://mattermost.example.com/api/v4'
MATTERMOST_CHANNEL_INFO = MATTERMOST_API_URL + '/channels/abcdefghijkl'
MATTERMOST_CHANNEL_POSTS = MATTERMOST_API_URL + '/channels/abcdefghijkl/posts'
MATTERMOST_USERS = MATTERMOST_API_URL + '/users'
MATTERMOST_USER_SDUENAS = MATTERMOST_USERS + '/8tbwn7uikpdy3gpse6fgiie5co'
MATTERMOST_USER_VALCOS = MATTERMOST_USERS + '/haqnaxe4cpn4jfsx3w7x3y96ea'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    channel_info = read_file('data/mattermost/mattermost_channel.json', 'rb')
    channel_posts = read_file('data/mattermost/mattermost_posts.json', 'rb')
    channel_posts_next = read_file('data/mattermost/mattermost_posts_next.json', 'rb')
    channel_posts_empty = read_file('data/mattermost/mattermost_posts_empty.json', 'rb')
    user_sduenas = read_file('data/mattermost/mattermost_user_sduenas.json', 'rb')
    user_valcos = read_file('data/mattermost/mattermost_user_valcos.json', 'rb')

    full_response = [
        channel_posts, channel_posts_next, channel_posts_empty
    ]

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()
        params = last_request.querystring

        status = 200

        if uri.startswith(MATTERMOST_USER_SDUENAS):
            body = user_sduenas
        elif uri.startswith(MATTERMOST_USER_VALCOS):
            body = user_valcos
        elif uri.startswith(MATTERMOST_CHANNEL_POSTS):
            if 'page' not in params:
                page = 0
            else:
                page = int(params['page'][0])
            body = full_response[page]
        elif uri.startswith(MATTERMOST_CHANNEL_INFO):
            body = channel_info
        else:
            raise Exception("no valid URL")

        http_requests.append(last_request)

        return status, headers, body

    httpretty.register_uri(httpretty.GET,
                           MATTERMOST_CHANNEL_INFO,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           MATTERMOST_CHANNEL_POSTS,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           MATTERMOST_USER_SDUENAS,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(1)
                           ])
    httpretty.register_uri(httpretty.GET,
                           MATTERMOST_USER_VALCOS,
                           responses=[
                               httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestMattermostBackend(unittest.TestCase):
    """Mattermost backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        mattermost = Mattermost('https://mattermost.example.com/', 'abcdefghijkl', 'aaaa',
                                max_items=5, tag='test',
                                sleep_for_rate=True, min_rate_to_sleep=10,
                                sleep_time=60)

        self.assertEqual(mattermost.origin, 'https://mattermost.example.com/abcdefghijkl')
        self.assertEqual(mattermost.channel, 'abcdefghijkl')
        self.assertEqual(mattermost.api_token, 'aaaa')
        self.assertEqual(mattermost.tag, 'test')
        self.assertEqual(mattermost.max_items, 5)
        self.assertTrue(mattermost.sleep_for_rate)
        self.assertTrue(mattermost.ssl_verify)
        self.assertEqual(mattermost.min_rate_to_sleep, 10)
        self.assertEqual(mattermost.sleep_time, 60)
        self.assertIsNone(mattermost.client)

        # When tag is empty or None it will be set to
        # the value in URL
        mattermost = Mattermost('https://mattermost.example.com/', 'abcdefghijkl', 'aaaa', ssl_verify=False)
        self.assertEqual(mattermost.origin, 'https://mattermost.example.com/abcdefghijkl')
        self.assertEqual(mattermost.tag, 'https://mattermost.example.com/abcdefghijkl')
        self.assertFalse(mattermost.ssl_verify)

        mattermost = Mattermost('https://mattermost.example.com/', 'abcdefghijkl', 'aaaa', tag='')
        self.assertEqual(mattermost.origin, 'https://mattermost.example.com/abcdefghijkl')
        self.assertEqual(mattermost.tag, 'https://mattermost.example.com/abcdefghijkl')

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Mattermost.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(Mattermost.has_resuming(), False)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of posts"""

        http_requests = setup_http_server()

        mattermost = Mattermost('https://mattermost.example.com/', 'abcdefghijkl', 'aaaa',
                                max_items=5)
        posts = [post for post in mattermost.fetch(from_date=None)]

        expected = [
            ('59io5i1f5bbetxtj6mbm67fouw', 'd023596f93fcd7e18838bd0adddae4e213d0ca15', 1523546846.639, 'sduenas'),
            ('pot46s7kjif7xx6x91ua7m4d7y', '8e4c190792621a567811d8b97b1d30ba8116b9b7', 1523546846.639, 'valcos'),
            ('zgzsgcnuobyf9bwdcbug8iqu6e', '409a4751fa5ec6e871694a1a16df5623f37a932e', 1523526214.021, 'sduenas'),
            ('sg3eifxowjba7k47xb16767isa', 'e5557d99965585ca643b71919e9fb3af2b849c8c', 1523526206.815, 'sduenas'),
            ('shs4ujzubtffzxbshxthfcxfdw', '549db8c7e437de41a80d5e3b87dc4e3289e80e26', 1523526199.108, 'sduenas'),
            ('swqyc3ekabrjbxc5bjf6hhba3w', 'e688e59eb9c672dd995ab15f39f2947f7b35d86a', 1523526187.090, 'valcos'),
            ('b15jpgkw9bftufcdzteqiypoyr', '1b702dbfd45e7f997b59cde56e7227b2f9464dba', 1523526181.298, 'valcos'),
            ('49ctz9ndgfd48eb5oq4xbjpfby', 'a377e2b8300f254cb2ee5c66ea532a39bbeb6745', 1523526171.280, 'valcos'),
            ('1ju85sxo7bfab8nf3yk5snn17a', '2411fc8c8cb8673ee99088d61537fe412aa17433', 1523525981.213, 'sduenas')
        ]
        expected_channel = ('grimoirelab', 'GrimoireLab channel')

        self.assertEqual(len(posts), len(expected))

        for x in range(len(posts)):
            post = posts[x]
            expc = expected[x]
            self.assertEqual(post['data']['id'], expc[0])
            self.assertEqual(post['uuid'], expc[1])
            self.assertEqual(post['origin'], 'https://mattermost.example.com/abcdefghijkl')
            self.assertEqual(post['updated_on'], expc[2])
            self.assertEqual(post['category'], 'post')
            self.assertEqual(post['tag'], 'https://mattermost.example.com/abcdefghijkl')
            self.assertEqual(post['data']['user_data']['username'], expc[3])
            self.assertEqual(post['data']['channel_data']['name'], expected_channel[0])
            self.assertEqual(post['data']['channel_data']['display_name'], expected_channel[1])

        # Check requests
        expected = [
            {
                'channel_id': ['abcdefghijkl']
            },
            {
                'per_page': ['5'],
                'page': ['0']
            },
            {},
            {},
            {
                'per_page': ['5'],
                'page': ['1']
            },
            {
                'per_page': ['5'],
                'page': ['2']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        mattermost = Mattermost('https://mattermost.example.com/', 'abcdefghijkl', 'aaaa',
                                max_items=5)
        posts = [post for post in mattermost.fetch()]

        post = posts[0]
        self.assertEqual(mattermost.metadata_id(post['data']), post['search_fields']['item_id'])
        self.assertEqual(post['data']['channel_data']['id'], 'abcdef4ut3dij8gywe38ktn51a')
        self.assertEqual(post['data']['channel_data']['id'], post['search_fields']['channel_id'])
        self.assertEqual(post['data']['channel_data']['name'], 'grimoirelab')
        self.assertEqual(post['data']['channel_data']['name'], post['search_fields']['channel_name'])

        post = posts[1]
        self.assertEqual(mattermost.metadata_id(post['data']), post['search_fields']['item_id'])
        self.assertEqual(post['data']['channel_data']['id'], 'abcdef4ut3dij8gywe38ktn51a')
        self.assertEqual(post['data']['channel_data']['id'], post['search_fields']['channel_id'])
        self.assertEqual(post['data']['channel_data']['name'], 'grimoirelab')
        self.assertEqual(post['data']['channel_data']['name'], post['search_fields']['channel_name'])

        post = posts[2]
        self.assertEqual(mattermost.metadata_id(post['data']), post['search_fields']['item_id'])
        self.assertEqual(post['data']['channel_data']['id'], 'abcdef4ut3dij8gywe38ktn51a')
        self.assertEqual(post['data']['channel_data']['id'], post['search_fields']['channel_id'])
        self.assertEqual(post['data']['channel_data']['name'], 'grimoirelab')
        self.assertEqual(post['data']['channel_data']['name'], post['search_fields']['channel_name'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether if fetches a set of posts from the given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2018, 4, 12, 9, 43, 2)

        mattermost = Mattermost('https://mattermost.example.com/', 'abcdefghijkl', 'aaaa',
                                max_items=5)
        posts = [post for post in mattermost.fetch(from_date=from_date)]

        expected = [
            ('59io5i1f5bbetxtj6mbm67fouw', 'd023596f93fcd7e18838bd0adddae4e213d0ca15', 1523546846.639, 'sduenas'),
            ('pot46s7kjif7xx6x91ua7m4d7y', '8e4c190792621a567811d8b97b1d30ba8116b9b7', 1523546846.639, 'valcos'),
            ('zgzsgcnuobyf9bwdcbug8iqu6e', '409a4751fa5ec6e871694a1a16df5623f37a932e', 1523526214.021, 'sduenas'),
            ('sg3eifxowjba7k47xb16767isa', 'e5557d99965585ca643b71919e9fb3af2b849c8c', 1523526206.815, 'sduenas'),
            ('shs4ujzubtffzxbshxthfcxfdw', '549db8c7e437de41a80d5e3b87dc4e3289e80e26', 1523526199.108, 'sduenas'),
            ('swqyc3ekabrjbxc5bjf6hhba3w', 'e688e59eb9c672dd995ab15f39f2947f7b35d86a', 1523526187.090, 'valcos')
        ]
        expected_channel = ('grimoirelab', 'GrimoireLab channel')

        self.assertEqual(len(posts), len(expected))

        for x in range(len(posts)):
            post = posts[x]
            expc = expected[x]
            self.assertEqual(post['data']['id'], expc[0])
            self.assertEqual(post['uuid'], expc[1])
            self.assertEqual(post['origin'], 'https://mattermost.example.com/abcdefghijkl')
            self.assertEqual(post['updated_on'], expc[2])
            self.assertEqual(post['category'], 'post')
            self.assertEqual(post['tag'], 'https://mattermost.example.com/abcdefghijkl')
            self.assertEqual(post['data']['user_data']['username'], expc[3])
            self.assertEqual(post['data']['channel_data']['name'], expected_channel[0])
            self.assertEqual(post['data']['channel_data']['display_name'], expected_channel[1])

        # Check requests
        expected = [
            {
                'channel_id': ['abcdefghijkl']
            },
            {
                'per_page': ['5'],
                'page': ['0']
            },
            {},
            {},
            {
                'per_page': ['5'],
                'page': ['1']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returned when there are no posts"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2019, 1, 1)

        mattermost = Mattermost('https://mattermost.example.com/', 'abcdefghijkl', 'aaaa',
                                max_items=5)
        posts = [post for post in mattermost.fetch(from_date=from_date)]

        self.assertEqual(len(posts), 0)

        # Check requests
        expected = [
            {
                'channel_id': ['abcdefghijkl']
            },
            {
                'per_page': ['5'],
                'page': ['0']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    def test_parse_json(self):
        """Test if it parses a JSON stream"""

        raw_json = read_file('data/mattermost/mattermost_posts.json')

        data = Mattermost.parse_json(raw_json)

        self.assertEqual(len(data['posts']), 5)
        self.assertEqual(len(data['order']), 5)


class TestMattermostBackendArchive(TestCaseBackendArchive):
    """Mattermost backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Mattermost('https://mattermost.example.com/',
                                                'abcdefghijkl', 'aaaa',
                                                max_items=5, archive=self.archive)
        self.backend_read_archive = Mattermost('https://mattermost.example.com/',
                                               'abcdefghijkl', 'aaaa',
                                               max_items=5, archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether it fetches a set of events from archive"""

        setup_http_server()
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_from_date_archive(self):
        """Test whether if fetches a set of events from the given date from archive"""

        setup_http_server()

        from_date = datetime.datetime(2018, 4, 12, 9, 43, 2)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returned when there are no events in the archive"""

        setup_http_server()

        from_date = datetime.datetime(2019, 1, 1)
        self._test_fetch_from_archive(from_date=from_date)


class TestMattermostCommand(unittest.TestCase):
    """Tests for MattermostCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Mattermost"""

        self.assertIs(MattermostCommand.BACKEND, Mattermost)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = MattermostCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Mattermost)

        args = ['https://mattermost.example.com/', 'abcdefghijkl',
                '--api-token', 'aaaa',
                '--max-items', '5',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01',
                '--sleep-for-rate',
                '--min-rate-to-sleep', '10',
                '--sleep-time', '10']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'https://mattermost.example.com/')
        self.assertEqual(parsed_args.channel, 'abcdefghijkl')
        self.assertEqual(parsed_args.api_token, 'aaaa')
        self.assertEqual(parsed_args.max_items, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.min_rate_to_sleep, 10)
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['https://mattermost.example.com/', 'abcdefghijkl',
                '--api-token', 'aaaa',
                '--max-items', '5',
                '--tag', 'test',
                '--no-archive',
                '--from-date', '1970-01-01',
                '--sleep-for-rate',
                '--min-rate-to-sleep', '10',
                '--sleep-time', '10',
                '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'https://mattermost.example.com/')
        self.assertEqual(parsed_args.channel, 'abcdefghijkl')
        self.assertEqual(parsed_args.api_token, 'aaaa')
        self.assertEqual(parsed_args.max_items, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertTrue(parsed_args.sleep_for_rate)
        self.assertEqual(parsed_args.min_rate_to_sleep, 10)
        self.assertEqual(parsed_args.sleep_time, 10)
        self.assertFalse(parsed_args.ssl_verify)


class TestMattermostClient(unittest.TestCase):
    """Mattermost API client tests.

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    def test_init(self):
        """Test initialization"""

        client = MattermostClient('https://mattermost.example.com/', 'aaaa')
        self.assertEqual(client.base_url, 'https://mattermost.example.com')
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_items, 60)
        self.assertFalse(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, 10)
        self.assertEqual(client.archive, None)
        self.assertFalse(client.from_archive)
        self.assertTrue(client.ssl_verify)

        client = MattermostClient('https://mattermost.example.com/', 'aaaa',
                                  max_items=5,
                                  sleep_for_rate=True,
                                  min_rate_to_sleep=5,
                                  sleep_time=3, ssl_verify=False)
        self.assertEqual(client.base_url, 'https://mattermost.example.com')
        self.assertEqual(client.api_token, 'aaaa')
        self.assertEqual(client.max_items, 5)
        self.assertTrue(client.sleep_for_rate)
        self.assertEqual(client.min_rate_to_sleep, 5)
        self.assertEqual(client.sleep_time, 3)
        self.assertFalse(client.ssl_verify)

    @httpretty.activate
    def test_channel(self):
        """Test channel API call"""

        http_requests = setup_http_server()

        client = MattermostClient('https://mattermost.example.com/', 'aaaa')

        # Call API
        channel = client.channel('abcdefghijkl')

        self.assertEqual(len(http_requests), 1)

        expected = [
            {
                'channel_id': ['abcdefghijkl']
            }
        ]

        self.assertEqual(len(http_requests), 1)

        for x in range(0, len(http_requests)):
            req = http_requests[x]
            self.assertEqual(req.method, 'GET')
            self.assertRegex(req.path, '/api/v4/channels/abcdefghijkl')
            self.assertDictEqual(req.querystring, expected[x])
            self.assertEqual(req.headers['Authorization'], 'Bearer aaaa')

    @httpretty.activate
    def test_posts(self):
        """Test posts API call"""

        http_requests = setup_http_server()

        client = MattermostClient('https://mattermost.example.com/', 'aaaa')

        # Call API
        posts = client.posts('abcdefghijkl')

        expected = [
            {
                'per_page': ['60'],
            }
        ]

        self.assertEqual(len(http_requests), 1)

        for x in range(0, len(http_requests)):
            req = http_requests[x]
            self.assertEqual(req.method, 'GET')
            self.assertRegex(req.path, '/api/v4/channels/abcdefghijkl/posts')
            self.assertDictEqual(req.querystring, expected[x])
            self.assertEqual(req.headers['Authorization'], 'Bearer aaaa')

    @httpretty.activate
    def test_posts_with_pagination(self):
        """Test posts API call using pagination"""

        http_requests = setup_http_server()

        client = MattermostClient('https://mattermost.example.com/', 'aaaa',
                                  max_items=5)

        # Call API with parameters
        posts = client.posts('abcdefghijkl', page=1)

        expected = [
            {
                'page': ['1'],
                'per_page': ['5'],
            }
        ]

        self.assertEqual(len(http_requests), 1)

        for x in range(0, len(http_requests)):
            req = http_requests[x]
            self.assertEqual(req.method, 'GET')
            self.assertRegex(req.path, '/api/v4/channels/abcdefghijkl/posts')
            self.assertDictEqual(req.querystring, expected[x])
            self.assertEqual(req.headers['Authorization'], 'Bearer aaaa')

    @httpretty.activate
    def test_user(self):
        """Test user API call"""

        http_requests = setup_http_server()

        client = MattermostClient('https://mattermost.example.com/', 'aaaa')

        # Call API
        user = client.user('8tbwn7uikpdy3gpse6fgiie5co')

        expected = [
            {}
        ]

        self.assertEqual(len(http_requests), 1)

        for x in range(0, len(http_requests)):
            req = http_requests[x]
            self.assertEqual(req.method, 'GET')
            self.assertRegex(req.path, '/api/v4/users/8tbwn7uikpdy3gpse6fgiie5co')
            self.assertDictEqual(req.querystring, expected[x])
            self.assertEqual(req.headers['Authorization'], 'Bearer aaaa')

    @httpretty.activate
    def test_calculate_time_to_reset(self):
        """Test whether the time to reset is zero if the sleep time is negative"""

        user = read_file('data/mattermost/mattermost_user_sduenas.json', 'rb')
        httpretty.register_uri(httpretty.GET,
                               MATTERMOST_USER_SDUENAS,
                               body=user,
                               status=200,
                               forcing_headers={
                                   'X-RateLimit-Remaining': '20',
                                   'X-RateLimit-Reset': int(datetime_utcnow().replace(microsecond=0).timestamp())
                               })

        client = MattermostClient('https://mattermost.example.com/', 'aaaa')
        _ = client.user('8tbwn7uikpdy3gpse6fgiie5co')

        time_to_reset = client.calculate_time_to_reset()

        self.assertEqual(time_to_reset, 0)

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = {MattermostClient.HAUTHORIZATION: 'Bearer aaaa'}
        c_headers = copy.deepcopy(headers)
        payload = {}

        san_u, san_h, san_p = MattermostClient.sanitize_for_archive(url, c_headers, payload)
        headers.pop(MattermostClient.HAUTHORIZATION)

        self.assertEqual(url, san_u)
        self.assertEqual(headers, san_h)
        self.assertEqual(payload, san_p)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

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
#     Alvaro del Castillo <acs@bitergia.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import shutil
import unittest
import copy

import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.discourse import (Discourse,
                                              DiscourseCommand,
                                              DiscourseClient,
                                              MAX_RETRIES,
                                              DEFAULT_SLEEP_TIME)
from perceval.errors import BackendError, HttpClientError
from base import TestCaseBackendArchive

DISCOURSE_SERVER_URL = 'http://example.com'
DISCOURSE_TOPICS_URL = DISCOURSE_SERVER_URL + '/latest.json'
DISCOURSE_TOPIC_URL_1148 = DISCOURSE_SERVER_URL + '/t/1148.json'
DISCOURSE_TOPIC_URL_1149 = DISCOURSE_SERVER_URL + '/t/1149.json'
DISCOURSE_TOPIC_URL_1150 = DISCOURSE_SERVER_URL + '/t/1150.json'
DISCOURSE_POST_URL_1 = DISCOURSE_SERVER_URL + '/posts/21.json'
DISCOURSE_POST_URL_2 = DISCOURSE_SERVER_URL + '/posts/22.json'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestDiscourseBackend(unittest.TestCase):
    """Discourse backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        discourse = Discourse(DISCOURSE_SERVER_URL, tag='test')

        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.tag, 'test')
        self.assertIsNone(discourse.client)
        self.assertEqual(discourse.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertEqual(discourse.max_retries, MAX_RETRIES)
        self.assertTrue(discourse.ssl_verify)

        # When origin is empty or None it will be set to
        # the value in url
        discourse = Discourse(DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.tag, DISCOURSE_SERVER_URL)

        discourse = Discourse(DISCOURSE_SERVER_URL, tag='', ssl_verify=False)
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.tag, DISCOURSE_SERVER_URL)
        self.assertFalse(discourse.ssl_verify)

        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=60, max_retries=30)
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.tag, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.sleep_time, 60)
        self.assertEqual(discourse.max_retries, 30)

        discourse = Discourse(DISCOURSE_SERVER_URL, api_username='user', api_token='1234')
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.api_token, '1234')
        self.assertEqual(discourse.api_username, 'user')

    def test_missing_credentials(self):
        """Test whether an exception is thrown when `api_username` and `api_token` aren't defined together"""

        with self.assertRaises(BackendError):
            _ = Discourse(DISCOURSE_SERVER_URL, api_token='1234')

        with self.assertRaises(BackendError):
            _ = Discourse(DISCOURSE_SERVER_URL, api_username='user')

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Discourse.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Discourse.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of topics is returned"""

        requests_http = []

        bodies_topics = [read_file('data/discourse/discourse_topics.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_POST_URL_1) or \
                    uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception

            requests_http.append(httpretty.last_request())

            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # Test fetch topics
        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=0)
        topics = [topic for topic in discourse.fetch()]

        self.assertEqual(len(topics), 2)

        # Topics are returned in reverse order
        # from oldest to newest
        self.assertEqual(topics[0]['data']['id'], 1149)
        self.assertEqual(len(topics[0]['data']['post_stream']['posts']), 2)
        self.assertEqual(topics[0]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[0]['uuid'], '18068b95de1323a84c8e11dee8f46fd137f10c86')
        self.assertEqual(topics[0]['updated_on'], 1464134770.909)
        self.assertEqual(topics[0]['category'], "topic")
        self.assertEqual(topics[0]['tag'], DISCOURSE_SERVER_URL)

        self.assertEqual(topics[1]['data']['id'], 1148)
        self.assertEqual(topics[1]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[1]['uuid'], '5298e4e8383c3f73c9fa7c9599779cbe987a48e4')
        self.assertEqual(topics[1]['updated_on'], 1464144769.526)
        self.assertEqual(topics[1]['category'], "topic")
        self.assertEqual(topics[1]['tag'], DISCOURSE_SERVER_URL)

        # The next assertions check the cases whether the chunk_size is
        # less than the number of posts of a topic
        self.assertEqual(len(topics[1]['data']['post_stream']['posts']), 22)
        self.assertEqual(topics[1]['data']['post_stream']['posts'][0]['id'], 18952)
        self.assertEqual(topics[1]['data']['post_stream']['posts'][20]['id'], 2500)

        # Check requests
        expected = [
            {'page': ['0']},
            {'page': ['1']},
            {},
            {},
            {},
            {}
        ]

        self.assertEqual(len(requests_http), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(requests_http[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_with_credentials(self):
        """Test whether a list of topics is returned when the backend is initialized with credentials"""

        requests_http = []

        bodies_topics = [read_file('data/discourse/discourse_topics.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_POST_URL_1) or \
                    uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception

            requests_http.append(httpretty.last_request())

            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # Test fetch topics
        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=0, api_username='user', api_token='12345')
        topics = [topic for topic in discourse.fetch()]

        self.assertEqual(len(topics), 2)

        # Topics are returned in reverse order
        # from oldest to newest
        self.assertEqual(topics[0]['data']['id'], 1149)
        self.assertEqual(len(topics[0]['data']['post_stream']['posts']), 2)
        self.assertEqual(topics[0]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[0]['uuid'], '18068b95de1323a84c8e11dee8f46fd137f10c86')
        self.assertEqual(topics[0]['updated_on'], 1464134770.909)
        self.assertEqual(topics[0]['category'], "topic")
        self.assertEqual(topics[0]['tag'], DISCOURSE_SERVER_URL)

        self.assertEqual(topics[1]['data']['id'], 1148)
        self.assertEqual(topics[1]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[1]['uuid'], '5298e4e8383c3f73c9fa7c9599779cbe987a48e4')
        self.assertEqual(topics[1]['updated_on'], 1464144769.526)
        self.assertEqual(topics[1]['category'], "topic")
        self.assertEqual(topics[1]['tag'], DISCOURSE_SERVER_URL)

        # The next assertions check the cases whether the chunk_size is
        # less than the number of posts of a topic
        self.assertEqual(len(topics[1]['data']['post_stream']['posts']), 22)
        self.assertEqual(topics[1]['data']['post_stream']['posts'][0]['id'], 18952)
        self.assertEqual(topics[1]['data']['post_stream']['posts'][20]['id'], 2500)

        # Check requests
        expected = [
            {'page': ['0']},
            {'page': ['1']},
            {},
            {},
            {},
            {}
        ]

        self.assertEqual(len(requests_http), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(requests_http[i].querystring, expected[i])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        bodies_topics = [read_file('data/discourse/discourse_topics.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_POST_URL_1) or \
                    uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception

            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # Test fetch topics
        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=0)
        topics = [topic for topic in discourse.fetch()]

        topic = topics[0]
        self.assertEqual(discourse.metadata_id(topic['data']), topic['search_fields']['item_id'])
        self.assertEqual(topic['data']['category_id'], 111)
        self.assertEqual(topic['data']['category_id'], topic['search_fields']['category_id'])

        topic = topics[1]
        self.assertEqual(discourse.metadata_id(topic['data']), topic['search_fields']['item_id'])
        self.assertEqual(topic['data']['category_id'], 111)
        self.assertEqual(topic['data']['category_id'], topic['search_fields']['category_id'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether a list of topics is returned from a given date"""

        requests_http = []

        bodies_topics = [read_file('data/discourse/discourse_topics.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_POST_URL_1) or \
                    uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception

            requests_http.append(httpretty.last_request())

            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # On this tests only one topic will be retrieved
        from_date = datetime.datetime(2016, 5, 25, 2, 0, 0)

        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=0)
        topics = [topic for topic in discourse.fetch(from_date=from_date)]

        self.assertEqual(len(topics), 1)

        self.assertEqual(topics[0]['data']['id'], 1148)
        self.assertEqual(len(topics[0]['data']['post_stream']['posts']), 22)
        self.assertEqual(topics[0]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[0]['uuid'], '5298e4e8383c3f73c9fa7c9599779cbe987a48e4')
        self.assertEqual(topics[0]['updated_on'], 1464144769.526)
        self.assertEqual(topics[0]['category'], 'topic')
        self.assertEqual(topics[0]['tag'], DISCOURSE_SERVER_URL)

        # Check requests
        expected = [
            {'page': ['0']},
            {},
            {},
            {}
        ]

        self.assertEqual(len(requests_http), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(requests_http[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no topics are fetched"""

        body = read_file('data/discourse/discourse_topics_empty.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               body=body, status=200)

        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=0)
        topics = [topic for topic in discourse.fetch()]

        self.assertEqual(len(topics), 0)

    @httpretty.activate
    def test_fetch_pinned(self):
        """Test whether the right list of topics is returned when some topics are pinned"""

        bodies_topics = [read_file('data/discourse/discourse_topics_pinned.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_topic_1150 = read_file('data/discourse/discourse_topic_1150.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_TOPIC_URL_1150):
                body = body_topic_1150
            elif uri.startswith(DISCOURSE_POST_URL_1) or \
                    uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1150,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # On this tests two topics will be retrieved.
        # One of them was pinned but the date is in range.
        from_date = datetime.datetime(2016, 5, 25, 2, 0, 0)

        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=0)
        topics = [topic for topic in discourse.fetch(from_date=from_date)]

        self.assertEqual(len(topics), 2)

        self.assertEqual(topics[0]['data']['id'], 1148)
        self.assertEqual(len(topics[0]['data']['post_stream']['posts']), 22)
        self.assertEqual(topics[0]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[0]['uuid'], '5298e4e8383c3f73c9fa7c9599779cbe987a48e4')
        self.assertEqual(topics[0]['updated_on'], 1464144769.526)
        self.assertEqual(topics[0]['category'], 'topic')
        self.assertEqual(topics[0]['tag'], DISCOURSE_SERVER_URL)

        self.assertEqual(topics[1]['data']['id'], 1150)
        self.assertEqual(len(topics[1]['data']['post_stream']['posts']), 2)
        self.assertEqual(topics[1]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[1]['uuid'], '373b597a2a389112875c3e544f197610373a7283')
        self.assertEqual(topics[1]['updated_on'], 1464274870.809)
        self.assertEqual(topics[1]['category'], 'topic')
        self.assertEqual(topics[0]['tag'], DISCOURSE_SERVER_URL)

    @httpretty.activate
    def test_fetch_topic_last_posted_at_null(self):
        """Test whether list of topics is returned when a topic has last_posted_at null"""

        bodies_topics = [read_file('data/discourse/discourse_topics_last_posted_at_null.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            else:
                raise Exception
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # On this tests two topics will be retrieved.
        # One of them has last_posted_at with null
        discourse = Discourse(DISCOURSE_SERVER_URL, sleep_time=0)
        topics = [topic for topic in discourse.fetch(from_date=None)]

        self.assertEqual(len(topics), 1)

        self.assertEqual(topics[0]['data']['id'], 1149)
        self.assertEqual(len(topics[0]['data']['post_stream']['posts']), 2)
        self.assertEqual(topics[0]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[0]['uuid'], '18068b95de1323a84c8e11dee8f46fd137f10c86')
        self.assertEqual(topics[0]['updated_on'], 1464134770.909)
        self.assertEqual(topics[0]['category'], 'topic')
        self.assertEqual(topics[0]['tag'], DISCOURSE_SERVER_URL)


class TestDiscourseBackendArchive(TestCaseBackendArchive):
    """Discourse backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Discourse(DISCOURSE_SERVER_URL,
                                               sleep_time=0, api_token="aaaaa", api_username="user",
                                               archive=self.archive)
        self.backend_read_archive = Discourse(DISCOURSE_SERVER_URL,
                                              sleep_time=0, archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of topics is returned from archive"""

        requests_http = []

        bodies_topics = [read_file('data/discourse/discourse_topics.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_POST_URL_1) or uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception

            requests_http.append(httpretty.last_request())

            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of topics is returned from a given date from archive"""

        requests_http = []

        bodies_topics = [read_file('data/discourse/discourse_topics.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_POST_URL_1) or \
                    uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception

            requests_http.append(httpretty.last_request())

            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # On this tests only one topic will be retrieved
        from_date = datetime.datetime(2016, 5, 25, 2, 0, 0)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether the fetch from archive works when no topics are present"""

        body = read_file('data/discourse/discourse_topics_empty.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               body=body, status=200)

        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_pinned_from_archive(self):
        """Test whether the right list of topics is returned from the archive when some topics are pinned"""

        bodies_topics = [read_file('data/discourse/discourse_topics_pinned.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')
        body_topic_1150 = read_file('data/discourse/discourse_topic_1150.json')
        body_post = read_file('data/discourse/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_TOPIC_URL_1150):
                body = body_topic_1150
            elif uri.startswith(DISCOURSE_POST_URL_1) or \
                    uri.startswith(DISCOURSE_POST_URL_2):
                body = body_post
            else:
                raise Exception
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1150,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_2,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # On this tests two topics will be retrieved.
        # One of them was pinned but the date is in range.
        from_date = datetime.datetime(2016, 5, 25, 2, 0, 0)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_topic_last_posted_at_null_from_archive(self):
        """Test whether list of topics is returned from the archive when a topic has last_posted_at null"""

        bodies_topics = [read_file('data/discourse/discourse_topics_last_posted_at_null.json'),
                         read_file('data/discourse/discourse_topics_empty.json')]
        body_topic_1149 = read_file('data/discourse/discourse_topic_1149.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            else:
                raise Exception
            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1149,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])

        # On this tests two topics will be retrieved.
        # One of them has last_posted_at with null
        self._test_fetch_from_archive()


class TestDiscourseClient(unittest.TestCase):
    """Discourse API client tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """

    def test_init(self):
        """Test whether attributes are initialized"""

        client = DiscourseClient(DISCOURSE_SERVER_URL)

        self.assertEqual(client.base_url, DISCOURSE_SERVER_URL)
        self.assertIsNone(client.api_key)
        self.assertIsNone(client.api_username)
        self.assertEqual(client.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, MAX_RETRIES)
        self.assertTrue(client.ssl_verify)

        client = DiscourseClient(DISCOURSE_SERVER_URL,
                                 api_key='aaaa', api_username='user', ssl_verify=False)

        self.assertEqual(client.base_url, DISCOURSE_SERVER_URL)
        self.assertEqual(client.api_key, 'aaaa')
        self.assertEqual(client.api_username, 'user')
        self.assertEqual(client.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertEqual(client.max_retries, MAX_RETRIES)
        self.assertFalse(client.ssl_verify)

        client = DiscourseClient(DISCOURSE_SERVER_URL,
                                 api_key='aaaa', api_username='user', sleep_time=60, max_retries=30)
        self.assertEqual(client.base_url, DISCOURSE_SERVER_URL)
        self.assertEqual(client.api_key, 'aaaa')
        self.assertEqual(client.api_username, 'user')
        self.assertEqual(client.sleep_time, 60)
        self.assertEqual(client.max_retries, 30)

    def test_missing_credentials(self):
        """Test whether an exception is thrown when `api_key` and `api_username` aren't defined together"""

        with self.assertRaises(HttpClientError):
            _ = DiscourseClient(DISCOURSE_SERVER_URL, api_key='1234')

        with self.assertRaises(HttpClientError):
            _ = DiscourseClient(DISCOURSE_SERVER_URL, api_username='user')

    @httpretty.activate
    def test_topics_page(self):
        """Test topics_page API call"""

        # Set up a mock HTTP server
        body = read_file('data/discourse/discourse_topics.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               body=body, status=200)

        # Call API without args
        client = DiscourseClient(DISCOURSE_SERVER_URL, api_key='aaaa', api_username='user', sleep_time=0)
        response = client.topics_page()

        self.assertEqual(response, body)

        # Check request params
        expected = {}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/latest.json')
        self.assertDictEqual(req.querystring, expected)

        # Call API selecting a page
        response = client.topics_page(page=1)

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'page': ['1']
        }

        req = httpretty.last_request()

        self.assertDictEqual(req.querystring, expected)
        self.assertEqual(req.headers[DiscourseClient.HKEY], 'aaaa')
        self.assertEqual(req.headers[DiscourseClient.HUSER], 'user')

    @httpretty.activate
    def test_topic(self):
        """Test topic API call"""

        # Set up a mock HTTP server
        body = read_file('data/discourse/discourse_topic_1148.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               body=body, status=200)

        # Call API
        client = DiscourseClient(DISCOURSE_SERVER_URL, api_key='aaaa', api_username='user', sleep_time=0)
        response = client.topic(1148)

        self.assertEqual(response, body)

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/t/1148.json')
        self.assertDictEqual(req.querystring, {})
        self.assertEqual(req.headers[DiscourseClient.HKEY], 'aaaa')
        self.assertEqual(req.headers[DiscourseClient.HUSER], 'user')

    @httpretty.activate
    def test_post(self):
        """Test post API call"""

        # Set up a mock HTTP server
        body = read_file('data/discourse/discourse_post.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               body=body, status=200)

        # Call API
        client = DiscourseClient(DISCOURSE_SERVER_URL, api_key='aaaa', api_username='user', sleep_time=0)
        response = client.post(21)

        self.assertEqual(response, body)

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/posts/21.json')
        self.assertDictEqual(req.querystring, {})
        self.assertEqual(req.headers[DiscourseClient.HKEY], 'aaaa')
        self.assertEqual(req.headers[DiscourseClient.HUSER], 'user')

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = {
            DiscourseClient.HUSER: 'user',
            DiscourseClient.HKEY: 'aaaa'
        }
        c_headers = copy.deepcopy(headers)
        payload = {}

        san_u, san_h, san_p = DiscourseClient.sanitize_for_archive(url, c_headers, payload)
        headers.pop(DiscourseClient.HUSER)
        headers.pop(DiscourseClient.HKEY)

        self.assertEqual(url, san_u)
        self.assertEqual(headers, san_h)
        self.assertEqual(payload, san_p)


class TestDiscourseCommand(unittest.TestCase):
    """Tests for DiscourseCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Discourse"""

        self.assertIs(DiscourseCommand.BACKEND, Discourse)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = DiscourseCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Discourse)

        args = ['--tag', 'test', '--no-archive',
                '--from-date', '1970-01-01',
                DISCOURSE_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, DISCOURSE_SERVER_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertIsNone(parsed_args.api_token)
        self.assertIsNone(parsed_args.api_username)
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertEqual(parsed_args.max_retries, MAX_RETRIES)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['--tag', 'test', '--no-archive',
                '--from-date', '1970-01-01',
                '--max-retries', '60',
                '--sleep-time', '30',
                DISCOURSE_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, DISCOURSE_SERVER_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertIsNone(parsed_args.api_token)
        self.assertIsNone(parsed_args.api_username)
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.sleep_time, 30)
        self.assertEqual(parsed_args.max_retries, 60)

        args = ['--tag', 'test', '--no-archive',
                '--from-date', '1970-01-01',
                '--max-retries', '60',
                '--sleep-time', '30',
                '--api-token', 'aaaa',
                '--no-ssl-verify',
                '--api-username', 'user',
                DISCOURSE_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, DISCOURSE_SERVER_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.api_token, 'aaaa')
        self.assertEqual(parsed_args.api_username, 'user')
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.sleep_time, 30)
        self.assertEqual(parsed_args.max_retries, 60)
        self.assertFalse(parsed_args.ssl_verify)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

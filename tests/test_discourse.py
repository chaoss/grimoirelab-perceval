#!/usr/bin/env python3
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import datetime
import shutil
import sys
import tempfile
import unittest

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
from perceval.backends.core.discourse import (Discourse,
                                              DiscourseCommand,
                                              DiscourseClient)


DISCOURSE_SERVER_URL = 'http://example.com'
DISCOURSE_TOPICS_URL = DISCOURSE_SERVER_URL + '/latest.json'
DISCOURSE_TOPIC_URL_1148 = DISCOURSE_SERVER_URL + '/t/1148.json'
DISCOURSE_TOPIC_URL_1149 = DISCOURSE_SERVER_URL + '/t/1149.json'
DISCOURSE_TOPIC_URL_1150 = DISCOURSE_SERVER_URL + '/t/1150.json'
DISCOURSE_POST_URL_1 = DISCOURSE_SERVER_URL + '/posts/21.json'
DISCOURSE_POST_URL_2 = DISCOURSE_SERVER_URL + '/posts/22.json'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
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
        self.assertIsInstance(discourse.client, DiscourseClient)

        # When origin is empty or None it will be set to
        # the value in url
        discourse = Discourse(DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.tag, DISCOURSE_SERVER_URL)

        discourse = Discourse(DISCOURSE_SERVER_URL, tag='')
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.tag, DISCOURSE_SERVER_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Discourse.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Discourse.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of topics is returned"""

        requests_http = []

        bodies_topics = [read_file('data/discourse_topics.json'),
                         read_file('data/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse_topic_1149.json')
        body_post = read_file('data/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif (uri.startswith(DISCOURSE_POST_URL_1) or
                  uri.startswith(DISCOURSE_POST_URL_2)):
                body = body_post
            else:
                raise

            requests_http.append(httpretty.last_request())

            return (200, headers, body)

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
        discourse = Discourse(DISCOURSE_SERVER_URL)
        topics = [topic for topic in discourse.fetch()]

        self.assertEqual(len(topics), 2)

        # Topics are returned in reverse order
        # from oldest to newest
        self.assertEqual(topics[0]['data']['id'], 1149)
        self.assertEqual(len(topics[0]['data']['post_stream']['posts']), 2)
        self.assertEqual(topics[0]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[0]['uuid'], '18068b95de1323a84c8e11dee8f46fd137f10c86')
        self.assertEqual(topics[0]['updated_on'], 1464134770.909)
        self.assertEqual(topics[0]['category'], 'topic')
        self.assertEqual(topics[0]['tag'], DISCOURSE_SERVER_URL)

        self.assertEqual(topics[1]['data']['id'], 1148)
        self.assertEqual(topics[1]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(topics[1]['uuid'], '5298e4e8383c3f73c9fa7c9599779cbe987a48e4')
        self.assertEqual(topics[1]['updated_on'], 1464144769.526)
        self.assertEqual(topics[1]['category'], 'topic')
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
    def test_fetch_from_date(self):
        """Test whether a list of topics is returned from a given date"""

        requests_http = []

        bodies_topics = [read_file('data/discourse_topics.json'),
                         read_file('data/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse_topic_1149.json')
        body_post = read_file('data/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif (uri.startswith(DISCOURSE_POST_URL_1) or
                  uri.startswith(DISCOURSE_POST_URL_2)):
                body = body_post
            else:
                raise

            requests_http.append(httpretty.last_request())

            return (200, headers, body)

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

        discourse = Discourse(DISCOURSE_SERVER_URL)
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

        body = read_file('data/discourse_topics_empty.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               body=body, status=200)

        discourse = Discourse(DISCOURSE_SERVER_URL)
        topics = [topic for topic in discourse.fetch()]

        self.assertEqual(len(topics), 0)

    @httpretty.activate
    def test_fetch_pinned(self):
        """Test whether the right list of topics is returned when some topics are pinned"""

        bodies_topics = [read_file('data/discourse_topics_pinned.json'),
                         read_file('data/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse_topic_1149.json')
        body_topic_1150 = read_file('data/discourse_topic_1150.json')
        body_post = read_file('data/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif uri.startswith(DISCOURSE_TOPIC_URL_1150):
                body = body_topic_1150
            elif (uri.startswith(DISCOURSE_POST_URL_1) or
                  uri.startswith(DISCOURSE_POST_URL_2)):
                body = body_post
            else:
                raise
            return (200, headers, body)

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

        discourse = Discourse(DISCOURSE_SERVER_URL)
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


class TestDiscourseBackendCache(unittest.TestCase):
    """Discourse backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        requests_http = []

        bodies_topics = [read_file('data/discourse_topics.json'),
                         read_file('data/discourse_topics_empty.json')]
        body_topic_1148 = read_file('data/discourse_topic_1148.json')
        body_topic_1149 = read_file('data/discourse_topic_1149.json')
        body_post = read_file('data/discourse_post.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_TOPICS_URL):
                body = bodies_topics.pop(0)
            elif uri.startswith(DISCOURSE_TOPIC_URL_1148):
                body = body_topic_1148
            elif uri.startswith(DISCOURSE_TOPIC_URL_1149):
                body = body_topic_1149
            elif (uri.startswith(DISCOURSE_POST_URL_1) or
                  uri.startswith(DISCOURSE_POST_URL_2)):
                body = body_post
            else:
                raise

            requests_http.append(httpretty.last_request())

            return (200, headers, body)

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

        # First, we fetch the topics from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        discourse = Discourse(DISCOURSE_SERVER_URL, cache=cache)

        topics = [topic for topic in discourse.fetch()]
        self.assertEqual(len(requests_http), 6)

        # Now, we get the topics from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_topics = [topic for topic in discourse.fetch_from_cache()]
        self.assertEqual(len(cached_topics), len(topics))

        self.assertEqual(len(cached_topics), 2)

        # Topics are returned in reverse order
        # from oldest to newest
        self.assertEqual(cached_topics[0]['data']['id'], 1149)
        self.assertEqual(len(cached_topics[0]['data']['post_stream']['posts']), 2)
        self.assertEqual(cached_topics[0]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(cached_topics[0]['uuid'], '18068b95de1323a84c8e11dee8f46fd137f10c86')
        self.assertEqual(cached_topics[0]['updated_on'], 1464134770.909)
        self.assertEqual(cached_topics[0]['category'], 'topic')
        self.assertEqual(cached_topics[0]['origin'], DISCOURSE_SERVER_URL)

        self.assertEqual(cached_topics[1]['data']['id'], 1148)
        self.assertEqual(cached_topics[1]['origin'], DISCOURSE_SERVER_URL)
        self.assertEqual(cached_topics[1]['uuid'], '5298e4e8383c3f73c9fa7c9599779cbe987a48e4')
        self.assertEqual(cached_topics[1]['updated_on'], 1464144769.526)
        self.assertEqual(cached_topics[1]['category'], 'topic')
        self.assertEqual(cached_topics[1]['origin'], DISCOURSE_SERVER_URL)

        # The next assertions check the cases whether the chunk_size is
        # less than the number of posts of a topic
        self.assertEqual(len(cached_topics[1]['data']['post_stream']['posts']), 22)
        self.assertEqual(cached_topics[1]['data']['post_stream']['posts'][0]['id'], 18952)
        self.assertEqual(cached_topics[1]['data']['post_stream']['posts'][20]['id'], 2500)

        # No more requests were sent
        self.assertEqual(len(requests_http), 6)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any topics returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        discourse = Discourse(DISCOURSE_SERVER_URL, cache=cache)
        cached_topics = [topic for topic in discourse.fetch_from_cache()]
        self.assertEqual(len(cached_topics), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        discourse = Discourse(DISCOURSE_SERVER_URL)

        with self.assertRaises(CacheError):
            _ = [topic for topic in discourse.fetch_from_cache()]


class TestDiscourseClient(unittest.TestCase):
    """Discourse API client tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """

    def test_init(self):
        """Test whether attributes are initializated"""

        client = DiscourseClient(DISCOURSE_SERVER_URL,
                                 api_key='aaaa')

        self.assertEqual(client.url, DISCOURSE_SERVER_URL)
        self.assertEqual(client.api_key, 'aaaa')

    @httpretty.activate
    def test_topics_page(self):
        """Test topics_page API call"""

        # Set up a mock HTTP server
        body = read_file('data/discourse_topics.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPICS_URL,
                               body=body, status=200)

        # Call API without args
        client = DiscourseClient(DISCOURSE_SERVER_URL, api_key='aaaa')
        response = client.topics_page()

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'api_key': ['aaaa']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/latest.json')
        self.assertDictEqual(req.querystring, expected)

        # Call API selecting a page
        response = client.topics_page(page=1)

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'api_key': ['aaaa'],
            'page': ['1']
        }

        req = httpretty.last_request()

        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_topic(self):
        """Test topic API call"""

        # Set up a mock HTTP server
        body = read_file('data/discourse_topic_1148.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_TOPIC_URL_1148,
                               body=body, status=200)

        # Call API
        client = DiscourseClient(DISCOURSE_SERVER_URL, api_key='aaaa')
        response = client.topic(1148)

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'api_key': ['aaaa'],
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/t/1148.json')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_post(self):
        """Test post API call"""

        # Set up a mock HTTP server
        body = read_file('data/discourse_post.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POST_URL_1,
                               body=body, status=200)

        # Call API
        client = DiscourseClient(DISCOURSE_SERVER_URL, api_key='aaaa')
        response = client.post(21)

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'api_key': ['aaaa'],
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/posts/21.json')
        self.assertDictEqual(req.querystring, expected)


class TestDiscourseCommand(unittest.TestCase):
    """Tests for DiscourseCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Discourse"""

        self.assertIs(DiscourseCommand.BACKEND, Discourse)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = DiscourseCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)

        args = ['--tag', 'test', '--no-cache',
                '--from-date', '1970-01-01',
                DISCOURSE_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, DISCOURSE_SERVER_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.no_cache, True)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

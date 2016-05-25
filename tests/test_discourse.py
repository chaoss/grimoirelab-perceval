#!/usr/bin/env python3
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
#     Alvaro del Castillo <acs@bitergia.com>
#

import argparse
import datetime
import json
import shutil
import sys
import tempfile
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.discourse import Discourse, DiscourseCommand, DiscourseClient


DISCOURSE_SERVER_URL = 'http://talk.manageiq.org'
DISCOURSE_POSTS_URL = DISCOURSE_SERVER_URL+'/latest.json'
DISCOURSE_POSTS_TOPIC_URL_1 = DISCOURSE_SERVER_URL+"/t/1448.json"
DISCOURSE_POSTS_TOPIC_URL_2 = DISCOURSE_SERVER_URL+"/t/1449.json"

def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content

class TestDiscourseBackend(unittest.TestCase):
    """Discourse backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        discourse = Discourse(DISCOURSE_SERVER_URL, origin='test')

        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, 'test')
        self.assertIsInstance(discourse.client, DiscourseClient)

        # When origin is empty or None it will be set to
        # the value in url
        discourse = Discourse(DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)

        discourse = Discourse(DISCOURSE_SERVER_URL, origin='')
        self.assertEqual(discourse.url, DISCOURSE_SERVER_URL)
        self.assertEqual(discourse.origin, DISCOURSE_SERVER_URL)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of posts is returned"""

        requests_http = []

        bodies_topics = read_file('data/discourse_topics.json')
        bodies_posts = read_file('data/discourse_posts.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_POSTS_URL):
                body = bodies_topics
            elif uri.startswith(DISCOURSE_POSTS_TOPIC_URL_1) or \
                 uri.startswith(DISCOURSE_POSTS_TOPIC_URL_2):
                body = bodies_posts
            else:
                body = ''

            requests_http.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_1,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_2,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])

        # Test fetch posts from topics list
        discourse = Discourse(DISCOURSE_SERVER_URL)
        posts = [build for build in discourse.fetch()]
        self.assertEqual(len(posts), 8)

        with open("data/discourse_post.json") as post_json:
            first_post = json.load(post_json)
            self.assertDictEqual(posts[0]['data'], first_post['data'])

        # Test metadata
        expected = [('0ec6a9ed2432fa98ed351cb984dbb84fb858ead1', 1464023039.465),
                    ('d7745c7f40b99ee657494cf1ef6d5332c9eed00a', 1464085132.433),
                    ('c32181d10f978985b2af5525e6e90fdc29de577e', 1464108572.57),
                    ('44d050dffbec6d505897d748eef4beb8d5ba5d17', 1464144769.526)]

        for x in range(len(expected)):
            post = posts[x]
            self.assertEqual(post['origin'], 'http://talk.manageiq.org')
            self.assertEqual(post['uuid'], expected[x][0])
            self.assertEqual(post['updated_on'], expected[x][1])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether a list of posts is returned from a given date"""

        requests_http = []

        bodies_topics = read_file('data/discourse_topics.json')
        bodies_posts = read_file('data/discourse_posts.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_POSTS_URL):
                body = bodies_topics
            elif uri.startswith(DISCOURSE_POSTS_TOPIC_URL_1) or \
                 uri.startswith(DISCOURSE_POSTS_TOPIC_URL_2):
                body = bodies_posts
            else:
                body = ''

            requests_http.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_1,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_2,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])

        from_date = datetime.datetime(2016, 5, 24)

        # Test fetch posts from topics list
        discourse = Discourse(DISCOURSE_SERVER_URL)
        posts = [build for build in discourse.fetch(from_date=from_date)]
        self.assertEqual(len(posts), 6)

        # Test metadata
        expected = [('d7745c7f40b99ee657494cf1ef6d5332c9eed00a', 1464085132.433),
                    ('c32181d10f978985b2af5525e6e90fdc29de577e', 1464108572.57),
                    ('44d050dffbec6d505897d748eef4beb8d5ba5d17', 1464144769.526)]

        for x in range(len(expected)):
            post = posts[x]
            self.assertEqual(post['origin'], 'http://talk.manageiq.org')
            self.assertEqual(post['uuid'], expected[x][0])
            self.assertEqual(post['updated_on'], expected[x][1])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no topics are fetched"""

        body = '{"topic_list": {"topics": []}}'
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_URL,
                               body=body, status=200)

        discourse = Discourse(DISCOURSE_SERVER_URL)
        posts = [build for build in discourse.fetch()]

        self.assertEqual(len(posts), 0)

class TestDiscourseBackendCache(unittest.TestCase):
    """Discourse backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        bodies_topics = read_file('data/discourse_topics.json', mode='rb')
        bodies_posts_job = read_file('data/discourse_posts.json')

        def request_callback(method, uri, headers):
            if uri.startswith(DISCOURSE_POSTS_URL):
                body = bodies_topics
            elif uri.startswith(DISCOURSE_POSTS_TOPIC_URL_1) or \
                 uri.startswith(DISCOURSE_POSTS_TOPIC_URL_2):
                body = bodies_posts_job
            else:
                body = ''

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_1,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_2,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])

        # First, we fetch the posts from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        discourse = Discourse(DISCOURSE_SERVER_URL, cache=cache)

        posts = [build for build in discourse.fetch()]

        # Now, we get the posts from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_posts = [build for build in discourse.fetch_from_cache()]
        self.assertEqual(len(cached_posts), len(posts))

        with open("data/discourse_post.json") as post_json:
            first_build = json.load(post_json)
            self.assertDictEqual(cached_posts[0]['data'], first_build['data'])

    def test_fetch_from_empty_cache(self):
        """Test if there are not any posts returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        discourse = Discourse(DISCOURSE_SERVER_URL, cache=cache)
        cached_posts = [build for build in discourse.fetch_from_cache()]
        self.assertEqual(len(cached_posts), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        discourse = Discourse(DISCOURSE_SERVER_URL)

        with self.assertRaises(CacheError):
            _ = [build for build in discourse.fetch_from_cache()]


class TestDiscourseCommand(unittest.TestCase):

    @httpretty.activate
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--origin', 'test', DISCOURSE_SERVER_URL]

        cmd = DiscourseCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, DISCOURSE_SERVER_URL)
        self.assertEqual(cmd.parsed_args.origin, 'test')
        self.assertIsInstance(cmd.backend, Discourse)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = DiscourseCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestDiscourseClient(unittest.TestCase):
    """Discourse API client tests

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""
        client = DiscourseClient(DISCOURSE_SERVER_URL, token=None, max_topics=None)

    @httpretty.activate
    def test_get_topics(self):
        """Test get_topics API call"""

        # Set up a mock HTTP server
        body = read_file('data/discourse_topics.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_URL,
                               body=body, status=200)

        client = DiscourseClient(DISCOURSE_SERVER_URL, token=None, max_topics=None)
        response = client.get_topics_id_list()

        topic_ids = [topic_id for topic_id in response]
        self.assertEqual(len(topic_ids), 2)

        expected = [1448, 1449]

        for x in range(len(expected)):
            self.assertEqual(topic_ids[x], expected[x])

    @httpretty.activate
    def test_get_posts(self, token=None, max_topics=None):
        """Test get_posts API call"""

        # Set up a mock HTTP server
        body_topics = read_file('data/discourse_topics.json')
        body_posts = read_file('data/discourse_posts.json')
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_URL,
                               body=body_topics, status=200)
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_1,
                               body=body_posts, status=200)
        httpretty.register_uri(httpretty.GET,
                               DISCOURSE_POSTS_TOPIC_URL_2,
                               body=body_posts, status=200)


        client = DiscourseClient(DISCOURSE_SERVER_URL, token=None, max_topics=None)
        response = client.get_posts()
        posts = [post for post in response]
        self.assertEqual(len(posts), 8)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

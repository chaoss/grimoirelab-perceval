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
import json
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

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.core.rss import (RSS,
                                            RSSCommand,
                                            RSSClient)


RSS_FEED_URL = 'http://example.com/rss'

requests_http = []

def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content

class TestRSSBackend(unittest.TestCase):
    """RSS backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        rss = RSS(RSS_FEED_URL, tag='test')

        self.assertEqual(rss.url, RSS_FEED_URL)
        self.assertEqual(rss.origin, RSS_FEED_URL)
        self.assertEqual(rss.tag, 'test')
        self.assertIsInstance(rss.client, RSSClient)

        # When tag is empty or None it will be set to
        # the value in url
        rss = RSS(RSS_FEED_URL)
        self.assertEqual(rss.url, RSS_FEED_URL)
        self.assertEqual(rss.origin, RSS_FEED_URL)
        self.assertEqual(rss.tag, RSS_FEED_URL)

        rss = RSS(RSS_FEED_URL, tag='')
        self.assertEqual(rss.url, RSS_FEED_URL)
        self.assertEqual(rss.origin, RSS_FEED_URL)
        self.assertEqual(rss.tag, RSS_FEED_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(RSS.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(RSS.has_resuming(), False)

    def __configure_http_server(self):
        bodies_entries_job = read_file('data/rss_entries.xml')

        def request_callback(method, uri, headers):
            if uri.startswith(RSS_FEED_URL):
                body = bodies_entries_job
            else:
                body = ''

            requests_http.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               RSS_FEED_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of entries is returned"""

        self.__configure_http_server()

        # Test fetch entries from feed
        rss = RSS(RSS_FEED_URL)
        entries = [item for item in rss.fetch()]
        self.assertEqual(len(entries), 30)

        # Test metadata
        expected = [('98572defb3a652afbfdfe96517edefb88a22dcfa', 1481044620.0),
                    ('e3b0d7463fca0c47d82debc3ddc37d8906f77548', 1480955040.0),
                    ('28bca39353ff0825f53b157b69da319e2f49ab4d', 1480886040.0)]

        for x in range(len(expected)):
            item = entries[x]
            self.assertEqual(item['origin'], 'http://example.com/rss')
            self.assertEqual(item['uuid'], expected[x][0])
            self.assertEqual(item['updated_on'], expected[x][1])
            self.assertEqual(item['category'], 'item')
            self.assertEqual(item['tag'], 'http://example.com/rss')

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no entries are fetched"""

        body = """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <rss version="2.0">
        </rss>
        """
        httpretty.register_uri(httpretty.GET,
                               RSS_FEED_URL,
                               body=body, status=200)

        rss = RSS(RSS_FEED_URL)
        entries = [item for item in rss.fetch()]

        self.assertEqual(len(entries), 0)


class TestRSSBackendCache(unittest.TestCase):
    """RSS backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        bodies_entries = read_file('data/rss_entries.xml')

        def request_callback(method, uri, headers):
            if uri.startswith(RSS_FEED_URL):
                body = bodies_entries
            else:
                body = ''

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               RSS_FEED_URL,
                               responses=[
                                    httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                               ])

        # First, we fetch the entries from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        rss = RSS(RSS_FEED_URL, cache=cache)

        entries = [item for item in rss.fetch()]

        # Now, we get the entries from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_entries = [item for item in rss.fetch_from_cache()]
        self.assertEqual(len(cached_entries), len(entries))


    def test_fetch_from_empty_cache(self):
        """Test if there are not any entries returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        rss = RSS(RSS_FEED_URL, cache=cache)
        cached_entries = [item for item in rss.fetch_from_cache()]
        self.assertEqual(len(cached_entries), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        rss = RSS(RSS_FEED_URL)

        with self.assertRaises(CacheError):
            _ = [item for item in rss.fetch_from_cache()]


class TestRSSCommand(unittest.TestCase):

    @httpretty.activate
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--tag', 'test', RSS_FEED_URL]

        cmd = RSSCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, RSS_FEED_URL)
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, RSS)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = RSSCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestRSSClient(unittest.TestCase):
    """RSS API client tests

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""
        client = RSSClient(RSS_FEED_URL)

    @httpretty.activate
    def test_get_entries(self):
        """Test get_entries API call"""

        # Set up a mock HTTP server
        body = read_file('data/rss_entries.xml')
        httpretty.register_uri(httpretty.GET,
                               RSS_FEED_URL,
                               body=body, status=200)

        client = RSSClient(RSS_FEED_URL)
        response = client.get_entries()

        self.assertEqual(response, body)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

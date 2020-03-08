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
#     Alvaro del Castillo <acs@bitergia.com>
#     Santiago Dueñas <sduenas@bitergia.com>
#     Stephan Barth <stephan.barth@gmail.com>
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import httpretty
import os
import pkg_resources
import unittest

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.rss import RSS, RSSCommand, RSSClient
from base import TestCaseBackendArchive


RSS_FEED_URL = 'http://example.com/rss'

requests_http = []


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def configure_http_server():
    bodies_entries_job = read_file('data/rss/rss_entries.xml')

    http_requests = []

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()

        if uri.startswith(RSS_FEED_URL):
            body = bodies_entries_job
        else:
            body = ''

        requests_http.append(httpretty.last_request())

        http_requests.append(last_request)

        return (200, headers, body)

    httpretty.register_uri(httpretty.GET,
                           RSS_FEED_URL,
                           responses=[
                               httpretty.Response(body=request_callback)
                               for _ in range(2)
                           ])

    return http_requests


class TestRSSBackend(unittest.TestCase):
    """RSS backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        rss = RSS(RSS_FEED_URL, tag='test')

        self.assertEqual(rss.url, RSS_FEED_URL)
        self.assertEqual(rss.origin, RSS_FEED_URL)
        self.assertEqual(rss.tag, 'test')
        self.assertIsNone(rss.client)
        self.assertTrue(rss.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        rss = RSS(RSS_FEED_URL, ssl_verify=False)
        self.assertEqual(rss.url, RSS_FEED_URL)
        self.assertEqual(rss.origin, RSS_FEED_URL)
        self.assertEqual(rss.tag, RSS_FEED_URL)
        self.assertFalse(rss.ssl_verify)

        rss = RSS(RSS_FEED_URL, tag='')
        self.assertEqual(rss.url, RSS_FEED_URL)
        self.assertEqual(rss.origin, RSS_FEED_URL)
        self.assertEqual(rss.tag, RSS_FEED_URL)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(RSS.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns False when has_resuming is called"""

        self.assertEqual(RSS.has_resuming(), False)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of entries is returned"""

        http_requests = configure_http_server()

        # Test fetch entries from feed
        rss = RSS(RSS_FEED_URL)
        entries = [entry for entry in rss.fetch()]
        self.assertEqual(len(entries), 30)
        self.assertEqual(len(http_requests), 1)

        # Test metadata
        expected = [('98572defb3a652afbfdfe96517edefb88a22dcfa', 1481044620.0,
                     'Connect 2016 Developer Workshop'),
                    ('e3b0d7463fca0c47d82debc3ddc37d8906f77548', 1480955040.0,
                     'Create a URL Shortener with Node.js and Couchbase using N1QL'),
                    ('28bca39353ff0825f53b157b69da319e2f49ab4d', 1480886040.0,
                     'ELT processing with Couchbase and N1QL')]

        for x in range(len(expected)):
            entry = entries[x]
            self.assertEqual(entry['origin'], 'http://example.com/rss')
            self.assertEqual(entry['uuid'], expected[x][0])
            self.assertEqual(entry['updated_on'], expected[x][1])
            self.assertEqual(entry['category'], 'entry')
            self.assertEqual(entry['tag'], 'http://example.com/rss')
            self.assertEqual(entry['data']['title'], expected[x][2])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        configure_http_server()

        rss = RSS(RSS_FEED_URL)
        entries = [entry for entry in rss.fetch()]

        for entry in entries:
            self.assertEqual(rss.metadata_id(entry['data']), entry['search_fields']['item_id'])

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
        entries = [entry for entry in rss.fetch()]

        self.assertEqual(len(entries), 0)

    @httpretty.activate
    def test_parse(self):
        """Test whether the parser works """

        xml_feed = read_file('data/rss/rss_entries.xml')
        json_feed = RSS.parse_feed(xml_feed)['entries']
        entry = json_feed[0]

        """ rss version="2.0"
        <entry><title>Connect 2016 Developer Workshop</title>
        <link>http://blog.couchbase.com/2016/november/connect-2016-developer-workshop</link>
        <description>&lt;p&gt;For the first day  ... </description>
        <pubDate>Tue, 06 Dec 2016 17:17:00 +0000</pubDate>
        <author>Matthew Groves</author>
        <avatar>/content/gallery/speakers/speakersCouchbase/mebricks.jpg/mebricks.jpg/hippogallery:original</avatar>
        </entry>
        """

        self.assertEqual(entry['title'], 'Connect 2016 Developer Workshop')
        self.assertEqual(entry['published'], 'Tue, 06 Dec 2016 17:17:00 +0000')
        self.assertEqual(entry['avatar'],
                         '/content/gallery/speakers/speakersCouchbase/mebricks.jpg/mebricks.jpg/hippogallery:original')
        self.assertEqual(entry['link'], 'http://blog.couchbase.com/2016/november/connect-2016-developer-workshop')
        self.assertEqual(len(entry['summary']), 410)
        self.assertEqual(entry['author'], 'Matthew Groves')


class TestRSSBackendArchive(TestCaseBackendArchive):
    """RSS backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = RSS(RSS_FEED_URL, archive=self.archive)
        self.backend_read_archive = RSS(RSS_FEED_URL, archive=self.archive)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of entries is returned from archive"""

        configure_http_server()
        self._test_fetch_from_archive()

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether the method fetch from archive works when no entries are present"""

        body = """
            <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <rss version="2.0">
            </rss>
            """
        httpretty.register_uri(httpretty.GET,
                               RSS_FEED_URL,
                               body=body, status=200)

        self._test_fetch_from_archive()


class TestRSSCommand(unittest.TestCase):
    """RSSCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is RSS"""

        self.assertIs(RSSCommand.BACKEND, RSS)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = RSSCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, RSS)

        args = ['--tag', 'test',
                '--no-archive',
                RSS_FEED_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, RSS_FEED_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['--tag', 'test',
                '--no-archive',
                '--no-ssl-verify',
                RSS_FEED_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, RSS_FEED_URL)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertFalse(parsed_args.ssl_verify)


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
        body = read_file('data/rss/rss_entries.xml')
        httpretty.register_uri(httpretty.GET,
                               RSS_FEED_URL,
                               body=body, status=200)

        client = RSSClient(RSS_FEED_URL)
        response = client.get_entries()

        self.assertEqual(response, body)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

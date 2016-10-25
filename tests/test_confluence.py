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
import datetime
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
from perceval.backends.confluence import (Confluence,
                                          ConfluenceClient,
                                          ConfluenceCommand)


CONFLUENCE_URL = 'http://example.com'
CONFLUENCE_API_URL = CONFLUENCE_URL + '/rest/api'
CONFLUENCE_CONTENTS_URL = CONFLUENCE_API_URL + '/content/search'
CONFLUENCE_HISTORICAL_CONTENT_1 = CONFLUENCE_API_URL + '/content/1'
CONFLUENCE_HISTORICAL_CONTENT_2 = CONFLUENCE_API_URL + '/content/2'
CONFLUENCE_HISTORICAL_CONTENT_ATT = CONFLUENCE_API_URL + '/content/att1'


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    body_contents = read_file('data/confluence_contents.json', 'rb')
    body_contents_next = read_file('data/confluence_contents_next.json', 'rb')
    body_contents_empty = read_file('data/confluence_contents_empty.json', 'rb')
    body_content_1_v1 = read_file('data/confluence_content_1_v1.json', 'rb')
    body_content_1_v2 = read_file('data/confluence_content_1_v2.json', 'rb')
    body_content_2 = read_file('data/confluence_content_2_v1.json', 'rb')
    body_content_att = read_file('data/confluence_content_att_v1.json', 'rb')

    def request_callback(method, uri, headers):
        if uri.startswith(CONFLUENCE_CONTENTS_URL):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)

            if 'start' in params and params['start'] == ['2']:
                body = body_contents_next
            elif params['cql'][0].startswith("lastModified>='2016-07-08 00:00'"):
                body = body_contents_empty
            else:
                body = body_contents
        elif uri.startswith(CONFLUENCE_HISTORICAL_CONTENT_1):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)

            if params['version'] == ['1']:
                body = body_content_1_v1
            else:
                body = body_content_1_v2
        elif uri.startswith(CONFLUENCE_HISTORICAL_CONTENT_2):
            body = body_content_2
        elif uri.startswith(CONFLUENCE_HISTORICAL_CONTENT_ATT):
            body = body_content_att
        else:
            raise

        http_requests.append(httpretty.last_request())

        return (200, headers, body)

    httpretty.register_uri(httpretty.GET,
                           CONFLUENCE_CONTENTS_URL,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           CONFLUENCE_HISTORICAL_CONTENT_1,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           CONFLUENCE_HISTORICAL_CONTENT_2,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           CONFLUENCE_HISTORICAL_CONTENT_ATT,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])

    return http_requests


class TestConfluenceBackend(unittest.TestCase):
    """Confluence backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        confluence = Confluence(CONFLUENCE_URL, tag='test')

        self.assertEqual(confluence.url, CONFLUENCE_URL)
        self.assertEqual(confluence.origin, CONFLUENCE_URL)
        self.assertEqual(confluence.tag, 'test')
        self.assertIsInstance(confluence.client, ConfluenceClient)

        # When tag is empty or None it will be set to
        # the value in url
        confluence = Confluence(CONFLUENCE_URL)
        self.assertEqual(confluence.url, CONFLUENCE_URL)
        self.assertEqual(confluence.origin, CONFLUENCE_URL)
        self.assertEqual(confluence.tag, CONFLUENCE_URL)

        confluence = Confluence(CONFLUENCE_URL, tag='')
        self.assertEqual(confluence.url, CONFLUENCE_URL)
        self.assertEqual(confluence.origin, CONFLUENCE_URL)
        self.assertEqual(confluence.tag, CONFLUENCE_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Confluence.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Confluence.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test it it fetches and parses a list of contents"""

        http_requests = setup_http_server()

        confluence = Confluence(CONFLUENCE_URL)
        hcs = [hc for hc in confluence.fetch()]

        expected = [('1', 1, '5b8bf26bfd906214ec82f5a682649e8f6fe87984', 1465589121.0),
                    ('1', 2, '94b8015bcb52fca1155ecee14153c8634856f1bc', 1466107110.0),
                    ('2', 1, 'eccc9b6c961f8753ee37fb8d077be80b9bea0976', 1467402626.0),
                    ('att1', 1, 'ff21bba0b1968adcec2588e94ff42782330174dd', 1467831550.0)]

        self.assertEqual(len(hcs), len(expected))

        for x in range(len(hcs)):
            hc = hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['category'], 'historical content')
            self.assertEqual(hc['tag'], CONFLUENCE_URL)

        # Check requests
        expected = [
                    {
                     'cql' : ["lastModified>='1970-01-01 00:00' order by lastModified"],
                     'limit' : ['200']
                    },
                    {
                     'cql' : ["lastModified>='1970-01-01 00:00' order by lastModified"],
                     'start' : ['2'],
                     'limit' : ['2'] # Hardcoded in JSON dataset
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['2']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    }
                   ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test if a list of contents is returned from a given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 6, 16, 0, 0, 0)

        confluence = Confluence(CONFLUENCE_URL)
        hcs = [hc for hc in confluence.fetch(from_date=from_date)]

        # On this test case the first version of content #1
        # will not be returned becasue this version was
        # created before the given date
        expected = [('1', 2, '94b8015bcb52fca1155ecee14153c8634856f1bc', 1466107110.0),
                    ('2', 1, 'eccc9b6c961f8753ee37fb8d077be80b9bea0976', 1467402626.0),
                    ('att1', 1, 'ff21bba0b1968adcec2588e94ff42782330174dd', 1467831550.0)]

        self.assertEqual(len(hcs), len(expected))

        for x in range(len(hcs)):
            hc = hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['category'], 'historical content')
            self.assertEqual(hc['tag'], CONFLUENCE_URL)

        # Check requests
        expected = [
                    {
                     'cql' : ["lastModified>='2016-06-16 00:00' order by lastModified"],
                     'limit' : ['200']
                    },
                    { # Hardcoded in JSON dataset
                     'cql' : ["lastModified>='1970-01-01 00:00' order by lastModified"],
                     'start' : ['2'],
                     'limit' : ['2']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['2']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    }
                   ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_removed_content(self):
        """Test if the method works when a content is not found"""

        http_requests = setup_http_server()

        # Set server to return a 404 error
        httpretty.register_uri(httpretty.GET,
                               CONFLUENCE_HISTORICAL_CONTENT_1,
                               status=404, body="Mock 404 error")

        confluence = Confluence(CONFLUENCE_URL)
        hcs = [hc for hc in confluence.fetch()]

        expected = [('2', 1, 'eccc9b6c961f8753ee37fb8d077be80b9bea0976', 1467402626.0),
                    ('att1', 1, 'ff21bba0b1968adcec2588e94ff42782330174dd', 1467831550.0)]

        self.assertEqual(len(hcs), len(expected))

        for x in range(len(hcs)):
            hc = hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['category'], 'historical content')
            self.assertEqual(hc['tag'], CONFLUENCE_URL)

        # Check requests
        expected = [
                    {
                     'cql' : ["lastModified>='1970-01-01 00:00' order by lastModified"],
                     'limit' : ['200']
                    },
                    {
                     'cql' : ["lastModified>='1970-01-01 00:00' order by lastModified"],
                     'start' : ['2'],
                     'limit' : ['2'] # Hardcoded in JSON dataset
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    },
                    {
                     'expand' : ['body.storage,history,version'],
                     'status' : ['historical'],
                     'version' : ['1']
                    }
                   ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returnerd when there are no contents"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 7, 8, 0, 0, 0)

        confluence = Confluence(CONFLUENCE_URL)
        hcs = [hc for hc in confluence.fetch(from_date=from_date)]

        self.assertEqual(len(hcs), 0)

        # Check requests
        expected = {
                    'cql' : ["lastModified>='2016-07-08 00:00' order by lastModified"],
                    'limit' : ['200']
                   }

        self.assertEqual(len(http_requests), 1)
        self.assertDictEqual(http_requests[0].querystring, expected)

    def test_parse_contents_summary(self):
        """Test if it parses a contents summary stream"""

        raw_contents = read_file('data/confluence_contents.json')

        contents = Confluence.parse_contents_summary(raw_contents)
        results = [content for content in contents]

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], '1')
        self.assertEqual(results[1]['id'], '2')

        # Parse a file without results
        raw_contents = read_file('data/confluence_contents_empty.json')

        contents = Confluence.parse_contents_summary(raw_contents)
        results = [content for content in contents]

        self.assertEqual(len(results), 0)

    def test_parse_historical_content(self):
        """Test if it parses a historical content stream"""

        raw_hc = read_file('data/confluence_content_1_v1.json')
        hc = Confluence.parse_historical_content(raw_hc)

        self.assertEqual(hc['id'], '1')
        self.assertEqual(hc['history']['latest'], False)
        self.assertEqual(hc['version']['number'], 1)
        self.assertEqual(hc['version']['when'], '2016-06-10T20:05:21.000Z')


class TestConfluenceBackendCache(unittest.TestCase):
    """Confluence backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        http_requests = setup_http_server()

        # First, we fetch the contents from the server,
        # storing them in a cache
        cache = Cache(self.tmp_path)
        confluence = Confluence(CONFLUENCE_URL, cache=cache)

        hcs = [hc for hc in confluence.fetch()]
        self.assertEqual(len(http_requests), 6)

        # Now, we get the contents from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_hcs = [hc for hc in confluence.fetch_from_cache()]
        self.assertEqual(len(cached_hcs), len(hcs))

        expected = [('1', 1, '5b8bf26bfd906214ec82f5a682649e8f6fe87984', 1465589121.0),
                    ('1', 2, '94b8015bcb52fca1155ecee14153c8634856f1bc', 1466107110.0),
                    ('2', 1, 'eccc9b6c961f8753ee37fb8d077be80b9bea0976', 1467402626.0),
                    ('att1', 1, 'ff21bba0b1968adcec2588e94ff42782330174dd', 1467831550.0)]

        self.assertEqual(len(cached_hcs), len(expected))

        for x in range(len(cached_hcs)):
            hc = cached_hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['category'], 'historical content')
            self.assertEqual(hc['tag'], CONFLUENCE_URL)

        # No more requests were sent
        self.assertEqual(len(http_requests), 6)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any content returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        confluence = Confluence(CONFLUENCE_URL, cache=cache)
        cached_hcs = [hc for hc in confluence.fetch_from_cache()]
        self.assertEqual(len(cached_hcs), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        confluence = Confluence(CONFLUENCE_URL)

        with self.assertRaises(CacheError):
            _ = [hc for hc in confluence.fetch_from_cache()]


class TestConfluenceCommand(unittest.TestCase):
    """Tests for ConfluenceCommand class"""

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['http://example.com',
                '--tag', 'test']

        cmd = ConfluenceCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, 'http://example.com')
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, Confluence)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = ConfluenceCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestConfluenceClient(unittest.TestCase):
    """ConfluenceClient unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization of parameters"""

        client = ConfluenceClient(CONFLUENCE_URL)
        self.assertEqual(client.base_url, CONFLUENCE_URL)

    @httpretty.activate
    def test_contents(self):
        """Test contents API call"""

        http_requests = setup_http_server()

        client = ConfluenceClient(CONFLUENCE_URL)
        dt = datetime.datetime(2016, 7, 8, 0, 0, 0)

        pages = client.contents(from_date=dt, offset=10, max_contents=2)
        pages = [p for p in pages]

        self.assertEqual(len(pages), 1)

        expected = {
                     'cql' : ["lastModified>='2016-07-08 00:00' order by lastModified"],
                     'start' : ['10'],
                     'limit' : ['2']
                   }

        self.assertEqual(len(http_requests), 1)
        self.assertDictEqual(http_requests[0].querystring, expected)

    @httpretty.activate
    def test_contents_pagination(self):
        """Test contents API call with pagination"""

        http_requests = setup_http_server()

        client = ConfluenceClient(CONFLUENCE_URL)

        pages = client.contents(max_contents=2)
        pages = [p for p in pages]

        self.assertEqual(len(pages), 2)

        expected = [{
                     'cql' : ["lastModified>='1970-01-01 00:00' order by lastModified"],
                     'limit' : ['2']
                    },
                    {
                     'cql' : ["lastModified>='1970-01-01 00:00' order by lastModified"],
                     'start' : ['2'],
                     'limit' : ['2']
                    }]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_historical_content(self):
        """Test historical content API call"""

        http_requests = setup_http_server()

        client = ConfluenceClient(CONFLUENCE_URL)
        hc = client.historical_content(content_id='1', version='2')

        expected = {
                    'expand' : ['body.storage,history,version'],
                    'status' : ['historical'],
                    'version' : ['2']
                   }

        self.assertIsInstance(hc, str)
        self.assertDictEqual(http_requests[0].querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

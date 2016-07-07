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

import datetime
import sys
import unittest
import urllib

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.confluence import ConfluenceClient


CONFLUENCE_URL = 'http://example.com'
CONFLUENCE_API_URL = CONFLUENCE_URL + '/rest/api'
CONFLUENCE_CONTENTS_URL = CONFLUENCE_API_URL + '/content/search'
CONFLUENCE_HISTORICAL_CONTENT_1_V1 = CONFLUENCE_API_URL + '/content/1'


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

    def request_callback(method, uri, headers):
        if uri.startswith(CONFLUENCE_CONTENTS_URL):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)

            if 'start' in params and params['start'] == ['2']:
                body = body_contents_next
            elif params['cql'][0].startswith("lastModified>='2016-07-07 00:00'"):
                body = body_contents_empty
            else:
                body = body_contents
        else:
            body = body_content_1_v1

        http_requests.append(httpretty.last_request())

        return (200, headers, body)

    httpretty.register_uri(httpretty.GET,
                           CONFLUENCE_CONTENTS_URL,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])
    httpretty.register_uri(httpretty.GET,
                           CONFLUENCE_HISTORICAL_CONTENT_1_V1,
                           responses=[
                                httpretty.Response(body=request_callback)
                           ])

    return http_requests


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
        dt = datetime.datetime(2016, 7, 7, 0, 0, 0)

        pages = client.contents(from_date=dt, offset=10, max_contents=2)
        pages = [p for p in pages]

        self.assertEqual(len(pages), 1)

        expected = {
                     'cql' : ["lastModified>='2016-07-07 00:00' order by lastModified"],
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

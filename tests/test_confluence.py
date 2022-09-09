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
#     Valerio Cosentino <valcos@bitergia.com>
#     Miguel Ángel Fernández <mafesan@bitergia.com>
#     Maurizio Pillitu <maoo@apache.org>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import shutil
import unittest
import urllib

import httpretty
import requests

from perceval.backend import BackendCommandArgumentParser
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.confluence import (Confluence,
                                               ConfluenceClient,
                                               ConfluenceCommand,
                                               SEARCH_ANCESTOR_IDS,
                                               SEARCH_CONTENT_ID,
                                               SEARCH_CONTENT_VERSION_NUMBER)
from base import TestCaseBackendArchive


CONFLUENCE_URL = 'http://example.com'
CONFLUENCE_API_URL = CONFLUENCE_URL + '/rest/api'
CONFLUENCE_CONTENTS_URL = CONFLUENCE_API_URL + '/content/search'
CONFLUENCE_HISTORICAL_CONTENT_1 = CONFLUENCE_API_URL + '/content/1'
CONFLUENCE_HISTORICAL_CONTENT_2 = CONFLUENCE_API_URL + '/content/2'
CONFLUENCE_HISTORICAL_CONTENT_3 = CONFLUENCE_API_URL + '/content/3'
CONFLUENCE_HISTORICAL_CONTENT_ATT = CONFLUENCE_API_URL + '/content/att1'
CONFLUENCE_CONTENTS_SPACE_URL = CONFLUENCE_URL + ''

STATUS_CODE_SUCCESS = 200
STATUS_CODE_NOT_HANDLED = 503


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server(not_handle_status_code=False):
    """Setup a mock HTTP server"""

    http_requests = []

    body_contents = read_file('data/confluence/confluence_contents.json', 'rb')
    body_contents_next = read_file('data/confluence/confluence_contents_next.json', 'rb')
    body_contents_empty = read_file('data/confluence/confluence_contents_empty.json', 'rb')
    body_content_1_v1 = read_file('data/confluence/confluence_content_1_v1.json', 'rb')
    body_content_1_v2 = read_file('data/confluence/confluence_content_1_v2.json', 'rb')
    body_content_1_v3 = read_file('data/confluence/confluence_content_1_v3.json', 'rb')
    body_content_2 = read_file('data/confluence/confluence_content_2_v1.json', 'rb')
    body_content_3 = read_file('data/confluence/confluence_content_3.json', 'rb')
    body_content_att = read_file('data/confluence/confluence_content_att_v1.json', 'rb')
    body_content_space = read_file('data/confluence/confluence_content_space.json', 'rb')

    def request_callback(method, uri, headers):

        status_code = STATUS_CODE_SUCCESS

        if uri.startswith(CONFLUENCE_CONTENTS_URL):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)

            if 'start' in params and params['start'] == ['2']:
                body = body_contents_next
            elif 'start' in params and params['start'] == ['3']:
                body = body_contents_empty
            elif params['cql'][0].startswith("lastModified>='2016-07-08 00:00'"):
                body = body_contents_empty
            elif params['cql'][0].startswith("space in"):
                body = body_content_space
            else:
                body = body_contents
        elif uri.startswith(CONFLUENCE_HISTORICAL_CONTENT_1):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)

            if params['version'] == ['1']:
                body = body_content_1_v1
            elif params['version'] == ['2']:
                body = body_content_1_v2
            else:
                body = body_content_1_v3
        elif uri.startswith(CONFLUENCE_HISTORICAL_CONTENT_2):
            body = body_content_2

            if not_handle_status_code:
                status_code = STATUS_CODE_NOT_HANDLED
        elif uri.startswith(CONFLUENCE_HISTORICAL_CONTENT_3):
            body = body_content_3

        elif uri.startswith(CONFLUENCE_HISTORICAL_CONTENT_ATT):
            body = body_content_att
        else:
            raise Exception

        http_requests.append(httpretty.last_request())

        return status_code, headers, body

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
                           CONFLUENCE_HISTORICAL_CONTENT_3,
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
        self.assertIsNone(confluence.client)
        self.assertTrue(confluence.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in url
        confluence = Confluence(CONFLUENCE_URL)
        self.assertEqual(confluence.url, CONFLUENCE_URL)
        self.assertEqual(confluence.origin, CONFLUENCE_URL)
        self.assertEqual(confluence.tag, CONFLUENCE_URL)

        confluence = Confluence(CONFLUENCE_URL, tag='', ssl_verify=False)
        self.assertEqual(confluence.url, CONFLUENCE_URL)
        self.assertEqual(confluence.origin, CONFLUENCE_URL)
        self.assertEqual(confluence.tag, CONFLUENCE_URL)
        self.assertFalse(confluence.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Confluence.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Confluence.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test it it fetches and parses a list of contents"""

        http_requests = setup_http_server()

        confluence = Confluence(CONFLUENCE_URL, max_contents=2)

        hcs = [hc for hc in confluence.fetch()]

        expected = [
            ('1', 1, '5b8bf26bfd906214ec82f5a682649e8f6fe87984',
             1465589121.0, 'http://example.com/display/meetings/TSC'),
            ('1', 2, '94b8015bcb52fca1155ecee14153c8634856f1bc',
             1466107110.0, 'http://example.com/display/meetings/TSC'),
            ('2', 1, 'eccc9b6c961f8753ee37fb8d077be80b9bea0976',
             1467402626.0, 'http://example.com/display/fuel/Colorado+Release+Status'),
            ('att1', 1, 'ff21bba0b1968adcec2588e94ff42782330174dd',
             1467831550.0, 'http://example.com/pages/viewpage.action?pageId=131079&preview=%2F131079%2F131085%2Fstep05-04.png')
        ]

        self.assertEqual(len(hcs), len(expected))

        for x in range(len(hcs)):
            hc = hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['data']['content_url'], expected[x][4])
            self.assertEqual(hc['category'], "historical content")
            self.assertEqual(hc['tag'], CONFLUENCE_URL)

        # Check requests
        expected = [
            {
                'cql': ["lastModified>='1970-01-01 00:00' order by lastModified"],
                'limit': ['200'],
                'expand': ['ancestors']
            },
            {
                'cql': ["lastModified>='1970-01-01 00:00' order by lastModified"],
                'start': ['2'],
                'limit': ['2']  # Hardcoded in JSON dataset
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['2']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['3']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_spaces(self):
        """Test it fetches and parses a list of contents in specific spaces"""

        http_requests = setup_http_server()

        confluence = Confluence(CONFLUENCE_URL, spaces=["TEST"])

        hcs = [hc for hc in confluence.fetch()]

        expected = [
            ('3', 3, '93cd38039f3987594d46508396317734131823c1',
             1610466397.336, 'http://example.com/display/TEST/PERCEVAL'),
        ]

        self.assertEqual(len(hcs), len(expected))

        for x in range(len(hcs)):
            hc = hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['data']['content_url'], expected[x][4])
            self.assertEqual(hc['category'], "historical content")
            self.assertEqual(hc['tag'], CONFLUENCE_URL)
            self.assertEqual(hc['data']['_expandable']['space'], '/rest/api/space/TEST')

        # Check requests
        expected = [
            {
                'cql': ["space in (TEST) and lastModified>='1970-01-01 00:00' order by lastModified"],
                'limit': ['200'],
                'expand': ['ancestors']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        setup_http_server()

        confluence = Confluence(CONFLUENCE_URL)

        hcs = [hc for hc in confluence.fetch()]

        hc = hcs[0]
        self.assertEqual(confluence.metadata_id(hc['data']), hc['search_fields']['item_id'])
        self.assertListEqual(hc['search_fields'][SEARCH_ANCESTOR_IDS], ['128548867', '167848895', '128548921'])
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_ID], '1')
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_VERSION_NUMBER], 1)

        hc = hcs[1]
        self.assertEqual(confluence.metadata_id(hc['data']), hc['search_fields']['item_id'])
        self.assertListEqual(hc['search_fields'][SEARCH_ANCESTOR_IDS], ['128548867', '167848895', '128548921'])
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_ID], '1')
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_VERSION_NUMBER], 2)

        hc = hcs[2]
        self.assertEqual(confluence.metadata_id(hc['data']), hc['search_fields']['item_id'])
        self.assertListEqual(hc['search_fields'][SEARCH_ANCESTOR_IDS], [])
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_ID], '2')
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_VERSION_NUMBER], 1)

        hc = hcs[3]
        self.assertEqual(confluence.metadata_id(hc['data']), hc['search_fields']['item_id'])
        self.assertListEqual(hc['search_fields'][SEARCH_ANCESTOR_IDS], [])
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_ID], 'att1')
        self.assertEqual(hc['search_fields'][SEARCH_CONTENT_VERSION_NUMBER], 1)

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
        expected = [
            ('1', 2, '94b8015bcb52fca1155ecee14153c8634856f1bc',
             1466107110.0, 'http://example.com/display/meetings/TSC'),
            ('2', 1, 'eccc9b6c961f8753ee37fb8d077be80b9bea0976',
             1467402626.0, 'http://example.com/display/fuel/Colorado+Release+Status'),
            ('att1', 1, 'ff21bba0b1968adcec2588e94ff42782330174dd',
             1467831550.0, 'http://example.com/pages/viewpage.action?pageId=131079&preview=%2F131079%2F131085%2Fstep05-04.png')
        ]

        self.assertEqual(len(hcs), len(expected))

        for x in range(len(hcs)):
            hc = hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['data']['content_url'], expected[x][4])
            self.assertEqual(hc['category'], 'historical content')
            self.assertEqual(hc['tag'], CONFLUENCE_URL)

        # Check requests
        expected = [
            {
                'cql': ["lastModified>='2016-06-16 00:00' order by lastModified"],
                'limit': ['200'],
                'expand': ['ancestors']
            },
            {
                # Hardcoded in JSON dataset
                'cql': ["lastModified>='1970-01-01 00:00' order by lastModified"],
                'start': ['2'],
                'limit': ['2']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['2']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['3']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_status_code_not_handled(self):
        """Test whether an exception is thrown when the API returns a HTTP status code
        different from 404 and 500 when fetching historical contents.
        """
        setup_http_server(not_handle_status_code=True)

        confluence = Confluence(CONFLUENCE_URL)

        with self.assertRaises(requests.exceptions.HTTPError):
            _ = [hc for hc in confluence.fetch(from_date=None)]

    @httpretty.activate
    def test_fetch_removed_content(self):
        """Test if the method works when a content is not found"""

        http_requests = setup_http_server()

        # Set server to return a 404 error
        httpretty.register_uri(httpretty.GET,
                               CONFLUENCE_HISTORICAL_CONTENT_1,
                               status=404, body="Mock 404 error")

        confluence = Confluence(CONFLUENCE_URL)
        hcs = [hc for hc in confluence.fetch(from_date=None)]

        expected = [
            ('2', 1, 'eccc9b6c961f8753ee37fb8d077be80b9bea0976',
             1467402626.0, 'http://example.com/display/fuel/Colorado+Release+Status'),
            ('att1', 1, 'ff21bba0b1968adcec2588e94ff42782330174dd',
             1467831550.0, 'http://example.com/pages/viewpage.action?pageId=131079&preview=%2F131079%2F131085%2Fstep05-04.png')
        ]

        self.assertEqual(len(hcs), len(expected))

        for x in range(len(hcs)):
            hc = hcs[x]
            self.assertEqual(hc['data']['id'], expected[x][0])
            self.assertEqual(hc['data']['version']['number'], expected[x][1])
            self.assertEqual(hc['uuid'], expected[x][2])
            self.assertEqual(hc['origin'], CONFLUENCE_URL)
            self.assertEqual(hc['updated_on'], expected[x][3])
            self.assertEqual(hc['data']['content_url'], expected[x][4])
            self.assertEqual(hc['category'], 'historical content')
            self.assertEqual(hc['tag'], CONFLUENCE_URL)

        # Check requests
        expected = [
            {
                'cql': ["lastModified>='1970-01-01 00:00' order by lastModified"],
                'limit': ['200'],
                'expand': ['ancestors']
            },
            {
                'cql': ["lastModified>='1970-01-01 00:00' order by lastModified"],
                'start': ['2'],
                'limit': ['2']  # Hardcoded in JSON dataset
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            },
            {
                'expand': ['body.storage,history,version'],
                'status': ['historical'],
                'version': ['1']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returned when there are no contents"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 7, 8, 0, 0, 0)

        confluence = Confluence(CONFLUENCE_URL)
        hcs = [hc for hc in confluence.fetch(from_date=from_date)]

        self.assertEqual(len(hcs), 0)

        # Check requests
        expected = {
            'cql': ["lastModified>='2016-07-08 00:00' order by lastModified"],
            'limit': ['200'],
            'expand': ['ancestors']
        }

        self.assertEqual(len(http_requests), 1)
        self.assertDictEqual(http_requests[0].querystring, expected)

    def test_parse_contents_summary(self):
        """Test if it parses a contents summary stream"""

        raw_contents = read_file('data/confluence/confluence_contents.json')

        contents = Confluence.parse_contents_summary(raw_contents)
        results = [content for content in contents]

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], '1')
        self.assertEqual(results[1]['id'], '2')

        # Parse a file without results
        raw_contents = read_file('data/confluence/confluence_contents_empty.json')

        contents = Confluence.parse_contents_summary(raw_contents)
        results = [content for content in contents]

        self.assertEqual(len(results), 0)

    def test_parse_historical_content(self):
        """Test if it parses a historical content stream"""

        raw_hc = read_file('data/confluence/confluence_content_1_v1.json')
        hc = Confluence.parse_historical_content(raw_hc)

        self.assertEqual(hc['id'], '1')
        self.assertEqual(hc['history']['latest'], False)
        self.assertEqual(hc['version']['number'], 1)
        self.assertEqual(hc['version']['when'], '2016-06-10T20:05:21.000Z')


class TestConfluenceBackendArchive(TestCaseBackendArchive):
    """Confluence backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Confluence(CONFLUENCE_URL, archive=self.archive)
        self.backend_read_archive = Confluence(CONFLUENCE_URL, archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test it it fetches and parses a list of contents from archive"""

        setup_http_server()
        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test if a list of contents is returned from a given date from archive"""

        setup_http_server()

        from_date = datetime.datetime(2016, 6, 16, 0, 0, 0)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_removed_content_from_archive(self):
        """Test if the fetch method from archive works when a content is not found"""

        setup_http_server()

        # Set server to return a 404 error
        httpretty.register_uri(httpretty.GET,
                               CONFLUENCE_HISTORICAL_CONTENT_1,
                               status=404, body="Mock 404 error")

        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test if nothing is returned from the archive when there are no contents"""

        setup_http_server()

        from_date = datetime.datetime(2016, 7, 8, 0, 0, 0)
        self._test_fetch_from_archive(from_date=from_date)


class TestConfluenceCommand(unittest.TestCase):
    """Tests for ConfluenceCommand class"""

    def test_backend_class(self):
        """Test if the backend class is Confluence"""

        self.assertIs(ConfluenceCommand.BACKEND, Confluence)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = ConfluenceCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Confluence)

        args = ['http://example.com',
                '--tag', 'test', '--no-archive',
                '--from-date', '1970-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertIsNone(parsed_args.spaces)
        self.assertEqual(parsed_args.max_contents, 200)

        args = ['http://example.com',
                '--tag', 'test', '--no-ssl-verify',
                '--from-date', '1970-01-01',
                '--spaces', 'TEST', 'PERCEVAL',
                '--max-contents', '2']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.url, 'http://example.com')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)
        self.assertEqual(parsed_args.spaces, ['TEST', 'PERCEVAL'])
        self.assertEqual(parsed_args.max_contents, 2)


class TestConfluenceClient(unittest.TestCase):
    """ConfluenceClient unit tests.

    These tests do not check the body of the response, only if the call
    was well formed and if a response was obtained.
    """
    def test_init(self):
        """Test initialization of parameters"""

        client = ConfluenceClient(CONFLUENCE_URL)
        self.assertEqual(client.base_url, CONFLUENCE_URL)
        self.assertTrue(client.ssl_verify)

        client = ConfluenceClient(CONFLUENCE_URL, ssl_verify=False)
        self.assertEqual(client.base_url, CONFLUENCE_URL)
        self.assertFalse(client.ssl_verify)

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
            'cql': ["lastModified>='2016-07-08 00:00' order by lastModified"],
            'start': ['10'],
            'limit': ['2'],
            'expand': ['ancestors']
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

        expected = [
            {
                'cql': ["lastModified>='1970-01-01 00:00' order by lastModified"],
                'limit': ['2'],
                'expand': ['ancestors']
            },
            {
                'cql': ["lastModified>='1970-01-01 00:00' order by lastModified"],
                'start': ['2'],
                'limit': ['2']
            }
        ]

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
            'expand': ['body.storage,history,version'],
            'status': ['historical'],
            'version': ['2']
        }

        self.assertIsInstance(hc, str)
        self.assertDictEqual(http_requests[0].querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

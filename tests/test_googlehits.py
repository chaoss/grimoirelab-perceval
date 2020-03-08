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
#     Valerio Cosentino <valcos@bitergia.com>
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import datetime
import os
import requests
import shutil
import unittest
import unittest.mock

import dateutil
import httpretty
import pkg_resources

pkg_resources.declare_namespace('perceval.backends')

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.googlehits import (GoogleHits,
                                               GoogleHitsClient,
                                               GoogleHitsCommand,
                                               GOOGLE_SEARCH_URL,
                                               CATEGORY_HITS,
                                               MAX_RETRIES,
                                               DEFAULT_SLEEP_TIME)

from perceval.errors import BackendError
from base import TestCaseBackendArchive


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


def setup_http_server(status=200, no_hits=False):
    """Setup a mock HTTP server"""

    body_no_hits = read_file('data/googlehits/hits_zero', 'r')
    body_bitergia = read_file('data/googlehits/hits_bitergia', 'r')
    body_grimoirelab = read_file('data/googlehits/hits_bitergia_grimoirelab', 'r')

    if no_hits:
        httpretty.register_uri(httpretty.GET,
                               GOOGLE_SEARCH_URL,
                               params={'q': 'bitergia'},
                               body=body_no_hits, status=status)
        return

    httpretty.register_uri(httpretty.GET,
                           GOOGLE_SEARCH_URL,
                           params={'q': 'bitergia'},
                           body=body_bitergia, status=status)

    httpretty.register_uri(httpretty.GET,
                           GOOGLE_SEARCH_URL,
                           params={'q': 'bitergia+grimoirelab'},
                           body=body_grimoirelab, status=status)


class TestGoogleHitsBackend(unittest.TestCase):
    """GoogleHits backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        backend = GoogleHits(['bitergia'], tag='test')

        self.assertEqual(backend.keywords, ['bitergia'])
        self.assertEqual(backend.origin, GOOGLE_SEARCH_URL)
        self.assertEqual(backend.tag, 'test')
        self.assertIsNone(backend.client)
        self.assertEqual(backend.max_retries, MAX_RETRIES)
        self.assertEqual(backend.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertTrue(backend.ssl_verify)

        # When tag is empty or None it will be set to the value in
        backend = GoogleHits(['bitergia', 'grimoirelab'], ssl_verify=False)
        self.assertEqual(backend.keywords, ['bitergia', 'grimoirelab'])
        self.assertEqual(backend.origin, GOOGLE_SEARCH_URL)
        self.assertEqual(backend.tag, GOOGLE_SEARCH_URL)
        self.assertFalse(backend.ssl_verify)

        backend = GoogleHits(['bitergia', 'grimoirelab'], tag='')
        self.assertEqual(backend.keywords, ['bitergia', 'grimoirelab'])
        self.assertEqual(backend.origin, GOOGLE_SEARCH_URL)
        self.assertEqual(backend.tag, GOOGLE_SEARCH_URL)

        backend = GoogleHits(['bitergia', 'grimoirelab'], tag='', max_retries=1, sleep_time=100)
        self.assertEqual(backend.keywords, ['bitergia', 'grimoirelab'])
        self.assertEqual(backend.origin, GOOGLE_SEARCH_URL)
        self.assertEqual(backend.tag, GOOGLE_SEARCH_URL)
        self.assertEqual(backend.max_retries, 1)
        self.assertEqual(backend.sleep_time, 100)

        with self.assertRaises(BackendError):
            _ = GoogleHits([''], tag='')

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(GoogleHits.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(GoogleHits.has_resuming(), True)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.googlehits.datetime_utcnow')
    def test_fetch(self, mock_utcnow):
        """Test whether it fetches data from the Google Search API"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server()

        backend = GoogleHits(['bitergia'])
        items = [item for item in backend.fetch()]

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['data']['fetched_on'], 1483228800.0)
        self.assertEqual(item['data']['id'], '18e8f9809f9c539bfe0ac5ad2724323873931825')
        self.assertEqual(item['data']['keywords'], ['bitergia'])
        self.assertEqual(item['uuid'], '119b60909d6560e2d22a579404c30c98f5cdc33d')
        self.assertEqual(item['origin'], 'https://www.google.com/search')
        self.assertEqual(item['updated_on'], 1483228800.0)
        self.assertEqual(item['category'], CATEGORY_HITS)
        self.assertEqual(item['tag'], 'https://www.google.com/search')

        backend = GoogleHits(['bitergia', 'grimoirelab'])
        items = [item for item in backend.fetch()]

        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertEqual(item['data']['fetched_on'], 1483228800.0)
        self.assertEqual(item['data']['id'], '2aaa5f3ab512ca6c451cb3c21c77da3d4510f75c')
        self.assertEqual(item['data']['keywords'], ['bitergia', 'grimoirelab'])
        self.assertEqual(item['uuid'], '3a83dfa224891986d091e708a2afd165df59576b')
        self.assertEqual(item['origin'], 'https://www.google.com/search')
        self.assertEqual(item['updated_on'], 1483228800.0)
        self.assertEqual(item['category'], CATEGORY_HITS)
        self.assertEqual(item['tag'], 'https://www.google.com/search')

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.googlehits.datetime_utcnow')
    def test_search_fields(self, mock_utcnow):
        """Test whether the search_fields is properly set"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server()

        backend = GoogleHits(['bitergia'])
        items = [item for item in backend.fetch()]

        item = items[0]
        self.assertEqual(backend.metadata_id(item['data']), item['search_fields']['item_id'])
        self.assertListEqual(item['data']['keywords'], ['bitergia'])
        self.assertListEqual(item['data']['keywords'], item['search_fields']['keywords'])

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.googlehits.datetime_utcnow')
    def test_fetch_no_hits(self, mock_utcnow):
        """Test whether it handles queries which have no hits"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server(no_hits=True)

        backend = GoogleHits(['bitergia'])

        with self.assertLogs() as cm:
            items = [item for item in backend.fetch()]
            self.assertEqual(cm.output[-2], "WARNING:perceval.backends.core.googlehits:No hits for ['bitergia']")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['data']['fetched_on'], 1483228800.0)
        self.assertEqual(item['data']['id'], '18e8f9809f9c539bfe0ac5ad2724323873931825')
        self.assertEqual(item['data']['hits'], 0)
        self.assertEqual(item['data']['keywords'], ['bitergia'])
        self.assertEqual(item['uuid'], '119b60909d6560e2d22a579404c30c98f5cdc33d')
        self.assertEqual(item['origin'], 'https://www.google.com/search')
        self.assertEqual(item['updated_on'], 1483228800.0)
        self.assertEqual(item['category'], CATEGORY_HITS)
        self.assertEqual(item['tag'], 'https://www.google.com/search')


class TestGoogleHitsBackendArchive(TestCaseBackendArchive):
    """GoogleHits backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = GoogleHits(['bitergia'], archive=self.archive)
        self.backend_read_archive = GoogleHits(['bitergia'], archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.googlehits.datetime_utcnow')
    def test_fetch_from_archive(self, mock_utcnow):
        """Test whether it fetches data from an archive"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server()
        self._test_fetch_from_archive()

    @httpretty.activate
    @unittest.mock.patch('perceval.backends.core.googlehits.datetime_utcnow')
    def test_fetch_from_archive_no_hits(self, mock_utcnow):
        """Test whether it fetches data with zero hits from an archive"""

        mock_utcnow.return_value = datetime.datetime(2017, 1, 1,
                                                     tzinfo=dateutil.tz.tzutc())
        setup_http_server(no_hits=True)

        with self.assertLogs() as cm:
            self._test_fetch_from_archive()
            self.assertEqual(cm.output[-2], "WARNING:perceval.backends.core.googlehits:No hits for ['bitergia']")


class TestGoogleHitsClient(unittest.TestCase):
    """GoogleHits API client tests"""

    @httpretty.activate
    def test_hits(self):
        """Test hits API call"""

        # Set up a mock HTTP server
        setup_http_server()

        # Call API
        client = GoogleHitsClient()
        client.hits(['bitergia'])

        last_request = httpretty.last_request()
        self.assertEqual(last_request.path, '/search?q=bitergia')
        self.assertDictEqual(last_request.querystring, {'q': ['bitergia']})

        client.hits(['bitergia', 'grimoirelab'])

        last_request = httpretty.last_request()
        self.assertEqual(last_request.path, '/search?q=bitergia+grimoirelab')
        self.assertDictEqual(last_request.querystring, {'q': ['bitergia grimoirelab']})

    @httpretty.activate
    def test_retries(self):
        """Test hits API call"""

        # Set up a mock HTTP server
        setup_http_server(status=429)

        # Call API
        client = GoogleHitsClient(max_retries=1, sleep_time=0.1)

        with self.assertRaises(requests.exceptions.RetryError):
            _ = [hit for hit in client.hits(['bitergia'])]


class TestGoogleHitsCommand(unittest.TestCase):
    """Tests for GoogleHits class"""

    def test_backend_class(self):
        """Test if the backend class is GoogleHits"""

        self.assertIs(GoogleHitsCommand.BACKEND, GoogleHits)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = GoogleHitsCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, GoogleHits)
        args = ['', '--no-archive']

        parsed_args = parser.parse(*args)
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.keywords, [''])
        self.assertEqual(parsed_args.max_retries, MAX_RETRIES)
        self.assertEqual(parsed_args.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertTrue(parsed_args.ssl_verify)

        args = ['bitergia', '--no-archive', '--no-ssl-verify']

        parsed_args = parser.parse(*args)
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.keywords, ['bitergia'])
        self.assertEqual(parsed_args.max_retries, MAX_RETRIES)
        self.assertEqual(parsed_args.sleep_time, DEFAULT_SLEEP_TIME)
        self.assertFalse(parsed_args.ssl_verify)

        args = ['bitergia', 'grimoirelab', '--no-archive', '--max-retries', '1', '--sleep-time', '100']

        parsed_args = parser.parse(*args)
        self.assertTrue(parsed_args.no_archive)
        self.assertEqual(parsed_args.keywords, ['bitergia', 'grimoirelab'])
        self.assertEqual(parsed_args.max_retries, 1)
        self.assertEqual(parsed_args.sleep_time, 100)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

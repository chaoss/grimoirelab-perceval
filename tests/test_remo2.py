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
import re
import shutil
import sys
import tempfile
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.remo2 import (
    ReMo, ReMoCommand, ReMoClient, MOZILLA_REPS_URL, REMO_DEFAULT_OFFSET)


MOZILLA_REPS_SERVER_URL = 'http://example.com'
MOZILLA_REPS_API = MOZILLA_REPS_SERVER_URL + '/api/beta'

MOZILLA_REPS_KINDS = ['events', 'activities', 'users']

def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class HTTPServer():

    requests_http = []  # requests done to the server

    @classmethod
    def routes(cls, empty=False):
        """Configure in http the routes to be served"""

        mozilla_bodies = {}  # dict with all the bodies to be returned by kind
        for kind in MOZILLA_REPS_KINDS:
            mozilla_bodies[kind] = {}
            # First two pages for each kind to test pagination
            mozilla_bodies[kind]['1'] = read_file('data/remo_'+kind+'_page_1_2.json')
            mozilla_bodies[kind]['2'] = read_file('data/remo_'+kind+'_page_2_2.json')
            # A sample item per each kind
            mozilla_bodies[kind]['item'] = read_file('data/remo_'+kind+'.json')

        if empty:
            for kind in MOZILLA_REPS_KINDS:
                mozilla_bodies[kind]['1'] = read_file('data/remo_'+kind+'_page_empty.json')

        def request_callback(method, uri, headers):
            body = ''
            if 'page' in uri:
                # Page with item list query
                page = uri.split("page=")[1].split("&")[0]
                for kind in MOZILLA_REPS_KINDS:
                    if kind in uri:
                        body = mozilla_bodies[kind][page]
                        break
            else:
                # Specific item. Always return the same for each kind.
                for kind in MOZILLA_REPS_KINDS:
                    if kind in uri:
                        body = mozilla_bodies[kind]['item']
                        break

            HTTPServer.requests_http.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               re.compile(MOZILLA_REPS_API+".*"),
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])


class TestReMoBackend(unittest.TestCase):
    """ReMo backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        remo = ReMo(MOZILLA_REPS_SERVER_URL, origin='test')

        self.assertEqual(remo.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.origin, 'test')
        self.assertIsInstance(remo.client, ReMoClient)

        # When origin is empty or None it will be set to
        # the value in url
        remo = ReMo(MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.origin, MOZILLA_REPS_SERVER_URL)

        remo = ReMo(MOZILLA_REPS_SERVER_URL, origin='')
        self.assertEqual(remo.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.origin, MOZILLA_REPS_SERVER_URL)

        # If no url is provided, MOZILLA_REPS_URL is used
        remo = ReMo()
        self.assertEqual(remo.url, MOZILLA_REPS_URL)
        self.assertEqual(remo.origin, MOZILLA_REPS_URL)

    def __check_events_contents(self, items):
        self.assertEqual(items[0]['data']['city'], 'Makassar')
        self.assertEqual(items[0]['data']['end'], '2012-06-10T11:00:00Z')
        self.assertEqual(items[0]['origin'], MOZILLA_REPS_SERVER_URL)
        self.assertEqual(items[0]['uuid'], 'e701d4ed3b954361383d678d2168a44307d7ff60')
        self.assertEqual(items[0]['updated_on'], 1339326000.0)

    def __check_activities_contents(self, items):
        self.assertEqual(items[0]['data']['location'], 'Bhopal, Madhya Pradesh, India')
        self.assertEqual(items[0]['data']['report_date'], '2016-11-05')
        self.assertEqual(items[0]['origin'], MOZILLA_REPS_SERVER_URL)
        self.assertEqual(items[0]['uuid'], '9e2b0c2c8ec8094d2c53a2621bd09f9d6f65e67f')
        self.assertEqual(items[0]['updated_on'], 1478304000.0)

    def __check_users_contents(self, items):
        self.assertEqual(items[0]['data']['city'], 'Makati City')
        self.assertEqual(items[0]['data']['date_joined_program'], '2011-06-01')
        self.assertEqual(items[0]['origin'], MOZILLA_REPS_SERVER_URL)
        self.assertEqual(items[0]['uuid'], '90b0f5bc90ed8a694261df418a2b85beed94535a')
        self.assertEqual(items[0]['updated_on'], 1306886400.0)


    @httpretty.activate
    def __test_fetch(self, kind='events'):
        """Test whether the events are returned"""

        items_page = ReMoClient.ITEMS_PER_PAGE
        pages = 2  # two pages of testing data

        HTTPServer.routes()
        prev_requests_http = len(HTTPServer.requests_http)

        # Test fetch events with their reviews
        remo = ReMo(MOZILLA_REPS_SERVER_URL)

        items = [page for page in remo.fetch(kind=kind)]

        self.assertEqual(len(items), items_page * pages)

        if kind == 'events':
            self.__check_events_contents(items)
        elif kind == 'users':
            self.__check_users_contents(items)
        elif kind == 'activities':
            self.__check_activities_contents(items)

        # Check requests: page list, items, page list, items
        expected = [{'page':['1']}]
        for i in range(0, items_page):
            expected += [{}]
        expected += [{'page':['2']}]
        for i in range(0, items_page):
            expected += [{}]

        self.assertEqual(len(HTTPServer.requests_http)-prev_requests_http, len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(HTTPServer.requests_http[i].querystring, expected[i])

    def test_fetch_events(self):
        self.__test_fetch(kind='events')

    def test_fetch_activities(self):
        self.__test_fetch(kind='activities')

    def test_fetch_users(self):
        self.__test_fetch(kind='users')

    @httpretty.activate
    def test_fetch_offset(self):
        items_page = ReMoClient.ITEMS_PER_PAGE
        pages = 2  # two pages of testing data
        offset = 15

        HTTPServer.routes()
        prev_requests_http = len(HTTPServer.requests_http)

        # Test fetch events with their reviews
        remo = ReMo(MOZILLA_REPS_SERVER_URL)

        # Test we get the correct number of items from an offset
        items = [page for page in remo.fetch(offset=15)]
        self.assertEqual(len(items), (items_page * pages) - offset)

        # Test that the same offset (17) is the same item
        items = [page for page in remo.fetch(offset=5)]
        uuid_17_1 = items[12]['uuid']
        self.assertEqual(items[12]['offset'], 17)
        items = [page for page in remo.fetch(offset=12)]
        uuid_17_2 = items[5]['uuid']
        self.assertEqual(items[5]['offset'], 17)
        self.assertEqual(uuid_17_1, uuid_17_2)

    def test_fetch_wrong_kind(self):
        with self.assertRaises(ValueError):
            self.__test_fetch(kind='wrong')

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no items are fetched"""

        HTTPServer.routes(empty=True)

        remo = ReMo(MOZILLA_REPS_SERVER_URL)
        events = [event for event in remo.fetch()]

        self.assertEqual(len(events), 0)


class TestReMoBackendCache(unittest.TestCase):
    """ReMo backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def __test_fetch_from_cache(self, kind):
        """Test whether the cache works"""

        HTTPServer.routes()

        # First, we fetch the events from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        remo = ReMo(MOZILLA_REPS_SERVER_URL, cache=cache)

        items = [item for item in remo.fetch(kind=kind)]

        requests_done = len(HTTPServer.requests_http)

        # Now, we get the items from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_items = [item for item in remo.fetch_from_cache()]
        # No new requests to the server
        self.assertEqual(len(HTTPServer.requests_http), requests_done)
        # The contents should be the same
        self.assertEqual(len(cached_items), len(items))
        for i in range(0,len(items)):
            self.assertDictEqual(cached_items[i]['data'], items[i]['data'])

    def test_fetch_from_cache_events(self):
        self.__test_fetch_from_cache('events')

    def test_fetch_from_cache_users(self):
        self.__test_fetch_from_cache('users')

    def test_fetch_from_cache_activitites(self):
        self.__test_fetch_from_cache('activities')

    def test_fetch_from_empty_cache(self):
        """Test if there are not any events returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        remo = ReMo(MOZILLA_REPS_SERVER_URL, cache=cache)
        cached_events = [event for event in remo.fetch_from_cache()]
        self.assertEqual(len(cached_events), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        remo = ReMo(MOZILLA_REPS_SERVER_URL)

        with self.assertRaises(CacheError):
            _ = [event for event in remo.fetch_from_cache()]


class TestReMoCommand(unittest.TestCase):

    @httpretty.activate
    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['--origin', 'test', '--kind', 'users', MOZILLA_REPS_SERVER_URL]

        cmd = ReMoCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(cmd.parsed_args.origin, 'test')
        self.assertEqual(cmd.parsed_args.kind, 'users')
        self.assertEqual(cmd.parsed_args.offset, REMO_DEFAULT_OFFSET)
        self.assertIsInstance(cmd.backend, ReMo)

        args = ['--origin', 'test', MOZILLA_REPS_SERVER_URL]

        cmd = ReMoCommand(*args)
        # Default kind is events
        self.assertEqual(cmd.parsed_args.kind, 'events')

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = ReMoCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestReMoClient(unittest.TestCase):
    """ReMo API client tests

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""
        client = ReMoClient(MOZILLA_REPS_SERVER_URL)

    @httpretty.activate
    def test_get_items(self):
        """Test get_events API call"""

        HTTPServer.routes()

        # Set up a mock HTTP server
        body = read_file('data/remo_events_page_1_2.json')
        client = ReMoClient(MOZILLA_REPS_SERVER_URL)
        response = next(client.get_items())
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertEqual(req.path, '/api/beta/events/?page=1')
        # Check request params
        expected = {
                    'page' : ['1']
                    }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_call(self):
        """Test get_all_users API call"""

        HTTPServer.routes()

        # Set up a mock HTTP server
        body = read_file('data/remo_events_page_1_2.json')
        client = ReMoClient(MOZILLA_REPS_SERVER_URL)
        response = client.call(MOZILLA_REPS_API+'/events/?page=1')
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertEqual(req.path, '/api/beta/events/?page=1')
        # Check request params
        expected = {
                    'page' : ['1']
                    }
        self.assertDictEqual(req.querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

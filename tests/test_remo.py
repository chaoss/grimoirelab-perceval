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
import shutil
import sys
import tempfile
import unittest

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.remo import ReMo, ReMoCommand, ReMoClient, MOZILLA_REPS_URL


MOZILLA_REPS_SERVER_URL = 'http://example.com'
MOZILLA_REPS_API = MOZILLA_REPS_SERVER_URL + '/api/v1/'
MOZILLA_REPS_API_EVENTS = MOZILLA_REPS_SERVER_URL + '/api/v1/event/'
MOZILLA_REPS_API_USERS = MOZILLA_REPS_SERVER_URL + '/api/v1/rep/'

def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


class HTTPServer():

    requests_http = []  # requests done to the server

    @classmethod
    def routes(cls, empty=False):
        """Configure in http the routes to be served"""

        mozilla_events_1 = read_file('data/remo_events_1_2.json')
        mozilla_events_2 = read_file('data/remo_events_2_2.json')
        mozilla_reps = read_file('data/remo_reps.json')
        if empty:
            mozilla_events_1 = read_file('data/remo_events_empty.json')

        def request_callback(method, uri, headers):
            if 'rep/?' in uri:
                body = mozilla_reps
            else:
                offset = uri.split("offset=")[1].split("&")[0]
                if offset == "0":
                    body = mozilla_events_1
                else:
                    body = mozilla_events_2

            HTTPServer.requests_http.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               MOZILLA_REPS_API_EVENTS,
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               MOZILLA_REPS_API_USERS,
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])


class TestReMoBackend(unittest.TestCase):
    """ReMo backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        remo = ReMo(MOZILLA_REPS_SERVER_URL, tag='test')

        self.assertEqual(remo.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.origin, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.tag, 'test')
        self.assertIsInstance(remo.client, ReMoClient)

        # When tag is empty or None it will be set to
        # the value in url
        remo = ReMo(MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.origin, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.tag, MOZILLA_REPS_SERVER_URL)

        remo = ReMo(MOZILLA_REPS_SERVER_URL, tag='')
        self.assertEqual(remo.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.origin, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(remo.tag, MOZILLA_REPS_SERVER_URL)

        # If no url is provided, MOZILLA_REPS_URL is used
        remo = ReMo()
        self.assertEqual(remo.url, MOZILLA_REPS_URL)
        self.assertEqual(remo.origin, MOZILLA_REPS_URL)
        self.assertEqual(remo.tag, MOZILLA_REPS_URL)

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(ReMo.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(ReMo.has_resuming(), True)

    def __check_events_contents(self, events):
        self.assertEqual(events[0]['data']['estimated_attendance'], 1000)
        self.assertEqual(events[0]['data']['local_start'], '2012-06-06T10:00:00')
        self.assertEqual(events[0]['data']['start'], '2012-06-06T02:00:00')
        self.assertEqual(events[0]['origin'], MOZILLA_REPS_SERVER_URL)
        self.assertEqual(events[0]['uuid'], 'e701d4ed3b954361383d678d2168a44307d7ff60')
        self.assertEqual(events[0]['updated_on'], 1339326000.0)
        self.assertEqual(events[0]['category'], 'event')
        self.assertEqual(events[0]['tag'], MOZILLA_REPS_SERVER_URL)

        if len(events) > 1:
            self.assertEqual(events[1]['data']['estimated_attendance'], 50)
            self.assertEqual(events[1]['data']['local_start'], '2012-06-09T09:00:00')
            self.assertEqual(events[1]['data']['start'], '2012-06-09T07:00:00')
            self.assertEqual(events[1]['origin'], MOZILLA_REPS_SERVER_URL)
            self.assertEqual(events[1]['uuid'], 'e83e53b1f1039f62c66d2a977e23df3adf5bdc87')
            self.assertEqual(events[1]['updated_on'], 1339344000.0)
            self.assertEqual(events[1]['category'], 'event')
            self.assertEqual(events[1]['tag'], MOZILLA_REPS_SERVER_URL)

    @httpretty.activate
    def test_fetch(self):
        """Test whether the events are returned"""

        HTTPServer.routes()

        # Test fetch events with their reviews
        remo = ReMo(MOZILLA_REPS_SERVER_URL)

        events = [page for page in remo.fetch()]

        self.assertEqual(len(events), 4)

        self.__check_events_contents(events)

        # Check requests: first get all users, then the events
        expected = [{'limit':['400']},
                    {'limit':['40'], 'offset':['0']},
                    {'limit':['40'], 'offset':['2']}
                    ]

        self.assertEqual(len(HTTPServer.requests_http), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(HTTPServer.requests_http[i].querystring, expected[i])


    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no jobs are fetched"""

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
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        HTTPServer.routes()

        # First, we fetch the events from the server, storing them
        # in a cache
        cache = Cache(self.tmp_path)
        remo = ReMo(MOZILLA_REPS_SERVER_URL, cache=cache)

        events = [event for event in remo.fetch()]

        requests_done = len(HTTPServer.requests_http)

        # Now, we get the events from the cache.
        # The contents should be the same and there won't be
        # any new request to the server
        cached_events = [event for event in remo.fetch_from_cache()]
        # No new requests to the server
        self.assertEqual(len(HTTPServer.requests_http), requests_done)
        # The contents should be the same
        self.assertEqual(len(cached_events), len(events))
        for i in range(0,len(events)):
            self.assertDictEqual(cached_events[i]['data'], events[i]['data'])

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

        args = ['--tag', 'test', MOZILLA_REPS_SERVER_URL]

        cmd = ReMoCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.url, MOZILLA_REPS_SERVER_URL)
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, ReMo)

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
    def test_get_events(self):
        """Test get_events API call"""

        HTTPServer.routes()

        # Set up a mock HTTP server
        body = read_file('data/remo_events_1_2.json')
        client = ReMoClient(MOZILLA_REPS_SERVER_URL)
        response = next(client.get_events())
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api/v1/event/')
        # Check request params
        expected = {
                    'limit' : ['40'],
                    'offset' : ['0']
                    }
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_get_all_users(self):
        """Test get_all_users API call"""

        HTTPServer.routes()

        # Set up a mock HTTP server
        body = read_file('data/remo_reps.json')
        client = ReMoClient(MOZILLA_REPS_SERVER_URL)
        response = client.get_all_users()
        req = HTTPServer.requests_http[-1]
        self.assertEqual(response, body)
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/api/v1/rep/')
        # Check request params
        expected = {
                    'limit' : ['400']
                    }
        self.assertDictEqual(req.querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

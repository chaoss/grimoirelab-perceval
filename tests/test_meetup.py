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

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.cache import Cache
from perceval.errors import CacheError
from perceval.backends.meetup import (Meetup,
                                      MeetupCommand,
                                      MeetupClient)


MEETUP_URL = 'https://api.meetup.com'
MEETUP_GROUP_URL = MEETUP_URL + '/sqlpass-es'
MEETUP_EVENTS_URL = MEETUP_GROUP_URL + '/events'
MEETUP_EVENT_1_URL = MEETUP_EVENTS_URL + '/1'
MEETUP_EVENT_2_URL = MEETUP_EVENTS_URL + '/2'
MEETUP_EVENT_3_URL = MEETUP_EVENTS_URL + '/3'
MEETUP_EVENT_1_COMMENTS_URL = MEETUP_EVENT_1_URL + '/comments'
MEETUP_EVENT_2_COMMENTS_URL = MEETUP_EVENT_2_URL + '/comments'
MEETUP_EVENT_3_COMMENTS_URL = MEETUP_EVENT_3_URL + '/comments'
MEETUP_EVENT_1_RSVPS_URL = MEETUP_EVENT_1_URL + '/rsvps'
MEETUP_EVENT_2_RSVPS_URL = MEETUP_EVENT_2_URL + '/rsvps'
MEETUP_EVENT_3_RSVPS_URL = MEETUP_EVENT_3_URL + '/rsvps'

MEETUP_COMMENTS_URL = [
    MEETUP_EVENT_1_COMMENTS_URL,
    MEETUP_EVENT_2_COMMENTS_URL,
    MEETUP_EVENT_3_COMMENTS_URL
]
MEETUP_RSVPS_URL = [
    MEETUP_EVENT_1_RSVPS_URL,
    MEETUP_EVENT_2_RSVPS_URL,
    MEETUP_EVENT_3_RSVPS_URL
]


def read_file(filename, mode='r'):
    with open(filename, mode) as f:
        content = f.read()
    return content


def setup_http_server():
    """Setup a mock HTTP server"""

    http_requests = []

    events_bodies = [
        read_file('data/meetup/meetup_events.json', 'rb'),
        read_file('data/meetup/meetup_events_next.json', 'rb')
    ]
    events_empty_body = read_file('data/meetup/meetup_events_empty.json', 'rb')
    event_comments_body = read_file('data/meetup/meetup_comments.json', 'rb')
    event_rsvps_body = read_file('data/meetup/meetup_rsvps.json', 'rb')

    def request_callback(method, uri, headers):
        last_request = httpretty.last_request()

        if uri.startswith(MEETUP_EVENT_1_COMMENTS_URL):
            body = event_comments_body
        elif uri.startswith(MEETUP_EVENT_2_COMMENTS_URL):
            body = event_comments_body
        elif uri.startswith(MEETUP_EVENT_3_COMMENTS_URL):
            body = event_comments_body
        elif uri.startswith(MEETUP_EVENT_1_RSVPS_URL):
            body = event_rsvps_body
        elif uri.startswith(MEETUP_EVENT_2_RSVPS_URL):
            body = event_rsvps_body
        elif uri.startswith(MEETUP_EVENT_3_RSVPS_URL):
            body = event_rsvps_body
        elif uri.startswith(MEETUP_EVENTS_URL):
            params = last_request.querystring
            scroll = params.get('scroll', None)

            if scroll and scroll[0] == 'since:2016-09-25T00:00:00.000Z':
                # Last events and no pagination
                body = events_bodies[-1]
            elif scroll and scroll[0] == 'since:2017-01-01T00:00:00.000Z':
                body = events_empty_body
            else:
                body = events_bodies.pop(0)

                if events_bodies:
                    # Mock the 'Link' header with a fake URL
                    headers['Link'] = '<' + MEETUP_EVENTS_URL + '>; rel="next"'
        else:
            raise

        http_requests.append(last_request)

        return (200, headers, body)

    httpretty.register_uri(httpretty.GET,
                           MEETUP_EVENTS_URL,
                           responses=[
                                httpretty.Response(body=request_callback) \
                                    for _ in range(2)
                           ])

    for url in MEETUP_COMMENTS_URL:
        httpretty.register_uri(httpretty.GET,
                               url,
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])
    for url in MEETUP_RSVPS_URL:
        httpretty.register_uri(httpretty.GET,
                               url,
                               responses=[
                                    httpretty.Response(body=request_callback)
                               ])

    return http_requests


class TestMeetupBackend(unittest.TestCase):
    """Meetup backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        meetup = Meetup('mygroup', 'aaaa', max_items=5, tag='test')

        self.assertEqual(meetup.origin, 'https://meetup.com/')
        self.assertEqual(meetup.tag, 'test')
        self.assertEqual(meetup.group, 'mygroup')
        self.assertEqual(meetup.max_items, 5)
        self.assertIsInstance(meetup.client, MeetupClient)
        self.assertEqual(meetup.client.api_key, 'aaaa')

        # When tag is empty or None it will be set to
        # the value in URL
        meetup = Meetup('mygroup', 'aaaa')
        self.assertEqual(meetup.origin, 'https://meetup.com/')
        self.assertEqual(meetup.tag, 'https://meetup.com/')

        meetup = Meetup('mygroup', 'aaaa', tag='')
        self.assertEqual(meetup.origin, 'https://meetup.com/')
        self.assertEqual(meetup.tag, 'https://meetup.com/')

    def test_has_caching(self):
        """Test if it returns True when has_caching is called"""

        self.assertEqual(Meetup.has_caching(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Meetup.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether it fetches a set of events"""

        http_requests = setup_http_server()

        meetup = Meetup('sqlpass-es', 'aaaa', max_items=2)
        events = [event for event in meetup.fetch()]

        expected = [('1', '0d07fe36f994a6c78dfcf60fb73674bcf158cb5a', 1460065164.0, 2, 3),
                    ('2', '24b47b622eb33965676dd951b18eea7689b1d81c', 1465503498.0, 2, 3),
                    ('3', 'a42b7cf556c17b17f05b951e2eb5e07a7cb0a731', 1474842748.0, 2, 3)]

        self.assertEqual(len(events), len(expected))

        for x in range(len(events)):
            event = events[x]
            expc = expected[x]
            self.assertEqual(event['data']['id'], expc[0])
            self.assertEqual(event['uuid'], expc[1])
            self.assertEqual(event['origin'], 'https://meetup.com/')
            self.assertEqual(event['updated_on'], expc[2])
            self.assertEqual(event['category'], 'event')
            self.assertEqual(event['tag'], 'https://meetup.com/')
            self.assertEqual(len(event['data']['comments']), expc[3])
            self.assertEqual(len(event['data']['rsvps']), expc[4])

        # Check requests
        expected = [
            {
             'fields' : ['event_hosts', 'featured', 'group_topics',
                         'plain_text_description', 'rsvpable', 'series'],
             'key' : ['aaaa'],
             'order' : ['updated'],
             'page' : ['2'],
             'scroll' : ['since:1970-01-01T00:00:00.000Z'],
             'sign' : ['true'],
             'status' : ['cancelled', 'upcoming', 'past', 'proposed',
                         'suggested', 'draft']
            },
            {
             'key' : ['aaaa'],
             'page' : ['2'],
             'sign' : ['true']
            },
            {
             'fields' : ['attendance_status'],
             'key' : ['aaaa'],
             'page' : ['2'],
             'response' : ['yes', 'no'],
             'sign' : ['true']
            },
            {
             'key' : ['aaaa'],
             'page' : ['2'],
             'sign' : ['true']
            },
            {
             'fields' : ['attendance_status'],
             'key' : ['aaaa'],
             'page' : ['2'],
             'response' : ['yes', 'no'],
             'sign' : ['true']
            },
            {
             'key': ['aaaa'],
             'sign': ['true']
            },
            {
             'key' : ['aaaa'],
             'page' : ['2'],
             'sign' : ['true']
            },
            {
             'fields' : ['attendance_status'],
             'key' : ['aaaa'],
             'page' : ['2'],
             'response' : ['yes', 'no'],
             'sign' : ['true']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test wether if fetches a set of events from the given date"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2016, 9, 25)

        meetup = Meetup('sqlpass-es', 'aaaa', max_items=2)
        events = [event for event in meetup.fetch(from_date=from_date)]

        expected = [('3', 'a42b7cf556c17b17f05b951e2eb5e07a7cb0a731', 1474842748.0, 2, 3)]

        self.assertEqual(len(events), len(expected))

        for x in range(len(events)):
            event = events[x]
            expc = expected[x]
            self.assertEqual(event['data']['id'], expc[0])
            self.assertEqual(event['uuid'], expc[1])
            self.assertEqual(event['origin'], 'https://meetup.com/')
            self.assertEqual(event['updated_on'], expc[2])
            self.assertEqual(event['category'], 'event')
            self.assertEqual(event['tag'], 'https://meetup.com/')
            self.assertEqual(len(event['data']['comments']), expc[3])
            self.assertEqual(len(event['data']['rsvps']), expc[4])

        # Check requests
        expected = [
            {
             'fields' : ['event_hosts', 'featured', 'group_topics',
                         'plain_text_description', 'rsvpable', 'series'],
             'key' : ['aaaa'],
             'order' : ['updated'],
             'page' : ['2'],
             'scroll' : ['since:2016-09-25T00:00:00.000Z'],
             'sign' : ['true'],
             'status' : ['cancelled', 'upcoming', 'past', 'proposed',
                         'suggested', 'draft']
            },
            {
             'key' : ['aaaa'],
             'page' : ['2'],
             'sign' : ['true']
            },
            {
             'fields' : ['attendance_status'],
             'key' : ['aaaa'],
             'page' : ['2'],
             'response' : ['yes', 'no'],
             'sign' : ['true']
            }
        ]

        self.assertEqual(len(http_requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(http_requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test if nothing is returned when there are no events"""

        http_requests = setup_http_server()

        from_date = datetime.datetime(2017, 1, 1)

        meetup = Meetup('sqlpass-es', 'aaaa', max_items=2)
        events = [event for event in meetup.fetch(from_date=from_date)]

        self.assertEqual(len(events), 0)

        # Check requests
        expected = {
            'fields' : ['event_hosts', 'featured', 'group_topics',
                        'plain_text_description', 'rsvpable', 'series'],
            'key' : ['aaaa'],
            'order' : ['updated'],
            'page' : ['2'],
            'scroll' : ['since:2017-01-01T00:00:00.000Z'],
            'sign' : ['true'],
            'status' : ['cancelled', 'upcoming', 'past', 'proposed',
                         'suggested', 'draft']
        }

        self.assertEqual(len(http_requests), 1)
        self.assertDictEqual(http_requests[0].querystring, expected)

    def test_parse_json(self):
        """Test if it parses a JSON stream"""

        raw_json = read_file('data/meetup/meetup_events.json')

        items = Meetup.parse_json(raw_json)
        results = [item for item in items]

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], '1')
        self.assertEqual(results[1]['id'], '2')

        # Parse a file without results
        raw_json = read_file('data/meetup/meetup_events_empty.json')

        items = Meetup.parse_json(raw_json)
        results = [item for item in items]

        self.assertEqual(len(results), 0)


class TestMeetupBackendCache(unittest.TestCase):
    """Redmine backend tests using a cache"""

    def setUp(self):
        self.tmp_path = tempfile.mkdtemp(prefix='perceval_')

    def tearDown(self):
        shutil.rmtree(self.tmp_path)

    @httpretty.activate
    def test_fetch_from_cache(self):
        """Test whether the cache works"""

        http_requests = setup_http_server()

        # First, we fetch the events from the server,
        # storing them in a cache
        cache = Cache(self.tmp_path)
        meetup = Meetup('sqlpass-es', 'aaaa', max_items=2, cache=cache)
        events = [event for event in meetup.fetch()]

        self.assertEqual(len(http_requests), 8)

        # Now, we get the events from the cache.
        # The events should be the same and there won't be
        # any new request to the server
        cached_events = [event for event in meetup.fetch_from_cache()]
        self.assertEqual(len(cached_events), len(events))

        expected = [('1', '0d07fe36f994a6c78dfcf60fb73674bcf158cb5a', 1460065164.0, 2, 3),
                    ('2', '24b47b622eb33965676dd951b18eea7689b1d81c', 1465503498.0, 2, 3),
                    ('3', 'a42b7cf556c17b17f05b951e2eb5e07a7cb0a731', 1474842748.0, 2, 3)]

        self.assertEqual(len(cached_events), len(expected))

        for x in range(len(cached_events)):
            event = cached_events[x]
            expc = expected[x]
            self.assertEqual(event['data']['id'], expc[0])
            self.assertEqual(event['uuid'], expc[1])
            self.assertEqual(event['origin'], 'https://meetup.com/')
            self.assertEqual(event['updated_on'], expc[2])
            self.assertEqual(event['category'], 'event')
            self.assertEqual(event['tag'], 'https://meetup.com/')
            self.assertEqual(len(event['data']['comments']), expc[3])
            self.assertEqual(len(event['data']['rsvps']), expc[4])

            # Compare chached and fetched task
            self.assertDictEqual(event['data'], events[x]['data'])

        # No more requests were sent
        self.assertEqual(len(http_requests), 8)

    def test_fetch_from_empty_cache(self):
        """Test if there are not any event returned when the cache is empty"""

        cache = Cache(self.tmp_path)
        meetup = Meetup('sqlpass-es', 'aaaa', max_items=2, cache=cache)
        cached_events = [event for event in meetup.fetch_from_cache()]
        self.assertEqual(len(cached_events), 0)

    def test_fetch_from_non_set_cache(self):
        """Test if a error is raised when the cache was not set"""

        meetup = Meetup('sqlpass-es', 'aaaa', max_items=2)

        with self.assertRaises(CacheError):
            _ = [event for event in meetup.fetch_from_cache()]


class TestMeetupCommand(unittest.TestCase):
    """Tests for MeetupCommand class"""

    def test_parsing_on_init(self):
        """Test if the class is initialized"""

        args = ['sqlpass-es',
                '--backend-token', 'aaaa',
                '--max-items', '5',
                '--tag', 'test']

        cmd = MeetupCommand(*args)
        self.assertIsInstance(cmd.parsed_args, argparse.Namespace)
        self.assertEqual(cmd.parsed_args.group, 'sqlpass-es')
        self.assertEqual(cmd.parsed_args.backend_token, 'aaaa')
        self.assertEqual(cmd.parsed_args.max_items, 5)
        self.assertEqual(cmd.parsed_args.tag, 'test')
        self.assertIsInstance(cmd.backend, Meetup)

    def test_argument_parser(self):
        """Test if it returns a argument parser object"""

        parser = MeetupCommand.create_argument_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)


class TestMeetupClient(unittest.TestCase):
    """Meetup REST API client tests.

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    def test_init(self):
        """Test initialization"""

        client = MeetupClient('aaaa', max_items=10)
        self.assertEqual(client.api_key, 'aaaa')
        self.assertEqual(client.max_items, 10)

    @httpretty.activate
    def test_events(self):
        """Test events API call"""

        http_requests = setup_http_server()

        client = MeetupClient('aaaa', max_items=2)

        from_date = datetime.datetime(2016, 1, 1)

        # Call API
        events = client.events('sqlpass-es', from_date=from_date)
        result = [event for event in events]

        self.assertEqual(len(result), 2)

        expected = [
            {
             'fields' : ['event_hosts', 'featured', 'group_topics',
                         'plain_text_description', 'rsvpable', 'series'],
             'key' : ['aaaa'],
             'order' : ['updated'],
             'page' : ['2'],
             'scroll' : ['since:2016-01-01T00:00:00.000Z'],
             'sign' : ['true'],
             'status' : ['cancelled', 'upcoming', 'past', 'proposed',
                         'suggested', 'draft']
            },
            {
             'key': ['aaaa'],
             'sign': ['true']
            }
        ]

        self.assertEqual(len(http_requests), 2)

        for x in range(0, len(http_requests)):
            req = http_requests[x]
            self.assertEqual(req.method, 'GET')
            self.assertRegex(req.path, '/sqlpass-es/events')
            self.assertDictEqual(req.querystring, expected[x])

    @httpretty.activate
    def test_comments(self):
        """Test comments API call"""

        http_requests = setup_http_server()

        client = MeetupClient('aaaa', max_items=2)

        # Call API
        comments = client.comments('sqlpass-es', '1')
        result = [comment for comment in comments]

        self.assertEqual(len(result), 1)

        expected = {
            'key' : ['aaaa'],
            'page' : ['2'],
            'sign' : ['true']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/sqlpass-es/events/1/comments')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_rsvps(self):
        """Test rsvps API call"""

        http_requests = setup_http_server()

        client = MeetupClient('aaaa', max_items=2)

        # Call API
        rsvps = client.rsvps('sqlpass-es', '1')
        result = [rsvp for rsvp in rsvps]

        self.assertEqual(len(result), 1)

        expected = {
            'fields' : ['attendance_status'],
            'key' : ['aaaa'],
            'page' : ['2'],
            'response' : ['yes', 'no'],
            'sign' : ['true']
        }

        self.assertEqual(len(http_requests), 1)

        req = http_requests[0]
        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/sqlpass-es/events/1/rsvps')
        self.assertDictEqual(req.querystring, expected)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

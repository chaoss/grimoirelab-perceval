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

import httpretty

if not '..' in sys.path:
    sys.path.insert(0, '..')

from perceval.backends.meetup import MeetupClient


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
    event_comments_body = read_file('data/meetup/meetup_comments.json')
    event_rsvps_body = read_file('data/meetup/meetup_rsvps.json', 'rb')

    def request_callback(method, uri, headers):
        print(uri)
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
            body = events_bodies.pop(0)

            if events_bodies:
                # Mock the 'Link' header with a fake URL
                headers['Link'] = '<' + MEETUP_EVENTS_URL + '>; rel="next"'
        else:
            raise

        http_requests.append(httpretty.last_request())

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

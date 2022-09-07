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
#     Harshal Mittal <harshalmittal4@gmail.com>
#

import copy
import datetime
import os
import shutil
import unittest

import httpretty
import requests

from perceval.backend import BackendCommandArgumentParser
from perceval.errors import BackendError, ParseError
from perceval.utils import DEFAULT_DATETIME
from perceval.backends.core.bugzilla import (Bugzilla,
                                             BugzillaCommand,
                                             BugzillaClient)
from base import TestCaseBackendArchive


BUGZILLA_SERVER_URL = 'http://example.com'
BUGZILLA_LOGIN_URL = BUGZILLA_SERVER_URL + '/index.cgi'
BUGZILLA_METADATA_URL = BUGZILLA_SERVER_URL + '/show_bug.cgi'
BUGZILLA_BUGLIST_URL = BUGZILLA_SERVER_URL + '/buglist.cgi'
BUGZILLA_BUG_URL = BUGZILLA_SERVER_URL + '/show_bug.cgi'
BUGZILLA_BUG_ACTIVITY_URL = BUGZILLA_SERVER_URL + '/show_activity.cgi'


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


class TestBugzillaBackend(unittest.TestCase):
    """Bugzilla backend tests"""

    def test_initialization(self):
        """Test whether attributes are initializated"""

        bg = Bugzilla(BUGZILLA_SERVER_URL, tag='test',
                      max_bugs=5)

        self.assertEqual(bg.url, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.origin, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.tag, 'test')
        self.assertEqual(bg.max_bugs, 5)
        self.assertIsNone(bg.client)
        self.assertTrue(bg.ssl_verify)

        # When tag is empty or None it will be set to
        # the value in the origin (URL)
        bg = Bugzilla(BUGZILLA_SERVER_URL)
        self.assertEqual(bg.url, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.origin, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.tag, BUGZILLA_SERVER_URL)

        bg = Bugzilla(BUGZILLA_SERVER_URL, tag='', ssl_verify=False)
        self.assertEqual(bg.url, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.origin, BUGZILLA_SERVER_URL)
        self.assertEqual(bg.tag, BUGZILLA_SERVER_URL)
        self.assertFalse(bg.ssl_verify)

    def test_has_archiving(self):
        """Test if it returns True when has_archiving is called"""

        self.assertEqual(Bugzilla.has_archiving(), True)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(Bugzilla.has_resuming(), True)

    @httpretty.activate
    def test_fetch(self):
        """Test whether a list of bugs is returned"""

        requests = []
        bodies_csv = [read_file('data/bugzilla/bugzilla_buglist.csv'),
                      read_file('data/bugzilla/bugzilla_buglist_next.csv'),
                      ""]
        bodies_xml = [read_file('data/bugzilla/bugzilla_version.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details_next.xml', mode='rb')]
        bodies_html = [read_file('data/bugzilla/bugzilla_bug_activity.html', mode='rb'),
                       read_file('data/bugzilla/bugzilla_bug_activity_empty.html', mode='rb')]

        def request_callback(method, uri, headers):
            if uri.startswith(BUGZILLA_BUGLIST_URL):
                body = bodies_csv.pop(0)
            elif uri.startswith(BUGZILLA_BUG_URL):
                body = bodies_xml.pop(0)
            else:
                body = bodies_html[len(requests) % 2]

            requests.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(7)
                               ])

        bg = Bugzilla(BUGZILLA_SERVER_URL,
                      max_bugs=5, max_bugs_csv=500)
        bugs = [bug for bug in bg.fetch()]

        self.assertEqual(len(bugs), 7)

        self.assertEqual(bugs[0]['data']['bug_id'][0]['__text__'], '15')
        self.assertEqual(len(bugs[0]['data']['activity']), 0)
        self.assertEqual(bugs[0]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[0]['uuid'], '5a8a1e25dfda86b961b4146050883cbfc928f8ec')
        self.assertEqual(bugs[0]['updated_on'], 1248276445.0)
        self.assertEqual(bugs[0]['category'], 'bug')
        self.assertEqual(bugs[0]['tag'], BUGZILLA_SERVER_URL)

        self.assertEqual(bugs[6]['data']['bug_id'][0]['__text__'], '888')
        self.assertEqual(len(bugs[6]['data']['activity']), 14)
        self.assertEqual(bugs[6]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[6]['uuid'], 'b4009442d38f4241a4e22e3e61b7cd8ef5ced35c')
        self.assertEqual(bugs[6]['updated_on'], 1439404330.0)
        self.assertEqual(bugs[6]['category'], 'bug')
        self.assertEqual(bugs[6]['tag'], BUGZILLA_SERVER_URL)

        # Check requests
        expected = [
            {
                'ctype': ['xml']
            },
            {
                'ctype': ['csv'],
                'limit': ['500'],
                'order': ['changeddate'],
                'chfieldfrom': ['1970-01-01 00:00:00']
            },
            {
                'ctype': ['csv'],
                'limit': ['500'],
                'order': ['changeddate'],
                'chfieldfrom': ['2009-07-30 11:35:33']
            },
            {
                'ctype': ['csv'],
                'limit': ['500'],
                'order': ['changeddate'],
                'chfieldfrom': ['2015-08-12 18:32:11']
            },
            {
                'ctype': ['xml'],
                'id': ['15', '18', '17', '20', '19'],
                'excludefield': ['attachmentdata']
            },
            {
                'id': ['15']
            },
            {
                'id': ['18']
            },
            {
                'id': ['17']
            },
            {
                'id': ['20']
            },
            {
                'id': ['19']
            },
            {
                'ctype': ['xml'],
                'id': ['30', '888'],
                'excludefield': ['attachmentdata']
            },
            {
                'id': ['30']
            },
            {
                'id': ['888']
            }
        ]

        self.assertEqual(len(requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(requests[i].querystring, expected[i])

    @httpretty.activate
    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        requests = []
        bodies_csv = [read_file('data/bugzilla/bugzilla_buglist.csv'),
                      read_file('data/bugzilla/bugzilla_buglist_next.csv'),
                      ""]
        bodies_xml = [read_file('data/bugzilla/bugzilla_version.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details_next.xml', mode='rb')]
        bodies_html = [read_file('data/bugzilla/bugzilla_bug_activity.html', mode='rb'),
                       read_file('data/bugzilla/bugzilla_bug_activity_empty.html', mode='rb')]

        def request_callback(method, uri, headers):
            if uri.startswith(BUGZILLA_BUGLIST_URL):
                body = bodies_csv.pop(0)
            elif uri.startswith(BUGZILLA_BUG_URL):
                body = bodies_xml.pop(0)
            else:
                body = bodies_html[len(requests) % 2]

            requests.append(httpretty.last_request())

            return 200, headers, body

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(7)
                               ])

        bg = Bugzilla(BUGZILLA_SERVER_URL,
                      max_bugs=5, max_bugs_csv=500)
        bugs = [bug for bug in bg.fetch()]

        self.assertEqual(len(bugs), 7)

        bug = bugs[0]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'][0]['__text__'], 'LibreGeoSocial (Android)')
        self.assertEqual(bug['data']['product'][0]['__text__'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'][0]['__text__'], 'general')
        self.assertEqual(bug['data']['component'][0]['__text__'], bug['search_fields']['component'])

        bug = bugs[1]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'][0]['__text__'], 'LibreGeoSocial (Android)')
        self.assertEqual(bug['data']['product'][0]['__text__'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'][0]['__text__'], 'general')
        self.assertEqual(bug['data']['component'][0]['__text__'], bug['search_fields']['component'])

        bug = bugs[2]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'][0]['__text__'], 'Bicho')
        self.assertEqual(bug['data']['product'][0]['__text__'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'][0]['__text__'], 'General')
        self.assertEqual(bug['data']['component'][0]['__text__'], bug['search_fields']['component'])

        bug = bugs[3]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'][0]['__text__'], 'LibreGeoSocial (server)')
        self.assertEqual(bug['data']['product'][0]['__text__'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'][0]['__text__'], 'general')
        self.assertEqual(bug['data']['component'][0]['__text__'], bug['search_fields']['component'])

        bug = bugs[4]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'][0]['__text__'], 'CVSAnalY')
        self.assertEqual(bug['data']['product'][0]['__text__'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'][0]['__text__'], 'general')
        self.assertEqual(bug['data']['component'][0]['__text__'], bug['search_fields']['component'])

        bug = bugs[5]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'][0]['__text__'], 'Bicho')
        self.assertEqual(bug['data']['product'][0]['__text__'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'][0]['__text__'], 'General')
        self.assertEqual(bug['data']['component'][0]['__text__'], bug['search_fields']['component'])

        bug = bugs[6]
        self.assertEqual(bg.metadata_id(bug['data']), bug['search_fields']['item_id'])
        self.assertEqual(bug['data']['product'][0]['__text__'], 'CVSAnalY')
        self.assertEqual(bug['data']['product'][0]['__text__'], bug['search_fields']['product'])
        self.assertEqual(bug['data']['component'][0]['__text__'], 'general')
        self.assertEqual(bug['data']['component'][0]['__text__'], bug['search_fields']['component'])

    @httpretty.activate
    def test_fetch_from_date(self):
        """Test whether a list of bugs is returned from a given date"""

        requests = []
        bodies_csv = [read_file('data/bugzilla/bugzilla_buglist_next.csv'),
                      ""]
        bodies_xml = [read_file('data/bugzilla/bugzilla_version.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details_next.xml', mode='rb')]
        bodies_html = [read_file('data/bugzilla/bugzilla_bug_activity.html', mode='rb'),
                       read_file('data/bugzilla/bugzilla_bug_activity_empty.html', mode='rb')]

        def request_callback(method, uri, headers):
            if uri.startswith(BUGZILLA_BUGLIST_URL):
                body = bodies_csv.pop(0)
            elif uri.startswith(BUGZILLA_BUG_URL):
                body = bodies_xml.pop(0)
            else:
                body = bodies_html[len(requests) % 2]

            requests.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])

        from_date = datetime.datetime(2015, 1, 1)

        bg = Bugzilla(BUGZILLA_SERVER_URL)
        bugs = [bug for bug in bg.fetch(from_date=from_date)]

        self.assertEqual(len(bugs), 2)
        self.assertEqual(bugs[0]['data']['bug_id'][0]['__text__'], '30')
        self.assertEqual(len(bugs[0]['data']['activity']), 14)
        self.assertEqual(bugs[0]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[0]['uuid'], '4b166308f205121bc57704032acdc81b6c9bb8b1')
        self.assertEqual(bugs[0]['updated_on'], 1426868155.0)
        self.assertEqual(bugs[0]['category'], 'bug')
        self.assertEqual(bugs[0]['tag'], BUGZILLA_SERVER_URL)

        self.assertEqual(bugs[1]['data']['bug_id'][0]['__text__'], '888')
        self.assertEqual(len(bugs[1]['data']['activity']), 0)
        self.assertEqual(bugs[1]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[1]['uuid'], 'b4009442d38f4241a4e22e3e61b7cd8ef5ced35c')
        self.assertEqual(bugs[1]['updated_on'], 1439404330.0)
        self.assertEqual(bugs[1]['category'], 'bug')
        self.assertEqual(bugs[1]['tag'], BUGZILLA_SERVER_URL)

        # Check requests
        expected = [
            {
                'ctype': ['xml']
            },
            {
                'ctype': ['csv'],
                'limit': ['10000'],
                'order': ['changeddate'],
                'chfieldfrom': ['2015-01-01 00:00:00']
            },
            {
                'ctype': ['csv'],
                'limit': ['10000'],
                'order': ['changeddate'],
                'chfieldfrom': ['2015-08-12 18:32:11']
            },
            {
                'ctype': ['xml'],
                'id': ['30', '888'],
                'excludefield': ['attachmentdata']
            },
            {
                'id': ['30']
            },
            {
                'id': ['888']
            }
        ]

        self.assertEqual(len(requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(requests[i].querystring, expected[i])

    @httpretty.activate
    def test_fetch_empty(self):
        """Test whether it works when no bugs are fetched"""

        body = read_file('data/bugzilla/bugzilla_version.xml')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               body="", status=200)

        from_date = datetime.datetime(2100, 1, 1)

        bg = Bugzilla(BUGZILLA_SERVER_URL)
        bugs = [bug for bug in bg.fetch(from_date=from_date)]

        self.assertEqual(len(bugs), 0)

        # Check request
        expected = {
            'ctype': ['csv'],
            'limit': ['10000'],
            'order': ['changeddate'],
            'chfieldfrom': ['2100-01-01 00:00:00']
        }

        req = httpretty.last_request()

        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_fetch_auth(self):
        """Test whether authentication works"""

        requests = []
        bodies_csv = [read_file('data/bugzilla/bugzilla_buglist_next.csv'),
                      ""]
        bodies_xml = [read_file('data/bugzilla/bugzilla_version.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details_next.xml', mode='rb')]
        bodies_html = [read_file('data/bugzilla/bugzilla_bug_activity.html', mode='rb'),
                       read_file('data/bugzilla/bugzilla_bug_activity_empty.html', mode='rb')]

        def request_callback(method, uri, headers):
            if uri.startswith(BUGZILLA_LOGIN_URL):
                body = "index.cgi?logout=1"
            elif uri.startswith(BUGZILLA_BUGLIST_URL):
                body = bodies_csv.pop(0)
            elif uri.startswith(BUGZILLA_BUG_URL):
                body = bodies_xml.pop(0)
            else:
                body = bodies_html[(len(requests) + 1) % 2]

            requests.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.POST,
                               BUGZILLA_LOGIN_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])

        from_date = datetime.datetime(2015, 1, 1)

        bg = Bugzilla(BUGZILLA_SERVER_URL,
                      user='jsmith@example.com',
                      password='1234')
        bugs = [bug for bug in bg.fetch(from_date=from_date)]

        self.assertEqual(len(bugs), 2)
        self.assertEqual(bugs[0]['data']['bug_id'][0]['__text__'], '30')
        self.assertEqual(len(bugs[0]['data']['activity']), 14)
        self.assertEqual(bugs[0]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[0]['uuid'], '4b166308f205121bc57704032acdc81b6c9bb8b1')
        self.assertEqual(bugs[0]['updated_on'], 1426868155.0)
        self.assertEqual(bugs[0]['category'], 'bug')
        self.assertEqual(bugs[0]['tag'], BUGZILLA_SERVER_URL)

        self.assertEqual(bugs[1]['data']['bug_id'][0]['__text__'], '888')
        self.assertEqual(len(bugs[1]['data']['activity']), 0)
        self.assertEqual(bugs[1]['origin'], BUGZILLA_SERVER_URL)
        self.assertEqual(bugs[1]['uuid'], 'b4009442d38f4241a4e22e3e61b7cd8ef5ced35c')
        self.assertEqual(bugs[1]['updated_on'], 1439404330.0)
        self.assertEqual(bugs[1]['category'], 'bug')
        self.assertEqual(bugs[1]['tag'], BUGZILLA_SERVER_URL)

        # Check requests
        auth_expected = {
            'Bugzilla_login': ['jsmith@example.com'],
            'Bugzilla_password': ['1234'],
            'GoAheadAndLogIn': ['Log in']
        }
        expected = [
            {
                'ctype': ['xml']
            },
            {
                'ctype': ['csv'],
                'limit': ['10000'],
                'order': ['changeddate'],
                'chfieldfrom': ['2015-01-01 00:00:00']
            },
            {
                'ctype': ['csv'],
                'limit': ['10000'],
                'order': ['changeddate'],
                'chfieldfrom': ['2015-08-12 18:32:11']
            },
            {
                'ctype': ['xml'],
                'id': ['30', '888'],
                'excludefield': ['attachmentdata']
            },
            {
                'id': ['30']
            },
            {
                'id': ['888']
            }
        ]

        # Check authentication request
        auth_req = requests.pop(0)
        self.assertDictEqual(auth_req.parsed_body, auth_expected)

        # Check the rests of the headers
        self.assertEqual(len(requests), len(expected))

        for i in range(len(expected)):
            self.assertDictEqual(requests[i].querystring, expected[i])


class TestBugzillaBackendArchive(TestCaseBackendArchive):
    """Bugzilla backend tests using an archive"""

    def setUp(self):
        super().setUp()
        self.backend_write_archive = Bugzilla(BUGZILLA_SERVER_URL,
                                              user='jsmith@example.com', password='1234',
                                              max_bugs=5, max_bugs_csv=500,
                                              archive=self.archive)
        self.backend_read_archive = Bugzilla(BUGZILLA_SERVER_URL,
                                             user='jreno@example.com', password='5678',
                                             max_bugs=5, max_bugs_csv=500,
                                             archive=self.archive)

    def tearDown(self):
        shutil.rmtree(self.test_path)

    @httpretty.activate
    def test_fetch_from_archive(self):
        """Test whether a list of bugs is returned from the archive"""

        requests = []
        bodies_csv = [read_file('data/bugzilla/bugzilla_buglist.csv'),
                      read_file('data/bugzilla/bugzilla_buglist_next.csv'),
                      ""]
        bodies_xml = [read_file('data/bugzilla/bugzilla_version.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details_next.xml', mode='rb')]
        bodies_html = [read_file('data/bugzilla/bugzilla_bug_activity.html', mode='rb'),
                       read_file('data/bugzilla/bugzilla_bug_activity_empty.html', mode='rb')]

        def request_callback(method, uri, headers):
            if uri.startswith(BUGZILLA_BUGLIST_URL):
                body = bodies_csv.pop(0)
            elif uri.startswith(BUGZILLA_BUG_URL):
                body = bodies_xml.pop(0)
            else:
                body = bodies_html[len(requests) % 2]

            requests.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.POST,
                               BUGZILLA_LOGIN_URL,
                               body="index.cgi?logout=1",
                               status=200)
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(3)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(7)
                               ])

        self._test_fetch_from_archive(from_date=None)

    @httpretty.activate
    def test_fetch_from_date_from_archive(self):
        """Test whether a list of bugs is returned from a given date from archive"""

        requests = []
        bodies_csv = [read_file('data/bugzilla/bugzilla_buglist_next.csv'),
                      ""]
        bodies_xml = [read_file('data/bugzilla/bugzilla_version.xml', mode='rb'),
                      read_file('data/bugzilla/bugzilla_bugs_details_next.xml', mode='rb')]
        bodies_html = [read_file('data/bugzilla/bugzilla_bug_activity.html', mode='rb'),
                       read_file('data/bugzilla/bugzilla_bug_activity_empty.html', mode='rb')]

        def request_callback(method, uri, headers):
            if uri.startswith(BUGZILLA_BUGLIST_URL):
                body = bodies_csv.pop(0)
            elif uri.startswith(BUGZILLA_BUG_URL):
                body = bodies_xml.pop(0)
            else:
                body = bodies_html[len(requests) % 2]

            requests.append(httpretty.last_request())

            return (200, headers, body)

        httpretty.register_uri(httpretty.POST,
                               BUGZILLA_LOGIN_URL,
                               body="index.cgi?logout=1",
                               status=200)
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                               ])
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               responses=[
                                   httpretty.Response(body=request_callback)
                                   for _ in range(2)
                               ])

        from_date = datetime.datetime(2015, 1, 1)
        self._test_fetch_from_archive(from_date=from_date)

    @httpretty.activate
    def test_fetch_empty_from_archive(self):
        """Test whether it works when no bugs are fetched from archive"""

        body = read_file('data/bugzilla/bugzilla_version.xml')
        httpretty.register_uri(httpretty.POST,
                               BUGZILLA_LOGIN_URL,
                               body="index.cgi?logout=1",
                               status=200)
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               body="", status=200)

        from_date = datetime.datetime(2100, 1, 1)
        self._test_fetch_from_archive(from_date=from_date)


class TestBugzillaBackendParsers(unittest.TestCase):
    """Bugzilla backend parsers tests"""

    def test_parse_buglist(self):
        """Test buglist parsing"""

        raw_csv = read_file('data/bugzilla/bugzilla_buglist.csv')

        bugs = Bugzilla.parse_buglist(raw_csv)
        result = [bug for bug in bugs]

        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]['bug_id'], '15')
        self.assertEqual(result[4]['bug_id'], '19')

    def test_parse_bugs_details(self):
        """Test bugs details parsing"""

        raw_xml = read_file('data/bugzilla/bugzilla_bugs_details.xml')

        bugs = Bugzilla.parse_bugs_details(raw_xml)
        result = [bug for bug in bugs]

        self.assertEqual(len(result), 5)

        bug_ids = [bug['bug_id'][0]['__text__'] for bug in result]
        expected = ['15', '18', '17', '20', '19']

        self.assertListEqual(bug_ids, expected)

        raw_xml = read_file('data/bugzilla/bugzilla_bugs_details_next.xml')

        bugs = Bugzilla.parse_bugs_details(raw_xml)
        result = [bug for bug in bugs]

    def test_parse_invalid_bug_details(self):
        """Test whether it fails parsing an invalid XML with no bugs"""

        raw_xml = read_file('data/bugzilla/bugzilla_bugs_details_not_valid.xml')

        with self.assertRaises(ParseError):
            bugs = Bugzilla.parse_bugs_details(raw_xml)
            _ = [bug for bug in bugs]

    def test_parse_activity(self):
        """Test activity bug parsing"""

        raw_html = read_file('data/bugzilla/bugzilla_bug_activity.html')

        activity = Bugzilla.parse_bug_activity(raw_html)
        result = [event for event in activity]

        self.assertEqual(len(result), 14)

        expected = {
            'Who': 'sduenas@example.org',
            'When': '2013-06-25 11:57:23 CEST',
            'What': 'Attachment #172 Attachment is obsolete',
            'Removed': '0',
            'Added': '1'
        }
        self.assertDictEqual(result[0], expected)

        expected = {
            'Who': 'sduenas@example.org',
            'When': '2013-06-25 11:59:07 CEST',
            'What': 'Depends on',
            'Removed': '350',
            'Added': ''
        }
        self.assertDictEqual(result[6], expected)

    def test_parse_empty_activity(self):
        """Test the parser when the activity table is empty"""

        # There are two possible cases for empty tables.
        # The first case includes the term 'bug' while the second
        # one replaces it by 'issue'.

        raw_html = read_file('data/bugzilla/bugzilla_bug_activity_empty.html')

        activity = Bugzilla.parse_bug_activity(raw_html)
        result = [event for event in activity]
        self.assertEqual(len(result), 0)

        raw_html = read_file('data/bugzilla/bugzilla_bug_activity_empty_alt.html')

        activity = Bugzilla.parse_bug_activity(raw_html)
        result = [event for event in activity]
        self.assertEqual(len(result), 0)

    def test_parse_activity_no_table(self):
        """Test if it raises an exception the activity table is not found"""

        raw_html = read_file('data/bugzilla/bugzilla_bug_activity_not_valid.html')

        with self.assertRaises(ParseError):
            activity = Bugzilla.parse_bug_activity(raw_html)
            _ = [event for event in activity]


class TestBugzillaCommand(unittest.TestCase):
    """BugzillaCommand unit tests"""

    def test_backend_class(self):
        """Test if the backend class is Bugzilla"""

        self.assertIs(BugzillaCommand.BACKEND, Bugzilla)

    def test_setup_cmd_parser(self):
        """Test if it parser object is correctly initialized"""

        parser = BugzillaCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, Bugzilla)

        args = ['--backend-user', 'jsmith@example.com',
                '--backend-password', '1234',
                '--max-bugs', '10', '--max-bugs-csv', '5',
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-archive',
                BUGZILLA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith@example.com')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.max_bugs, 10)
        self.assertEqual(parsed_args.max_bugs_csv, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertTrue(parsed_args.no_archive)
        self.assertTrue(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.url, BUGZILLA_SERVER_URL)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)

        args = ['--backend-user', 'jsmith@example.com',
                '--backend-password', '1234',
                '--max-bugs', '10', '--max-bugs-csv', '5',
                '--tag', 'test',
                '--from-date', '1970-01-01',
                '--no-ssl-verify',
                BUGZILLA_SERVER_URL]

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.user, 'jsmith@example.com')
        self.assertEqual(parsed_args.password, '1234')
        self.assertEqual(parsed_args.max_bugs, 10)
        self.assertEqual(parsed_args.max_bugs_csv, 5)
        self.assertEqual(parsed_args.tag, 'test')
        self.assertFalse(parsed_args.ssl_verify)
        self.assertEqual(parsed_args.url, BUGZILLA_SERVER_URL)
        self.assertEqual(parsed_args.from_date, DEFAULT_DATETIME)


class TestBugzillaClient(unittest.TestCase):
    """Bugzilla API client tests

    These tests not check the body of the response, only if the call
    was well formed and if a response was obtained. Due to this, take
    into account that the body returned on each request might not
    match with the parameters from the request.
    """
    @httpretty.activate
    def test_init(self):
        """Test initialization"""

        client = BugzillaClient(BUGZILLA_SERVER_URL)
        self.assertEqual(client.version, None)
        self.assertTrue(client.ssl_verify)
        self.assertIsInstance(client.session, requests.Session)

        client = BugzillaClient(BUGZILLA_SERVER_URL, ssl_verify=False)
        self.assertEqual(client.version, None)
        self.assertFalse(client.ssl_verify)
        self.assertIsInstance(client.session, requests.Session)

    @httpretty.activate
    def test_init_auth(self):
        """Test initialization with authentication"""

        # Set up a mock HTTP server
        httpretty.register_uri(httpretty.POST,
                               BUGZILLA_LOGIN_URL,
                               body="index.cgi?logout=1",
                               status=200)

        _ = BugzillaClient(BUGZILLA_SERVER_URL,
                           user='jsmith@example.com',
                           password='1234')

        # Check request params
        expected = {
            'Bugzilla_login': ['jsmith@example.com'],
            'Bugzilla_password': ['1234'],
            'GoAheadAndLogIn': ['Log in']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'POST')
        self.assertRegex(req.path, '/index.cgi')
        self.assertEqual(req.parsed_body, expected)

    @httpretty.activate
    def test_logout(self):
        """Test whether the logout is properly completed"""

        # Set up a mock HTTP server
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_LOGIN_URL,
                               body="index.cgi?logout=1",
                               status=200)

        client = BugzillaClient(BUGZILLA_SERVER_URL)
        client.logout()

        req = httpretty.last_request()
        self.assertEqual(req.close_connection, True)

    @httpretty.activate
    def test_invalid_auth(self):
        """Test whether it fails when the authentication goes wrong"""

        # Set up a mock HTTP server
        httpretty.register_uri(httpretty.POST,
                               BUGZILLA_LOGIN_URL,
                               body="",
                               status=200)

        with self.assertRaises(BackendError):
            _ = BugzillaClient(BUGZILLA_SERVER_URL,
                               user='jsmith@example.com',
                               password='1234')

    @httpretty.activate
    def test_not_found_version(self):
        """Test if it fails when the server version is not found"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_no_version.xml')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)

        with self.assertRaises(BackendError):
            client = BugzillaClient(BUGZILLA_SERVER_URL)
            client.buglist()

    @httpretty.activate
    def test_metadata(self):
        """Test metadata API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_version.xml')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.metadata()

        self.assertEqual(response, body)

        # Check request params
        expected = {'ctype': ['xml']}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/show_bug.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_buglist(self):
        """Test buglist API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_version.xml')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)

        body = read_file('data/bugzilla/bugzilla_buglist.csv')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               body=body, status=200)

        # Call API without args
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.buglist()

        self.assertEqual(client.version, '4.2.1+')
        self.assertEqual(response, body)

        # Check request params
        expected = {
            'ctype': ['csv'],
            'limit': ['10000'],
            'order': ['changeddate'],
            'chfieldfrom': ['1970-01-01 00:00:00']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/buglist.cgi')
        self.assertDictEqual(req.querystring, expected)

        # Call API with from_date
        response = client.buglist(from_date=datetime.datetime(2015, 1, 1))

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'ctype': ['csv'],
            'limit': ['10000'],
            'order': ['changeddate'],
            'chfieldfrom': ['2015-01-01 00:00:00']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/buglist.cgi')
        self.assertDictEqual(req.querystring, expected)

        # Call API having defined max_bugs_cvs parameter
        client = BugzillaClient(BUGZILLA_SERVER_URL,
                                max_bugs_csv=300)
        response = client.buglist()

        # Check request params
        expected = {
            'ctype': ['csv'],
            'limit': ['300'],
            'order': ['changeddate'],
            'chfieldfrom': ['1970-01-01 00:00:00']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/buglist.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_buglist_old_version(self):
        """Test buglist API call when the version of the server is less than 3.3"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_version.xml')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)

        body = read_file('data/bugzilla/bugzilla_buglist.csv')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               body=body, status=200)

        # Call API without args
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        client.version = '3.2.3'
        response = client.buglist()

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'ctype': ['csv'],
            'limit': ['10000'],
            'order': ['Last Changed'],
            'chfieldfrom': ['1970-01-01 00:00:00']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/buglist.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_bugs(self):
        """Test bugs API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_bug.xml')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.bugs('8', '9')

        self.assertEqual(response, body)

        # Check request params
        expected = {
            'id': ['8', '9'],
            'ctype': ['xml'],
            'excludefield': ['attachmentdata']
        }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/show_bug.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_bug_activity(self):
        """Test bug acitivity API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla/bugzilla_version.xml')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)

        body = read_file('data/bugzilla/bugzilla_bug_activity.html')
        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.bug_activity('8')

        self.assertEqual(response, body)

        # Check request params
        expected = {'id': ['8']}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/show_activity.cgi')
        self.assertDictEqual(req.querystring, expected)

    def test_sanitize_for_archive(self):
        """Test whether the sanitize method works properly"""

        url = "http://example.com"
        headers = "headers-information"
        payload = {'GoAheadAndLogIn': 'Log in',
                   'Bugzilla_password': '1234',
                   'Bugzilla_login': 'jsmith@example.com'}

        s_url, s_headers, s_payload = BugzillaClient.sanitize_for_archive(url, headers, copy.deepcopy(payload))
        payload.pop('GoAheadAndLogIn')
        payload.pop('Bugzilla_password')
        payload.pop('Bugzilla_login')

        self.assertEqual(url, s_url)
        self.assertEqual(headers, s_headers)
        self.assertEqual(payload, s_payload)


if __name__ == "__main__":
    unittest.main(warnings='ignore')

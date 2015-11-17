#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bitergia
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

import sys

if not '..' in sys.path:
    sys.path.insert(0, '..')

import unittest

import httpretty

from perceval.backends.bugzilla import BugzillaClient


BUGZILLA_SERVER_URL = 'http://example.com'
BUGZILLA_METADATA_URL = BUGZILLA_SERVER_URL + '/show_bug.cgi'
BUGZILLA_BUGLIST_URL = BUGZILLA_SERVER_URL + '/buglist.cgi'
BUGZILLA_BUG_URL = BUGZILLA_SERVER_URL + '/show_bug.cgi'
BUGZILLA_BUG_ACTIVITY_URL = BUGZILLA_SERVER_URL + '/show_activity.cgi'


def read_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    return content


class TestBugzillaClient(unittest.TestCase):
    """Bugzilla API client tests"""

    @httpretty.activate
    def test_metadata(self):
        """Test metadata API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_version.xml')

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_METADATA_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.metadata()

        self.assertEqual(response, body)

        # Check request params
        expected = {'ctype' : ['xml']}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/show_bug.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_buglist(self):
        """Test buglist API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_buglist.csv')

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               body=body, status=200)

        # Call API without args
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.buglist()

        self.assertEqual(response, body)

        # Check request params
        expected = {
                    'ctype' : ['csv'],
                    'order' : ['changeddate'],
                    'chfieldfrom' : ['1970-01-01']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/buglist.cgi')
        self.assertDictEqual(req.querystring, expected)

        # Call API with from_date and version args
        response = client.buglist(from_date='2015-01-01', version='4.0')

        self.assertEqual(response, body)

        # Check request params
        expected = {
                    'ctype' : ['csv'],
                    'order' : ['changeddate'],
                    'chfieldfrom' : ['2015-01-01']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/buglist.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_buglist_old_version(self):
        """Test buglist API call when the version of the server is less than 3.3"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_buglist.csv')

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUGLIST_URL,
                               body=body, status=200)

        # Call API without args
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.buglist(version='3.2.3')

        self.assertEqual(response, body)

        # Check request params
        expected = {
                    'ctype' : ['csv'],
                    'order' : ['Last Changed'],
                    'chfieldfrom' : ['1970-01-01']
                    }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/buglist.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_bug(self):
        """Test bug API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_bug.xml')

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.bug('8')

        self.assertEqual(response, body)

        # Check request params
        expected = {
                    'id' : ['8'],
                    'ctype' : ['xml'],
                    'excludefield' : ['attachmentdata']
                   }

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/show_bug.cgi')
        self.assertDictEqual(req.querystring, expected)

    @httpretty.activate
    def test_bug_activity(self):
        """Test bug acitivity API call"""

        # Set up a mock HTTP server
        body = read_file('data/bugzilla_bug_activity.html')

        httpretty.register_uri(httpretty.GET,
                               BUGZILLA_BUG_ACTIVITY_URL,
                               body=body, status=200)

        # Call API
        client = BugzillaClient(BUGZILLA_SERVER_URL)
        response = client.bug_activity('8')

        self.assertEqual(response, body)

        # Check request params
        expected = {'id' : ['8']}

        req = httpretty.last_request()

        self.assertEqual(req.method, 'GET')
        self.assertRegex(req.path, '/show_activity.cgi')
        self.assertDictEqual(req.querystring, expected)


if __name__ == "__main__":
    unittest.main()
